#!/usr/bin/env python3
"""Check the Kalah TDD study landing page (#62): the showcase summary, one Awards section, the report Headline with its
framed figures, and a contents list of every page.

Usage: check_kalah_tdd_page_landing.py
"""
import collections
import functools
import importlib
import importlib.util
import re
import sys
import unittest
import unittest.mock
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ARTIFACT = "https://claude.ai/artifact/5g7jbNAxSnZPjQ2nLEJ15a"
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
# The runs the committed landing names, in first-mention order. Recount by reading the page before re-pinning.
NAMED_RUNS = ("full-1", "tcp-1-list2", "rep-1", "rep-2", "tcp-1")


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
    """Each p, li, dt and dd text of the landing sources that the landing built from snapshot s leaves out. A chunk
    counts only as a whole element of its own kind, once per copy, so a dropped one-letter cell still shows."""
    snapshot, tree = kalah("snapshot"), module("check_kalah_tdd_study").Tree
    report = s.files[snapshot.REPORT]
    head, methods = snapshot.section(report, "kalah-tdd-experiment"), snapshot.section(report, "methods")
    sources = (snapshot.view(s.files[snapshot.SHOWCASE], "summary"), head[:head.index('<h3 id="awards"')],
               methods[:methods.index('<h3 id="classic-greedy-tdd"')])
    kinds = ("p", "li", "dt", "dd")
    page = tree(module("build_kalah_tdd_study").render_page(landing_page(), s, kalah("links").index(s))).root
    left = collections.Counter((n.tag, text(n)) for n in page.iter() if n.tag in kinds)
    out = []
    for n in (n for source in sources for n in tree(source).root.iter() if n.tag in kinds):
        # Claim tag sentences render as a tag pill holding the kind.
        chunk = (n.tag, kalah("pages.landing").TAG.sub(r"\1", text(n)))
        if left[chunk]:
            left[chunk] -= 1
        elif chunk[1] != "Kalah TDD showcase":
            out.append(chunk[1])
    return out


def doc_version_gaps(page):
    """What the doc version sentence of the committed landing page gets wrong: its runs against the expected list,
    then against a plain token scan of the rest of the page, each with its own run_doc."""
    snapshot = kalah("snapshot")
    main = next(n for n in module("check_kalah_tdd_study").Tree(page).root.iter() if n.tag == "main")
    docs = [text(n) for n in main.iter() if n.tag == "p" and text(n).startswith("The methods text")]
    if len(docs) != 1:
        return [f"{len(docs)} doc version sentences"]
    listed = docs[0].split("short sha256: ", 1)[1].removesuffix(".").split(", ")
    tokens = {t.strip(".,;:()") for t in text(main).replace(docs[0], "").split()}
    named = sorted(tokens & set(snap().facts["runs"]))
    gaps = [] if [e.split()[0] for e in listed] == list(NAMED_RUNS) else [f"lists {listed}"]
    gaps += [run for run in named if f"{run} {snapshot.run_doc(snap(), run)}" not in listed]
    return gaps + [e for e in listed if e.split()[0] not in named]


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
        self.assertEqual(doc_version_gaps(html()), [])

    def test_doc_version_check_catches_wrong_guard(self):
        landing = kalah("pages.landing")

        def wrong(s, html):  # a space joins the lookahead guard, so a run followed by a space goes unnamed
            keys = "|".join(map(re.escape, sorted(s.facts["runs"], key=len, reverse=True)))
            return list(dict.fromkeys(re.findall(rf"(?<![\w/-])({keys})(?![\w/ -])", re.sub(r"<[^>]+>", " ", html))))

        with unittest.mock.patch.object(landing, "named_runs", wrong):
            page = module("build_kalah_tdd_study").render_page(landing_page(), snap(), kalah("links").index(snap()))
        self.assertNotEqual(doc_version_gaps(page), [])

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

    def test_dropped_short_text_reported(self):
        build, page = module("build_kalah_tdd_study"), html()
        for cell in ("<dt>E</dt>", "<dd>9</dd>"):
            with self.subTest(cell), unittest.mock.patch.object(
                    build, "render_page", lambda *_, cell=cell: page.replace(cell, cell[:4] + cell[5:], 1)):
                self.assertEqual(missing_text(snap()), [cell[4]])

    def test_added_section_ids_stay_unique(self):
        s, snapshot = snap(), kalah("snapshot")
        summary = snapshot.view(s.files[snapshot.SHOWCASE], "summary")
        added = "<h2>Contents</h2><p>An added contents note.</p><h2><em>Notes</em> &amp; more</h2><p>A note.</p>"
        s = s._replace(files={**s.files, snapshot.SHOWCASE: s.files[snapshot.SHOWCASE].replace(summary, summary + added)})
        page = module("build_kalah_tdd_study").render_page(landing_page(), s, kalah("links").index(s))
        ids = kalah("links").ID.findall(page)
        self.assertEqual(sorted(i for i in set(ids) if ids.count(i) > 1), [])
        self.assertIn("notes-more", ids)
        # Every #contents link reaches the contents list, not the added section.
        after = page.split('<h2 id="contents">', 1)[1]
        self.assertTrue(after.startswith("Contents</h2>"))
        self.assertIn('<div class="grid contents">', after.split("<h2", 1)[0])
        self.assertIn('href="#contents"', page)

    def test_runs_come_from_the_text(self):
        named = kalah("pages.landing").named_runs
        self.assertEqual(named(snap(), "<p>Runs: rep-2 a, <b>full-1</b> b, tcp-1-list2 c. Again rep-2.</p>"),
                         ["rep-2", "full-1", "tcp-1-list2"])


if __name__ == "__main__":
    unittest.main()
