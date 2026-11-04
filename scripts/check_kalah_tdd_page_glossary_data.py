#!/usr/bin/env python3
"""Check the Kalah TDD glossary and supporting data pages (#70): every report block of their sections kept in order,
report h3 as h2 and h4 as h3 with ids kept, tables in labelled regions, folds open, and the showcase short forms on
the glossary, each linked to its full entry.

Usage: check_kalah_tdd_page_glossary_data.py
"""
import functools
import importlib
import importlib.util
import re
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BASE = "/studies/kalah-tdd-study/"
PAGES = ("glossary", "data", "data/contrasts", "data/methods", "data/ratings", "data/runs")
# Items of the 6 pages and labels of the 5 data pages, from check_kalah_tdd_study.inventory at the snapshot sha.
ITEMS = 500
LABELS = 151
FOLDS = {"glossary": 1, "data": 1, "data/contrasts": 2, "data/methods": 1, "data/ratings": 0, "data/runs": 2}
MEASURES = BASE + "methodology/measures/"
MEASURED = ("Awards and E", "APFD-I", "Kendall distance", "M and M_io", "CQP and CQP accepted")
# Each showcase short form and the glossary row that defines it in full.
SHORT_FORMS = {"Functional mark": "Functional mark /15", "E": "Awards and E", "Cost to completion": "Cost to completion",
               "M": "M and M_io", "M_io": "M and M_io", "Alignment": "Awards and E",
               "C": "Relative spread and consistency score C", "PMD": "PMD and strict PMD compliance",
               "Weighted tokens": "Weighted tokens", "APFDc-H": "APFDc-H", "CQP": "CQP and CQP accepted",
               "Adjusted mutation": "Adjusted mutation score", "Planned contrast": "Planned contrast",
               "U": "Planned contrast", "Holm": "Planned contrast"}
HEAD = re.compile(r'<h([1-6])\b[^>]*(?<![\w-])id="([^"]+)"')
HREF = re.compile(r'href="([^"]*)"')


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


def showcase():
    return snap().files[kalah("snapshot").SHOWCASE]


def page(slug):
    return kalah("pagemap").BY_SLUG[slug]


@functools.cache
def rendered():
    """{slug: html} of one fresh build."""
    out = script("build_kalah_tdd_study").render_pages(snap())
    return {path.removesuffix("index.html").rstrip("/"): html for path, html in out.items()}


@functools.cache
def parsed(slug):
    return study().parse(rendered()[slug])


def main(slug):
    return parsed(slug).ids["main"]


@functools.cache
def cut(id):
    """The report section of this heading up to the next heading of its level or higher, or with a page of its own."""
    anchors = {a for p in kalah("pagemap").PAGES for a in p.anchors}
    heads = list(HEAD.finditer(report()))
    at = next(k for k, m in enumerate(heads) if m[2] == id)
    level, stop = int(heads[at][1]), report().index("</main>")
    end = next((m.start() for m in heads[at + 1:] if int(m[1]) <= level or m[2] in anchors), stop)
    return report()[heads[at].start():min(end, stop)]


def source(slug):
    return study().Tree("".join(cut(a) for a in page(slug).anchors)).root


def body():
    return kalah("pages.glossary_data")


def refused(test, files, *named):
    with test.assertRaises(ValueError) as caught:
        body().body(page("glossary"), snap()._replace(files={**snap().files, **files}), kalah("links").index(snap()))
    for name in named:
        test.assertIn(name, str(caught.exception))


def entry(name):
    """The report glossary row of this term."""
    return re.search(rf'<div class="entry"><p class="sub"><b>{re.escape(name)}</b>.*?</div>', cut("glossary"), re.S).group(0)


class GlossaryData(unittest.TestCase):
    def test_built_not_stub(self):
        for slug in PAGES:
            with self.subTest(slug):
                p = parsed(slug)
                self.assertFalse(p.stub, f"{slug} is a stub")
                levels = [study().heading(n) for n in p.root.iter() if study().heading(n)]
                self.assertEqual((levels.count(1), levels[0]), (1, 1))
                self.assertFalse([b for a, b in zip(levels, levels[1:]) if b > a + 1], f"heading skipped: {levels}")
                ids = [n.attrs["id"] for n in p.root.iter() if n.attrs.get("id")]
                self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
                sub = [(n.tag, n.attrs["id"]) for n in main(slug).iter() if n.tag in ("h2", "h3") and n.attrs.get("id")]
                self.assertEqual([i for t, i in sub if t == "h2"], list(page(slug).anchors))
                current = next(n for n in p.ids["toc"].iter() if n.attrs.get("aria-current") == "page")
                listed = [a.attrs["href"] for a in current.parent.iter() if a.tag == "a" and a is not current]
                self.assertEqual(listed, [f"{BASE}{slug}/#{i}" for _, i in sub])

    def test_coverage_counts(self):
        """Issue guard: coverage checks for 6 pages."""
        items, errors = study().inventory(snap().files)
        self.assertEqual(errors, [])
        items = [i for i in items if i.page in PAGES]
        self.assertEqual(len(items), ITEMS)
        errors, checked = study().coverage(items, rendered())
        self.assertEqual(errors, [])
        self.assertEqual(checked, ITEMS)

    def test_showcase_terms_on_glossary(self):
        terms = next(n for n in main("glossary").iter() if n.tag == "dl" and "terms" in n.classes())
        self.assertEqual(terms.closest("section").attrs.get("aria-labelledby"), "glossary")
        heads = [n for n in main("glossary").iter() if n.tag == "h3"]
        self.assertEqual([h.attrs.get("id") for h in heads], ["showcase-terms"])
        terms_html = re.search(r'<dl class="terms">(.*?)</dl>', kalah("snapshot").view(showcase(), "summary"), re.S)
        want = re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", terms_html.group(1), re.S)
        self.assertEqual(len(want), 15)
        squash = study().squash
        dts = [k for k in terms.elements() if k.tag == "dt"]
        self.assertEqual([squash(study().pair(dt)) for dt in dts],
                         [squash(study().Tree(f"<dt>{t}</dt><dd>{d}</dd>").root.text()) for t, d in want])
        self.assertEqual([k.tag for k in terms.elements()], ["dt", "dd"] * 15)
        for dt in dts:
            with self.subTest(study().spaced(dt)):
                links = [a for a in dt.iter() if a.tag == "a"]
                self.assertEqual(len(links), 1)
                href = links[0].attrs["href"]
                self.assertTrue(href.startswith("#term-"), href)
                row = parsed("glossary").ids[href[1:]]
                self.assertIn("entry", row.classes())
                name = study().spaced(next(b for b in row.iter() if b.tag == "b"))
                self.assertEqual(name, SHORT_FORMS[study().spaced(dt)])

    def test_terms_refuse(self):
        snapshot = kalah("snapshot")
        sc = showcase()
        self.assertIn("<dt>Holm</dt>", sc)
        refused(self, {snapshot.SHOWCASE: sc.replace("<dt>Holm</dt>", "<dt>Sidak</dt>")}, "Sidak")
        refused(self, {snapshot.REPORT: report().replace(entry("Planned contrast"), "")}, "Planned contrast")
        view = re.search(r'<main\b[^>]*id="classic".*?</main>', sc, re.S).group(0)
        refused(self, {snapshot.SHOWCASE: sc.replace(view, view.replace("<dt>U</dt>", "<dt>U value</dt>"))}, "classic")
        summary = re.search(r'<main\b[^>]*id="summary".*?</main>', sc, re.S).group(0)
        terms = re.search(r'<dl class="terms">.*?</dl>', summary, re.S).group(0)
        refused(self, {snapshot.SHOWCASE: sc.replace(summary, summary.replace(terms, terms * 2))}, "view summary holds 2 term lists")
        # Every view holds the list alike, so the stray p goes in each to reach the pair check.
        stray = terms.replace('<dl class="terms">', '<dl class="terms"><p>stray</p>')
        refused(self, {snapshot.SHOWCASE: sc.replace(terms, stray)}, "more than dt and dd pairs", "<p>stray</p>")
        row = entry("Planned contrast")
        refused(self, {snapshot.REPORT: report().replace(row, row.replace('<p class="sub">', "<p>", 1))},
                "no known form", "<p><b>Planned contrast</b>")
        self.assertTrue(body().body(page("glossary"), snap(), kalah("links").index(snap())))

    def test_measures_links(self):
        rows = [n for n in main("glossary").iter() if "entry" in n.classes()]
        self.assertEqual(len(rows), 35)
        squash = study().squash
        built = SCRIPTS.parent / MEASURES.lstrip("/") / "index.html"
        defined = study().parse(built.read_text(encoding="utf-8")).ids
        for row in rows:
            name = study().spaced(next(b for b in row.iter() if b.tag == "b"))
            linked = any(a.tag == "a" for a in row.iter())
            with self.subTest(name):
                self.assertEqual(linked, name in MEASURED)
                if linked:
                    # The link closes the row's card, after a div that holds the report row's text whole.
                    *text, after = row.elements()
                    self.assertEqual([(t.tag, squash(t.text())) for t in text], [("div", squash(study().Tree(entry(name)).root.text()))])
                    # The link goes to the dfn of the row's metric on the built measures page.
                    [href] = [a.attrs["href"] for a in after.iter() if a.tag == "a"]
                    page, _, frag = href.partition("#")
                    self.assertEqual(page, MEASURES)
                    self.assertEqual(getattr(defined.get(frag), "tag", None), "dfn", f"{href} names no dfn on measures")
                    self.assertEqual(" ".join(after.text().split()), "Its formula and inputs are on Measures.")
        refused(self, {kalah("snapshot").REPORT: report().replace(entry("Kendall distance"), "")}, "Kendall distance")

    def test_ids_kept(self):
        idx = kalah("links").index(snap())[kalah("snapshot").REPORT]
        homed = [(slug, frag) for slug, frag in idx.values() if slug in PAGES and frag]
        self.assertIn(("data/runs", "cap-hits-2"), homed)
        for slug, frag in homed:
            self.assertIn(frag, parsed(slug).ids, f"{slug} lacks #{frag}")
        for slug in PAGES:
            ids = parsed(slug).ids
            for n in source(slug).iter():
                if study().heading(n) and n.attrs.get("id"):
                    want = {"h2": "h2", "h3": "h2", "h4": "h3"}[n.tag]
                    self.assertEqual(ids[n.attrs["id"]].tag, want, f"{slug} #{n.attrs['id']}")

    def test_blocks_verbatim_in_order(self):
        squash = study().squash
        for slug in PAGES:
            with self.subTest(slug):
                want = [(n.tag, squash(n.text())) for n in source(slug).iter()
                        if n.tag in ("p", "li", "summary") or "entry" in n.classes()]
                have = iter((n.tag, squash(n.text())) for n in main(slug).iter())
                missing = [w for w in want if not any(w == h for h in have)]
                self.assertEqual(missing, [], "source blocks missing or out of order")

    def test_refuses_unknown_block(self):
        sec = cut("findings")
        for extra, said in (("<figure><p>x</p></figure>", "<figure"), ('<p class="lead">x</p>', '<p class="lead"'),
                            ("stray text", "stray"), ('<div class="shaped"><ul><li>x</li></ul></div>', "<ul")):
            with self.subTest(extra):
                with self.assertRaises(ValueError) as caught:
                    body().split("findings", sec + extra)
                self.assertIn("findings", str(caught.exception))
                self.assertIn(said, str(caught.exception))
        self.assertTrue(body().split("findings", sec))

    def test_tables_wrapped_folds_open(self):
        for slug in PAGES:
            with self.subTest(slug):
                labels = []
                for table in (n for n in main(slug).iter() if n.tag == "table"):
                    region = table.parent
                    self.assertEqual((region.tag, region.classes(), region.attrs.get("role"), region.attrs.get("tabindex")),
                                     ("div", ["table-scroll"], "region", "0"))
                    self.assertEqual(region.elements(), [table])
                    labels.append(region.attrs.get("aria-label"))
                    self.assertTrue(all(th.attrs.get("scope") for th in table.iter() if th.tag == "th"))
                self.assertTrue(all(labels))
                self.assertEqual([k for k, n in Counter(labels).items() if n > 1], [])
                folds = [n for n in main(slug).iter() if n.tag == "details"]
                self.assertEqual(len(folds), FOLDS[slug])
                self.assertTrue(all("open" in f.attrs for f in folds), "a fold is closed")
                self.assertTrue(all(study().ROWS.search(study().spaced(f.elements()[0])) for f in folds))

    def test_no_new_labels(self):
        total = 0
        for slug in PAGES[1:]:
            with self.subTest(slug):
                want = Counter(study().labels(source(slug)))
                self.assertEqual(Counter(study().labels(main(slug))), want)
                total += sum(want.values())
        self.assertEqual(total, LABELS)

    def test_links_rewritten(self):
        for slug in PAGES:
            hrefs = HREF.findall(rendered()[slug])
            with self.subTest(slug):
                self.assertEqual([h for h in hrefs if "report.html" in h or re.search(r"methods/[\w-]+\.html", h)], [])
        scope = next(n for n in main("glossary").iter() if n.tag == "section"
                     and n.attrs.get("aria-labelledby") == "scope-and-terms")
        self.assertEqual([a.attrs["href"] for a in scope.iter() if a.tag == "a"],
                         [f"{BASE}methodology/analysis/#limits", f"{BASE}experimental-design/#study-stage",
                          f"{BASE}experimental-design/#course-context"])
        self.assertIn(f"{MEASURES}#columns", [a.attrs.get("href") for a in main("data/methods").iter() if a.tag == "a"])
        designs = [a.attrs["href"] for a in main("data/contrasts").iter() if a.tag == "a"]
        self.assertEqual(designs, [f"{BASE}designs/{d[0]}/" for d in kalah("pagemap").DESIGNS])
        listed = [a.attrs["href"] for a in main("data").iter() if a.tag == "a"]
        self.assertEqual(listed, [f"{BASE}{slug}/" for slug in PAGES[1:]])


if __name__ == "__main__":
    unittest.main()
