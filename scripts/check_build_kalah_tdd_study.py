#!/usr/bin/env python3
"""Check the Kalah TDD study page generator (#59): byte-for-byte --check, old link rewrites, unique ids, host paths,
page order and stub markers. Also checks that the committed pages match a fresh build.

Usage: check_build_kalah_tdd_study.py
"""
import functools
import importlib.util
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
SITE = SCRIPTS.parent
BASE = "/studies/kalah-tdd-study/"
ARTIFACT = "https://claude.ai/artifact/5g7jbNAxSnZPjQ2nLEJ15a"
HREF = re.compile(r'href="([^"]*)"')
ID = re.compile(r'\bid="([^"]+)"')


@functools.cache
def build():
    spec = importlib.util.spec_from_file_location("build_kalah_tdd_study", SCRIPTS / "build_kalah_tdd_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kalah(name):
    build()
    return importlib.import_module(f"kalah_tdd.{name}")


@functools.cache
def snap():
    return kalah("snapshot").load()


@functools.cache
def rendered():
    return build().render_pages(snap())


def slugs():
    return [p.slug for p in kalah("pagemap").PAGES]


def page_url(slug):
    return BASE + (f"{slug}/" if slug else "")


class Check(unittest.TestCase):
    def test_check_fails_on_hand_edit(self):
        b = build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            b.write_pages(out, rendered())
            self.assertEqual(b.check_current(out, rendered()), [])
            page = out / "methodology/index.html"
            page.write_bytes(page.read_bytes().replace(b"</main>", b"<p>hand edit</p></main>"))
            self.assertRegex(" ".join(b.check_current(out, rendered())), "methodology/index.html")
            page.unlink()
            self.assertRegex(" ".join(b.check_current(out, rendered())), "methodology/index.html")
            b.write_pages(out, rendered())
            (out / "retired").mkdir()
            (out / "retired/index.html").write_text("stale")
            self.assertRegex(" ".join(b.check_current(out, rendered())), "retired/index.html")
            b.write_pages(out, rendered())
            self.assertFalse((out / "retired/index.html").exists(), "a write left a page the map no longer has")

    def test_committed_pages_are_current(self):
        self.assertEqual(build().check_current(build().OUT, rendered()), [])

    def test_output_is_deterministic(self):
        self.assertEqual(build().render_pages(snap()), rendered())


class Links(unittest.TestCase):
    def test_rewrites_every_old_link(self):
        links = kalah("links")
        idx = links.index(snap())
        for doc in idx:
            for href in sorted(set(HREF.findall(snap().files[doc]))):
                with self.subTest(doc=doc, href=href):
                    new = HREF.search(links.rewrite(f'<a href="{href}">', doc, None, idx)).group(1)
                    if href.startswith("https://") and href != ARTIFACT:
                        self.assertEqual(new, href)
                        continue
                    path, _, frag = new.partition("#")
                    self.assertIn(path, [page_url(s) for s in slugs()])
                    self.assertNotRegex(new, r"\.html|claude\.ai")

    def test_rewrites_each_old_link_kind(self):
        links = kalah("links")
        idx = links.index(snap())
        cases = [("runs/full-1/report.html", "#q12", BASE + "questions/#q12"),
                 ("runs/full-1/report.html", "methods/tpp.html", BASE + "designs/tpp/"),
                 ("runs/full-1/report.html", "#classic-greedy-tdd", BASE + "designs/classic/#classic-greedy-tdd"),
                 ("runs/full-1/report.html", "#run-record-rep-1", BASE + "data/runs/#run-record-rep-1"),
                 ("runs/full-1/methods/classic.html", "../report.html", BASE),
                 ("runs/full-1/methods/classic.html", "held-out.html", BASE + "designs/held-out/"),
                 ("runs/full-1/methods/classic.html", "#columns", BASE + "designs/classic/#columns"),
                 ("artifact/showcase.html", "#mapped-path", BASE + "designs/mapped-path/"),
                 ("artifact/showcase.html", "#summary", BASE),
                 ("artifact/showcase.html", ARTIFACT, BASE)]
        for doc, old, new in cases:
            with self.subTest(old=old):
                self.assertEqual(links.rewrite(f'<a href="{old}">x</a>', doc, None, idx), f'<a href="{new}">x</a>')
        # A link to the page it sits on keeps only its fragment.
        self.assertEqual(links.rewrite('<a href="#q3">', "runs/full-1/report.html", "questions", idx), '<a href="#q3">')

    def test_refuses_unknown_link(self):
        links = kalah("links")
        idx = links.index(snap())
        for href in ("#no-such-anchor", "other/page.html", "methods/missing.html"):
            with self.subTest(href=href), self.assertRaises(ValueError):
                links.rewrite(f'<a href="{href}">', "runs/full-1/report.html", None, idx)

    def test_ids_unique_per_page(self):
        for path, html in rendered().items():
            with self.subTest(path):
                ids = ID.findall(html)
                self.assertEqual(len(ids), len(set(ids)))
        links = kalah("links")
        first = '<h2 id="columns">A</h2>'
        second = ('<h3 id="columns">B</h3><a href="#columns">B</a><svg aria-labelledby="t columns">'
                  '<path marker-end="url(#columns)"/></svg><p id="columns-2">C</p>')
        a, b = links.unique_ids([first, second], reserved=("main",))
        self.assertEqual(a, first)
        self.assertEqual(b, '<h3 id="columns-3">B</h3><a href="#columns-3">B</a><svg aria-labelledby="t columns-3">'
                            '<path marker-end="url(#columns-3)"/></svg><p id="columns-2">C</p>')
        self.assertEqual(links.unique_ids(['<p id="main">x</p>'], reserved=("main",)), ['<p id="main-2">x</p>'])


class Snapshot(unittest.TestCase):
    def test_load_refuses_changed_file(self):
        s = kalah("snapshot")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("MANIFEST.json", *snap().files, "facts.json"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes((s.ROOT / name).read_bytes())
            self.assertEqual(s.load(root).sha, snap().sha)
            (root / s.SHOWCASE).write_bytes((root / s.SHOWCASE).read_bytes() + b" ")
            with self.assertRaisesRegex(SystemExit, "MANIFEST"):
                s.load(root)

    def test_section_and_view(self):
        s = kalah("snapshot")
        report = snap().files[s.REPORT]
        part = s.section(report, "test-order")
        self.assertTrue(part.startswith('<h3 id="test-order">Test order</h3>'))
        self.assertTrue(report.split(part, 1)[1].lstrip().startswith('<h2 id="methods"'))
        # An h2 runs past its h3 children to the next h2; the last section stops at the end of main.
        self.assertIn('id="key-findings"', s.section(snap().files[s.REPORT], "headline"))
        self.assertNotIn("</main>", s.section(snap().files[s.REPORT], "run-record-rep-2"))
        view = s.view(snap().files[s.SHOWCASE], "classic")
        self.assertIn("<h1>Classic greedy TDD</h1>", view)
        self.assertNotIn("<h1>Noun-verb map</h1>", view)
        self.assertRaises(ValueError, s.section, snap().files[s.REPORT], "nowhere")


class HostPaths(unittest.TestCase):
    def test_rejects_host_path(self):
        b = build()
        for leak in ("/Users/echo/project/tdd-experiment/runs", "C:/Users/quint/tdd", "C:\\Users\\quint", "~/clones/r01",
                     "/home/runner/work/x", "E:/Obi-Done/Claude", "Cryptomator vault", "file:///tmp/x"):
            with self.subTest(leak), self.assertRaisesRegex(SystemExit, "host path"):
                b.refuse_host_paths({"x/index.html": f"<p>{leak}</p>"})

    def test_allows_links_and_prose(self):
        build().refuse_host_paths(rendered())
        # Every source string passes, its https:// links included.
        hits = {(doc, m.group(0)) for doc, text in snap().files.items() for m in build().LOCAL_PATH.finditer(text)}
        self.assertEqual(hits, set())
        build().refuse_host_paths({"x/index.html": '<a href="https://github.com/Users/x">E: distinct</a> a / b '
                                                   '<a href="/projects">P</a> rep-2/rebuild'})


class Pages(unittest.TestCase):
    def test_prev_next_order(self):
        pagemap = kalah("pagemap")
        self.assertEqual(len(pagemap.PAGES), 29)
        self.assertEqual(slugs()[0], "")
        self.assertEqual(len(set(slugs())), 29)
        for i, slug in enumerate(slugs()):
            prev, nxt = pagemap.neighbours(slug)
            self.assertEqual(prev and prev.slug, slugs()[i - 1] if i else None)
            self.assertEqual(nxt and nxt.slug, slugs()[i + 1] if i < 28 else None)
            html = rendered()[build().page_path(pagemap.PAGES[i])]
            for rel, other in (("prev", prev), ("next", nxt)):
                hrefs = re.findall(rf'<a rel="{rel}" href="([^"]*)"', html)
                self.assertEqual(hrefs, [page_url(other.slug)] * 2 if other else [], (slug, rel))
            bars = re.findall(r'<nav class="pager" aria-label="([^"]*)">(.*?)</nav>', html, re.S)
            self.assertEqual(len(bars), 2)
            self.assertNotEqual(bars[0][0], bars[1][0], "the two pagers need distinct labels")
            self.assertEqual(bars[0][1], bars[1][1], "the top and bottom pagers differ")
            self.assertIn(f'<a class="pager-home" href="{BASE}">', bars[0][1])

    def test_parts(self):
        pagemap = kalah("pagemap")
        self.assertEqual(list(dict.fromkeys(p.part for p in pagemap.PAGES)), list(pagemap.PARTS))
        self.assertEqual(len(pagemap.PARTS), 8)
        self.assertEqual(pagemap.part_of("designs/tpp"), "Designs")
        html = rendered()["methodology/measures/index.html"]
        self.assertIn("Kalah TDD study · Part 4 of 29 · Methodology", html)
        self.assertEqual(re.findall(r'<a [^>]*aria-current="page"[^>]*>', html.split('class="toc"', 1)[1]),
                         [f'<a href="{BASE}methodology/measures/" aria-current="page">'])

    def test_stub_marker(self):
        pages = kalah("pages")
        for page in kalah("pagemap").PAGES:
            html = rendered()[build().page_path(page)]
            with self.subTest(page.slug):
                stub = pages.built(page) is None
                self.assertEqual(html.count('<meta name="kalah-tdd-stub">'), stub)
                self.assertEqual("This part is being written" in html, stub)
        page = kalah("pagemap").PAGES[1]
        fake = types.SimpleNamespace(body=lambda page, snap, idx: '<h2 id="intro">Intro</h2>')
        with mock.patch.object(pages, "built", return_value=fake):
            html = build().render_page(page, snap(), kalah("links").index(snap()))
        self.assertNotIn("kalah-tdd-stub", html)
        self.assertNotIn("being written", html)
        self.assertIn(f'<li><a href="{BASE}{page.slug}/#intro">Intro</a></li>', html)

    def test_shell(self):
        bar = re.search(r'<nav class="site-bar".*?</style>', (SITE / "studies/subagent-crew-study/index.html").read_text(),
                        re.S).group(0)
        sha = snap().sha
        for path, html in rendered().items():
            with self.subTest(path):
                self.assertTrue(html.startswith('<!doctype html>\n<html lang="en">'))
                self.assertIn(bar, html)
                self.assertEqual(html.count("<h1"), 1)
                self.assertEqual(html.count("<main"), 1)
                self.assertIn(f'<meta name="generator" content="scripts/build_kalah_tdd_study.py from Quintuplin/tdd-experiment {sha}">', html)
                self.assertIn('<link rel="stylesheet" href="/studies/kalah-tdd-study/study.css">', html)
                self.assertIn("IBM+Plex+Mono:wght@400;500;600", html)
                self.assertIn(f"tdd-experiment <code>{sha[:7]}</code>", html)
                self.assertRegex(html, r'<div class="backdrop" aria-hidden="true"></div>\s*<div class="sheet">')
                self.assertRegex(html, re.compile(r'</style>\s*<a class="skip" href="#main">[^<]+</a>\s*<div class="study">\s*'
                                       r'<header class="study-head">.*?</header>\s*<nav class="pager".*?</nav>\s*'
                                       r'<details class="toc" id="toc">.*?</details>\s*<main id="main">.*?</main>\s*'
                                       r'<nav class="pager".*?</nav>\s*</div>\s*</div>', re.S))
                self.assertIn('<nav aria-label="Study contents">', html)
                self.assertNotIn("---", html.split("\n", 1)[0])


if __name__ == "__main__":
    unittest.main()
