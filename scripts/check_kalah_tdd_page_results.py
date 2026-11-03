#!/usr/bin/env python3
"""Check the four Kalah TDD results pages (#89): each report results section kept verbatim with its heading as h2,
its figures numbered by part with svg bytes unchanged, free tables in labelled regions and question links pointed
at the questions page.

Usage: check_kalah_tdd_page_results.py [--render]
--render prints the four pages, which test_deterministic compares across hash seeds.
"""
import functools
import importlib
import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
BASE = "/studies/kalah-tdd-study/"
SLUGS = ("results/survey", "results/contrasts", "results/consistency", "results/test-order")
# Report results items on the four pages, from check_kalah_tdd_study.inventory at the snapshot sha.
RESULTS_ITEMS = 283
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
P_OR_ENTRY = re.compile(r'<p\b[^>]*>.*?</p>|<div class="entry">.*?</div>', re.S)


@functools.cache
def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kalah(name):
    script("build_kalah_tdd_study")
    return importlib.import_module(f"kalah_tdd.{name}")


def study():
    return script("check_kalah_tdd_study")


@functools.cache
def snap():
    return kalah("snapshot").load()


def report():
    return snap().files[kalah("snapshot").REPORT]


def page(slug):
    return kalah("pagemap").BY_SLUG[slug]


@functools.cache
def html(slug):
    return (STUDY / slug / "index.html").read_text(encoding="utf-8")


def own(id):
    """The report section of this heading up to its first nested heading with an id."""
    snapshot = kalah("snapshot")
    sec = snapshot.section(report(), id)
    nested = snapshot.HEADING.search(sec, 1)
    return sec[:nested.start()] if nested else sec


def sources(slug):
    return [own(a) for a in page(slug).anchors]


def nodes(slug):
    return list(study().parse(html(slug)).root.iter())


def headings(slug):
    return [n for n in nodes(slug) if study().heading(n)]


def render():
    build = script("build_kalah_tdd_study")
    s = snap()
    idx = kalah("links").index(s)
    return "".join(build.render_page(page(slug), s, idx) for slug in SLUGS)


class Results(unittest.TestCase):
    def test_built_not_stub(self):
        for slug in SLUGS:
            with self.subTest(slug):
                parsed = study().parse(html(slug))
                self.assertFalse(parsed.stub, f"{slug} is a stub")
                levels = [study().heading(h) for h in headings(slug)]
                self.assertEqual(levels.count(1), 1)
                self.assertEqual(levels[0], 1)
                self.assertFalse([b for a, b in zip(levels, levels[1:]) if b > a + 1], f"heading skipped: {levels}")
                ids = [n.attrs["id"] for n in nodes(slug) if n.attrs.get("id")]
                self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
                main = parsed.ids["main"]
                h2 = [n.attrs.get("id") for n in main.iter() if n.tag == "h2"]
                self.assertEqual(h2, list(page(slug).anchors))
                current = next(n for n in parsed.ids["toc"].iter() if n.attrs.get("aria-current") == "page")
                listed = [a.attrs["href"] for a in current.parent.iter() if a.tag == "a" and a is not current]
                self.assertEqual(listed, [f"{BASE}{slug}/#{a}" for a in page(slug).anchors])

    def test_coverage_counts_results(self):
        items, errors = study().inventory(snap().files)
        self.assertEqual(errors, [])
        items = [i for i in items if i.page in SLUGS]
        self.assertEqual(len(items), RESULTS_ITEMS)
        errors, checked = study().coverage(items, {slug: html(slug) for slug in SLUGS})
        self.assertEqual(errors, [])
        self.assertEqual(checked, RESULTS_ITEMS)

    def test_source_figures_numbered(self):
        for slug in SLUGS:
            want = [f for sec in sources(slug) for f in re.findall(r'<figure id="[^"]+">.*?</figure>', sec, re.S)]
            figs = re.findall(r'<figure id="([^"]+)" aria-label="Figure (\d+\.\d+): [^"]*">(.*?)</figure>', html(slug), re.S)
            part = kalah("pagemap").number(slug)
            with self.subTest(slug):
                self.assertEqual([f[0] for f in figs], [re.match(r'<figure id="([^"]+)"', w).group(1) for w in want])
                self.assertEqual([f[1] for f in figs], [f"{part}.{k}" for k in range(1, len(want) + 1)])
                for (id, _, body), source in zip(figs, want):
                    self.assertEqual(SVG.findall(body), SVG.findall(source), id)
                ids = set(study().parse(html(slug)).ids)
                for target in re.findall(r'<a href="#([^"]+)"[^>]*>Data</a>', html(slug)):
                    self.assertIn(target, ids)
        self.assertEqual([len(re.findall(r'<figure id="[^"]+" aria-label="Figure', html(s))) for s in SLUGS], [3, 8, 1, 0])

    def test_section_text_verbatim(self):
        squash = study().squash
        for slug in SLUGS:
            texts = study().parse(html(slug)).texts
            want = [squash(study().Tree(m).root.text()) for sec in sources(slug) for m in P_OR_ENTRY.findall(sec)]
            with self.subTest(slug):
                self.assertTrue(want)
                self.assertEqual([t for t in want if not texts[t]], [])
        main = study().parse(html("results/survey")).ids["main"]
        intro = re.search(r"<p>(.*?)</p>", own("arguments"), re.S).group(1)
        h2 = next(n for n in main.iter() if n.attrs.get("id") == "arguments")
        after = h2.parent.elements()[h2.parent.elements().index(h2) + 1]
        self.assertEqual(squash(after.text()), squash(study().Tree(intro).root.text()))

    def test_free_tables_wrapped(self):
        for slug in SLUGS:
            for table in (n for n in nodes(slug) if n.tag == "table"):
                region = table.closest("div", "table-scroll")
                in_view = table.closest("details") and table.closest("figure")
                with self.subTest(slug):
                    self.assertTrue(in_view or (region and region.attrs.get("role") == "region"
                                                and region.attrs.get("aria-label")), "a free table outside a region")
        main = study().parse(html("results/contrasts")).ids["main"]
        free = [t for t in main.iter() if t.tag == "table" and not t.closest("figure")]
        self.assertEqual(len(free), 2)
        regions = {id(t.closest("div", "table-scroll")) for t in free}
        self.assertEqual(len(regions), 1, "the rep-1 tables share one region")
        self.assertEqual(free[0].closest("div", "table-scroll").attrs.get("aria-label"), "Planned contrasts (rep-1)")

    def test_question_links(self):
        total = 0
        for slug in SLUGS:
            hrefs = re.findall(r'href="([^"]*)"', html(slug))
            q = [h for h in hrefs if re.search(r"#q\d+$", h)]
            want = sum(len(re.findall(r'href="#q\d+"', sec)) for sec in sources(slug))
            with self.subTest(slug):
                self.assertEqual(len(q), want)
                self.assertEqual([h for h in q if not re.fullmatch(rf"{BASE}questions/#q\d+", h)], [])
                self.assertEqual([h for h in hrefs if "report.html" in h], [])
            total += want
        self.assertGreater(total, 0)

    def test_refuses_unknown_block(self):
        results = kalah("pages.results")
        for block in ("<ul><li>b</li></ul>", "stray text", '<div class="shaped"><table></table><div class="entry"></div></div>',
                      '<p class="lead">x</p>'):
            with self.subTest(block), self.assertRaises(ValueError) as caught:
                results.split("made-up", f'<h3 id="made-up">Made up</h3><p>a</p>{block}<p>c</p>')
            self.assertIn("made-up", str(caught.exception))
            self.assertIn(block[:12], str(caught.exception))
        kinds = [k for k, _ in results.split("made-up", '<h3 id="made-up">Made up</h3>\n<p>a</p>\n'
                                                       '<div class="shaped"><div class="entry"><p>e</p></div></div>')]
        self.assertEqual(kinds, ["p", "entries"])

    def test_deterministic(self):
        # Set order follows the hash seed, so a second process with another seed shows any order the pages rely on.
        # -I would ignore PYTHONHASHSEED, so the child gets -s -P, the parent's -B and an environment of the seed alone.
        seed = "1" if os.environ.get("PYTHONHASHSEED") == "0" else "0"
        flags = ["-s", "-P"] + ["-B"] * sys.flags.dont_write_bytecode
        child = subprocess.run([sys.executable, *flags, __file__, "--render"], env={"PYTHONHASHSEED": seed},
                               capture_output=True, check=False)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        mine = render()
        self.assertNotIn("kalah-tdd-stub", mine)
        self.assertEqual(child.stdout, mine.encode())


if __name__ == "__main__":
    if sys.argv[1:] == ["--render"]:
        sys.stdout.buffer.write(render().encode())
    else:
        unittest.main()
