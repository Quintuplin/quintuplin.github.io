#!/usr/bin/env python3
"""Check the Kalah TDD study landing page (#62): the showcase summary, one Awards section, the report Headline with its
framed figures, and a contents list of every page.

Usage: check_kalah_tdd_page_landing.py
"""
import functools
import importlib
import importlib.util
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ARTIFACT = "https://claude.ai/artifact/5g7jbNAxSnZPjQ2nLEJ15a"
SVG = re.compile(r"<svg\b.*?</svg>", re.S)


@functools.cache
def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def kalah(name):
    module("build_kalah_tdd_study")
    return importlib.import_module(f"kalah_tdd.{name}")


@functools.cache
def snap():
    return kalah("snapshot").load()


def landing_page():
    return kalah("pagemap").PAGES[0]


@functools.cache
def html():
    return module("build_kalah_tdd_study").render_page(landing_page(), snap(), kalah("links").index(snap()))


@functools.cache
def root():
    return module("check_kalah_tdd_study").Tree(html()).root


def main_node():
    return next(n for n in root().iter() if n.tag == "main")


def by_id(id):
    return next(n for n in root().iter() if n.attrs.get("id") == id)


def text(node):
    return " ".join(node.text(" ").split())


def section(id):
    """The h2 with this id and every element after it up to the next h2, as nodes under main."""
    kids, out = main_node().elements(), []
    start = next(i for i, n in enumerate(kids) if n.attrs.get("id") == id)
    for n in kids[start:]:
        if out and n.tag == "h2":
            break
        out.append(n)
    return out


def missing_text(s):
    """Each p, li, dt and dd text of the landing sources that the landing built from snapshot s leaves out."""
    snapshot, tree = kalah("snapshot"), module("check_kalah_tdd_study").Tree
    report = s.files[snapshot.REPORT]
    head, methods = snapshot.section(report, "kalah-tdd-experiment"), snapshot.section(report, "methods")
    sources = (snapshot.view(s.files[snapshot.SHOWCASE], "summary"), head[:head.index('<h3 id="awards"')],
               methods[:methods.index('<h3 id="classic-greedy-tdd"')])
    page = text(tree(module("build_kalah_tdd_study").render_page(landing_page(), s, kalah("links").index(s))).root)
    # Claim tag sentences render as a tag pill holding the kind.
    chunks = [kalah("pages.landing").TAG.sub(r"\1", text(n)) for source in sources for n in tree(source).root.iter()
              if n.tag in ("p", "li", "dt", "dd")]
    return [c for c in chunks if c not in page and c not in ("Kalah TDD showcase", "Kalah TDD Experiment")]


def hrefs(nodes):
    return [a.attrs["href"] for n in nodes for a in n.iter() if a.tag == "a" and "href" in a.attrs]


class LandingStructure(unittest.TestCase):
    def test_built_not_stub(self):
        self.assertIsNotNone(kalah("pages").built(landing_page()))
        self.assertNotIn('<meta name="kalah-tdd-stub">', html())

    def test_one_h1_and_ordered_headings(self):
        levels = [int(n.tag[1]) for n in root().iter() if re.fullmatch(r"h[1-6]", n.tag)]
        self.assertEqual(levels.count(1), 1)
        self.assertEqual(levels[0], 1)
        for a, b in zip(levels, levels[1:]):
            self.assertLessEqual(b, a + 1, f"heading levels skip from h{a} to h{b}")

    def test_anchors_kept(self):
        ids = kalah("links").ID.findall(html())
        for anchor in landing_page().anchors:
            with self.subTest(anchor):
                self.assertEqual(ids.count(anchor), 1)

    def test_showcase_head_matches_header(self):
        summary = kalah("snapshot").view(snap().files[kalah("snapshot").SHOWCASE], "summary")
        h1 = re.search(r"<h1>(.*?)</h1>", summary).group(1)
        lede = re.search(r'<p class="lede">(.*?)</p>', summary).group(1)
        self.assertEqual(h1, landing_page().title)
        self.assertEqual(lede, landing_page().blurb)
        self.assertEqual([text(n) for n in root().iter() if n.tag == "h1"], [landing_page().title])
        self.assertNotIn("Kalah TDD showcase", text(main_node()))


class LandingContent(unittest.TestCase):
    def test_covers_all_landing_items(self):
        study = module("check_kalah_tdd_study")
        items, errors = study.inventory(snap().files)
        self.assertEqual(errors, [])
        landing = [i for i in items if i.page == ""]
        self.assertEqual(len(landing), 70, "the landing item count changed; recount before re-pinning")
        self.assertEqual(study.coverage(landing, {"": html()}), ([], 70))

    def test_awards_merged(self):
        h2 = [n for n in root().iter() if n.tag == "h2" and text(n) == "Awards"]
        self.assertEqual(len(h2), 1)
        self.assertEqual(h2[0].attrs.get("id"), "awards")
        nodes = section("awards")
        cards = [n for s in nodes for n in s.iter() if n.tag == "article" and "award" in n.classes()]
        self.assertEqual(len(cards), 6)
        places = [n for s in nodes for n in s.iter() if "awards" in n.classes()]
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0].closest("details").tag, "details", "the report award places sit in a fold")

    def test_contents_lists_every_page(self):
        pagemap, links = kalah("pagemap"), kalah("links")
        nodes = section("contents")
        self.assertEqual(hrefs(nodes), [links.url(p.slug) for p in pagemap.PAGES])
        lists = [n for s in nodes for n in s.iter() if n.tag == "ol"]
        self.assertEqual(len(lists), len(pagemap.PARTS))
        for part, ol in zip(pagemap.PARTS, lists):
            pages = [p for p in pagemap.PAGES if p.part == part]
            with self.subTest(part):
                self.assertEqual(text(ol.closest(cls="design").elements()[0]), part)
                self.assertEqual(ol.attrs.get("start"), str(pagemap.number(pages[0].slug)))
                entries = [li for li in ol.elements() if li.tag == "li"]
                self.assertEqual([text(li) for li in entries], [f"{p.title} {p.blurb}" for p in pages])
        current = [a for s in nodes for a in s.iter() if a.attrs.get("aria-current") == "page"]
        self.assertEqual([a.attrs["href"] for a in current], [links.url("")])

    def test_figures_framed(self):
        report = snap().files[kalah("snapshot").REPORT]
        for n, id in (("1.1", "pmd-cost"), ("1.2", "rep-1-mutation")):
            with self.subTest(id):
                fig = by_id(id)
                self.assertEqual(fig.tag, "figure")
                self.assertTrue(fig.attrs["aria-label"].startswith(f"Figure {n}: "))
                source = re.search(rf'<figure id="{id}">.*?</figure>', report, re.S).group(0)
                framed = re.search(rf'<figure id="{id}".*?</figure>', html(), re.S).group(0)
                self.assertEqual(SVG.findall(framed), SVG.findall(source))
                data = [a for a in fig.iter() if a.tag == "a" and text(a) == "Data"]
                self.assertEqual([a.attrs["href"] for a in data], [f"#{id}-data"])
                self.assertEqual(by_id(f"{id}-data").tag, "details")
                self.assertIs(by_id(f"{id}-data").closest("figure"), fig)

    def test_no_self_or_old_links(self):
        links = hrefs([main_node()])
        self.assertNotIn(ARTIFACT, html())
        designs = {f"#{d[0]}" for d in kalah("pagemap").DESIGNS}
        self.assertEqual([h for h in links if h in designs or ".html" in h], [])
        notes = [a for s in section("about-the-data") for a in s.iter() if a.tag == "a"]
        self.assertEqual([a.attrs["href"] for a in notes], ["#contents"])
        self.assertEqual(links.count(kalah("links").url("")), 1, "only the contents entry links the landing itself")

    def test_doc_versions_cover_the_report_runs(self):
        snapshot = kalah("snapshot")
        listed = re.search(r"Runs: (.*?)\.", snap().files[snapshot.REPORT]).group(1)
        page = text(main_node())
        self.assertIn(f"methods doc {snap().doc}", page)
        for run in (r.split()[0] for r in listed.split(", ")):
            with self.subTest(run):
                self.assertEqual(page.count(f"{run} {snapshot.run_doc(snap(), run)}"), 1)

    def test_doc_versions_cover_every_named_run(self):
        snapshot = kalah("snapshot")
        docs = [text(n) for n in main_node().iter() if n.tag == "p" and text(n).startswith("The methods text")]
        self.assertEqual(len(docs), 1)
        rest = text(main_node()).replace(docs[0], "")
        keys = "|".join(map(re.escape, sorted(snap().facts["runs"], key=len, reverse=True)))
        named = set(re.findall(rf"(?<![\w/-])({keys})(?![\w/-])", rest))
        self.assertIn("tcp-1", named)
        for run in named:
            with self.subTest(run):
                self.assertEqual(docs[0].count(f"{run} {snapshot.run_doc(snap(), run)}"), 1)

    def test_keeps_all_source_text(self):
        self.assertEqual(missing_text(snap()), [])

    def test_keeps_added_source_text(self):
        s, snapshot = snap(), kalah("snapshot")
        summary, report = snapshot.view(s.files[snapshot.SHOWCASE], "summary"), s.files[snapshot.REPORT]
        intro = re.search(r'<h2 id="methods">Methods</h2>\s*<p>.*?</p>', report, re.S).group(0)
        files = {**s.files, snapshot.SHOWCASE: s.files[snapshot.SHOWCASE].replace(
                     summary, summary + "<h2>Caveats</h2><ul><li>An added showcase note.</li></ul>"),
                 snapshot.REPORT: report.replace(intro, intro + "<p>An added methods paragraph.</p>")}
        self.assertEqual(missing_text(s._replace(files=files)), [])

    def test_runs_come_from_the_text(self):
        named = kalah("pages.landing").named_runs
        self.assertEqual(named(snap(), "<p>Runs: rep-2 a, <b>full-1</b> b, tcp-1-list2 c. Again rep-2.</p>"),
                         ["rep-2", "full-1", "tcp-1-list2"])


if __name__ == "__main__":
    unittest.main()
