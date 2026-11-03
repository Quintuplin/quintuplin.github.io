#!/usr/bin/env python3
"""Check the Kalah TDD measures page (#84): metric cards kept from the snapshot, dfns, formulas, doc versions,
refusals, Figure 4.1 and the column index.

Usage: check_kalah_tdd_page_measures.py
"""
import copy
import functools
import importlib
import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SLUG = "methodology/measures"
HEADINGS = ["measurement-pipeline", "columns", "tests", "static-analysis-and-mutation", "size-and-speed", "cost",
            "review-ratings", "combined-and-consistency", "records", "test-order-measures", "column-index"]
# The metrics plan.md names for this page, as dfn names.
PLAN_METRICS = {"functional mark", "hidden pass", "seen tests", "unseen pass", "acceptance pass", "strict pmd compliance",
                "strict pmd violations", "mutation score", "k/n", "adjusted mutation", "weighted tokens",
                "cost to completion", "e", "m", "m_io", "cqp", "cqp accepted", "apfd-i", "apfdc-h", "kendall distance",
                "relative spread", "consistency score c", "clear presentation", "explanatory language", "consistent code",
                "used content", "simple constructs", "minimal duplication", "modular structure", "problem alignment"}
ABSENT = "Module: not stated in the snapshot."
STRAY = ('<div class="entry"><p class="sub"><b>{}</b>. Source: stray.json. Tag: recomputed.</p>'
         '<p><b>Definition:</b> A row no family holds.</p></div>')
FILE = re.compile(r"[\w-]+\.(?:tsv|json|txt|csv|calls)\b")
NS = "{http://www.w3.org/2000/svg}"


@functools.cache
def module(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)


def kalah(name):
    return module(f"kalah_tdd.{name}")


def check():
    return module("check_kalah_tdd_study")


def flowcheck():
    return module("check_kalah_tdd_flow")


@functools.cache
def build():
    spec = importlib.util.spec_from_file_location("build_kalah_tdd_study", SCRIPTS / "build_kalah_tdd_study.py")
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out


@functools.cache
def snap():
    return kalah("snapshot").load()


def page_entry():
    return next(p for p in kalah("pagemap").PAGES if p.slug == SLUG)


def render(s):
    return build().render_page(page_entry(), s, kalah("links").index(s))


@functools.cache
def html():
    return render(snap())


@functools.cache
def page():
    parsed = check().parse(html())
    if parsed.stub:
        raise AssertionError(f"{SLUG} is still a stub")
    return parsed


def body(s):
    """The measures body on an in-memory snapshot, so a refusal raises."""
    return measures().body(page_entry(), s, kalah("links").index(s))


def measures():
    return kalah("pages.measures")


def index_section():
    return check().Tree(kalah("snapshot").section(html(), "column-index")).root


def report():
    return snap().files[kalah("snapshot").REPORT]


def entries(fragment):
    root = check().Tree(fragment).root
    return [n for n in root.iter() if "entry" in n.classes()]


def name_of(entry):
    return check().spaced(next(n for n in entry.iter() if n.tag == "b"))


def glossary():
    """{name: entry node} of the report glossary."""
    return {name_of(e): e for e in entries(kalah("snapshot").section(report(), "glossary"))}


def method_entries(files):
    """Distinct method page Column definitions entries, in first-seen order."""
    seen = {}
    for name, text in sorted(files.items()):
        if name.startswith(check().METHODS) and (i := text.find("<summary>Column definitions")) >= 0:
            for e in entries(text[i:text.index("</details>", i)]):
                seen.setdefault(check().squash(e.text()), e)
    return list(seen.values())


def source_entries():
    return entries(kalah("snapshot").section(report(), "columns")) + method_entries(snap().files) + list(glossary().values())


def cards():
    return [n for n in page().root.iter() if "entry" in n.classes() and n.closest(cls="entry") is None]


def first_p(node):
    return next(n for n in node.iter() if n.tag == "p")


def subs(card, prefix):
    return [n for n in card.iter() if n.tag == "p" and "sub" in n.classes() and check().spaced(n).startswith(prefix)]


def tagged_texts(root):
    """{(tag, squashed text)} for every element under root."""
    text = {}
    check().squashed(root, text)
    return {(n.tag, text[id(n)]) for n in root.iter()}


def lead():
    main = html()[html().index('<main id="main">'):]
    return re.sub(r"<[^>]+>", " ", main[:main.index("<h2")])


def runs_named(s, text):
    """Each facts run named in text, in first-mention order; a run inside a longer run name is no mention."""
    names = sorted(s.facts["runs"], key=len, reverse=True)
    found = re.findall(r"(?<![\w/-])(" + "|".join(map(re.escape, names)) + r")(?![\w/-])", text)
    return list(dict.fromkeys(found))


def f4_svg():
    fig = re.search(r'<figure id="f4".*?</figure>', html(), re.S).group(0)
    return fig, ET.fromstring(re.search(r"<svg.*?</svg>", fig, re.S).group(0))


def with_report(s, old, new):
    files = dict(s.files)
    files[kalah("snapshot").REPORT] = files[kalah("snapshot").REPORT].replace(old, new, 1)
    return s._replace(files=files)


def source_field(entry):
    m = re.search(r"Source: (.*?)\. Tag:", check().spaced(first_p(entry)))
    return m.group(1) if m else ""


class Measures(unittest.TestCase):
    def test_built_not_stub(self):
        self.assertFalse(check().parse(html()).stub)
        self.assertEqual(len(re.findall(r"<h1\b", html())), 1)
        self.assertEqual(re.findall(r'<h[23] id="([^"]+)"', html().split('<main id="main">')[1]), HEADINGS)

    def test_coverage_counts_measures(self):
        items, errors = check().inventory(snap().files)
        mine = [i for i in items if i.page == SLUG]
        self.assertEqual(len(mine), 33)
        found, checked = check().coverage(mine, {SLUG: html()})
        self.assertEqual(found, [])
        self.assertEqual(checked, len(mine))

    def test_method_rows_kept(self):
        items, _ = check().inventory(snap().files)
        rows = {i.key: i.shown for i in items if i.page == check().SHARED and i.source.startswith(check().METHODS)}
        self.assertEqual(len(rows), 12)
        for key in rows:
            self.assertGreaterEqual(page().texts[key], 1, rows[key])
        key = next(iter(rows))
        root = check().Tree(html()).root
        text = {}
        check().squashed(root, text)
        node = next(n for n in root.iter() if text[id(n)] == key and n.parent and text[id(n.parent)] != key)
        node.parent.kids.remove(node)
        dropped = check().Page(False, check().texts(list(root.iter()), root), {}, Counter(), root)
        self.assertIsNotNone(check().lacks((("row", key, rows[key]), 1), dropped))

    def test_plan_metrics_have_dfn(self):
        self.assertLessEqual(PLAN_METRICS, check().dfn_names(page()))
        ids = [n.attrs.get("id") for n in page().root.iter() if n.tag == "dfn"]
        self.assertNotIn(None, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([i for i in ids if page().ids[i].tag != "dfn"], [])

    def test_columns_anchor_and_intro(self):
        self.assertEqual(page().ids["columns"].tag, "h2")
        intro = re.search(r"<p>.*?</p>", kalah("snapshot").section(report(), "columns"), re.S).group(0)
        self.assertIn(intro, kalah("snapshot").section(html(), "columns"))
        self.assertEqual(kalah("links").index(snap())[kalah("snapshot").REPORT]["columns"], (SLUG, "columns"))

    def test_keeps_all_source_text(self):
        have = tagged_texts(page().root)
        section = check().Tree(kalah("snapshot").section(report(), "columns")).root
        chunks = tagged_texts(section)
        wanted = [(t, s) for t, s in chunks if t in ("p", "li", "dt", "dd") and s]
        self.assertGreater(len(wanted), 64)
        self.assertEqual([w for w in wanted if w not in have], [])

    def test_tags_from_source(self):
        lines = {check().squash(first_p(e).text()): e for e in source_entries()}
        found = cards()
        self.assertGreaterEqual(len(found), 32 + 10 + 4)
        for card in found:
            sub = first_p(card)
            with self.subTest(check().spaced(sub)):
                self.assertIn(check().squash(sub.text()), lines)
                kind = re.search(r"Tag: (\w+)\.", check().spaced(sub)).group(1)
                pills = [check().spaced(n) for n in sub.iter() if "tag" in n.classes()]
                self.assertEqual(pills, [kind])
                if "Source:" not in check().spaced(sub):
                    self.assertEqual(kind, "verified")
        rows = {name_of(e): e for e in entries(kalah("snapshot").section(report(), "columns"))}
        for tr in (n for n in index_section().iter() if n.tag == "tr" and n.closest("tbody")):
            cells = [check().spaced(c) for c in tr.elements()]
            sub = check().spaced(first_p(rows[cells[0]]))
            with self.subTest(cells[0]):
                self.assertIn(f"Source: {cells[1]}. Tag: {cells[2]}.", sub)

    def test_module_named_or_absent(self):
        rows = glossary()
        for card in cards():
            inner = card.elements()[0]
            source = check().spaced(inner)
            lines = subs(card, "Module:")
            with self.subTest(check().spaced(first_p(card))):
                self.assertEqual(len(lines), 1)
                line = lines[0]
                cited = [check().spaced(n) for n in line.iter() if n.tag == "i"]
                text = " ".join([source] + [check().spaced(rows[c]) for c in cited])
                if check().spaced(line) == ABSENT:
                    self.assertIsNone(re.search(r"\S+\.py\b", source))
                else:
                    named = [check().spaced(n) for n in line.iter() if n.tag == "code"]
                    self.assertTrue(named)
                    for m in named:
                        self.assertIn(m, text)

    def test_weight_text_kept(self):
        weight_text = snap().facts["pipeline"]["weight_text"]
        card = page().ids["weighted-tokens"].closest(cls="entry")
        self.assertIn(weight_text, check().spaced(card))
        want = {k: v for k, v in re.findall(r"(input|cache creation|cache read|output) ([\d.]+)", weight_text)}
        self.assertEqual(len(want), 4)

        def weights(root_html):
            card = check().parse(root_html).ids["weighted-tokens"].closest(cls="entry")
            code = check().spaced(next(n for n in subs(card, "Formula:")[0].iter() if n.tag == "code"))
            return {k.strip(): v for v, k in re.findall(r"([\d.]+) × ([a-z ]+?)(?= \+|$)", code)}

        self.assertEqual(weights(html()), want)
        s = with_report(snap(), "output 5 per token", "output 6 per token")
        facts = copy.deepcopy(s.facts)
        facts["pipeline"]["weight_text"] = weight_text.replace("output 5", "output 6")
        self.assertEqual(weights(render(s._replace(facts=facts)))["output"], "6")

    def test_formula_numbers_from_source(self):
        m_row = check().spaced(next(e for e in entries(kalah("snapshot").section(report(), "columns")) if name_of(e) == "M"))
        doc = next(f["doc"] for f in snap().facts["analysis"]["functions"] if f["name"] == "error_count")
        cited = {"weighted-tokens": snap().facts["pipeline"]["weight_text"], "m": m_row, "e": doc}
        found = {}
        for card in cards():
            for line in subs(card, "Formula:"):
                dfn = next(n for n in card.iter() if n.tag == "dfn")
                code = next(n for n in line.iter() if n.tag == "code")
                found[dfn.attrs["id"]] = code
        self.assertEqual(set(found), set(cited))
        for key, code in found.items():
            with self.subTest(key):
                for number in re.findall(r"\d+(?:\.\d+)?", check().spaced(code)):
                    self.assertRegex(cited[key], rf"(?<![\d.]){re.escape(number)}(?![\d.])")
                hrefs = [n.attrs["href"] for n in code.iter() if n.tag == "a"]
                self.assertTrue(hrefs)
                for href in hrefs:
                    self.assertEqual(page().ids[href.removeprefix("#")].tag, "dfn", href)

    def test_doc_versions_cover_named_runs(self):
        text = lead()
        self.assertIn(f"methods doc {snap().doc}", " ".join(text.split()))
        main = html()[html().index('<main id="main">'):]
        rest = runs_named(snap(), re.sub(r"<[^>]+>", " ", main[main.index("<h2"):]))
        self.assertTrue(rest)
        listed = re.findall(r"(\S+) ([0-9a-f]{8})\b", text.split("doc versions")[1])
        self.assertEqual([r for r, _ in listed], runs_named(snap(), text.split("doc versions")[1]))
        self.assertEqual(sorted(r for r, _ in listed), sorted(set(rest + runs_named(snap(), text))))
        for run, doc in listed:
            self.assertEqual(doc, kalah("snapshot").run_doc(snap(), run), run)
        self.assertEqual(measures().named_runs(snap(), "tcp-1-list2 and rep-2/rebuild"), ["tcp-1-list2", "rep-2/rebuild"])

    def test_refuses_unassigned_row(self):
        at = report().index("</div></details>", report().index("<summary>Column definitions"))
        s = snap()._replace(files={**snap().files, kalah("snapshot").REPORT:
                                   report()[:at] + STRAY.format("Stray column") + report()[at:]})
        self.assertIn("Stray column", kalah("snapshot").section(s.files[kalah("snapshot").REPORT], "columns"))
        with self.assertRaisesRegex(ValueError, "Stray column"):
            body(s)
        name = next(n for n in sorted(snap().files) if n.startswith(check().METHODS)
                    and "<summary>Column definitions" in snap().files[n])
        files = dict(snap().files)
        at = files[name].index("</div></details>", files[name].index("<summary>Column definitions"))
        files[name] = files[name][:at] + STRAY.format("Stray method row") + files[name][at:]
        with self.assertRaisesRegex(ValueError, "Stray method row"):
            body(snap()._replace(files=files))

    def test_refuses_missing_source(self):
        kendall = glossary()["Kendall distance"]
        start = report().index("<b>Kendall distance</b>")
        start = report().rindex('<div class="entry">', 0, start)
        end = report().index("</div>", start) + len("</div>")
        self.assertIn("Kendall", report()[start:end])
        self.assertTrue(kendall)
        with self.assertRaisesRegex(ValueError, "Kendall distance"):
            body(with_report(snap(), report()[start:end], ""))
        facts = copy.deepcopy(snap().facts)
        facts["analysis"]["functions"] = [f for f in facts["analysis"]["functions"] if f["name"] != "error_count"]
        with self.assertRaisesRegex(ValueError, "error_count"):
            body(snap()._replace(facts=facts))
        facts = copy.deepcopy(snap().facts)
        facts["pipeline"]["weight_text"] = "Weighted tokens count every token alike."
        with self.assertRaisesRegex(ValueError, "weight_text"):
            body(snap()._replace(facts=facts))

    def test_pipeline_text_version_matches(self):
        fig, root = f4_svg()
        nodes = flowcheck().node_boxes(root)
        items = re.findall(r"<li>", re.search(r'<details id="f4-data">.*?</details>', fig, re.S).group(0))
        self.assertEqual(len(nodes), len(items))
        self.assertEqual(len(nodes), len(measures().pipeline(snap())[0]))
        self.assertIsNotNone(root.find(NS + "title"))
        self.assertIsNotNone(root.find(NS + "desc"))
        ids = [e.get("id") for e in root.iter() if e.get("id")]
        self.assertTrue(ids)
        self.assertEqual([i for i in ids if not i.startswith("f4-")], [])

    def test_pipeline_from_sources(self):
        nodes, edges = measures().pipeline(snap())
        sources = {name_of(e): source_field(e) for e in source_entries()}
        for n in nodes:
            fields = " ".join(sources[c] for c in measures().LANES[n.lane])
            for name in FILE.findall(f"{n.label} {n.note}"):
                with self.subTest(node=n.id, file=name):
                    self.assertIn(name, fields)
        doc = {f["name"]: f["doc"] for f in snap().facts["analysis"]["functions"]}
        for target, (kind, name, inputs) in measures().COMPOSITES.items():
            sentence = doc[name] if kind == "function" else check().spaced(glossary()[name])
            self.assertEqual({e.src for e in edges if e.dst == target}, set(inputs), target)
            for terms in inputs.values():
                for term in terms:
                    self.assertIn(term, sentence, target)
        with self.assertRaisesRegex(ValueError, r"pmd\.txt"):
            body(snap()._replace(files={**snap().files, kalah("snapshot").REPORT: report().replace("pmd.txt", "lint.txt")}))

    def test_pipeline_routes_and_limits(self):
        nodes, edges = measures().pipeline(snap())
        cols = kalah("figures.flow").COLS
        self.assertEqual([n.id for n in nodes if n.col is None or not 0 <= n.col < cols], [])
        self.assertEqual([e.label for e in edges if len(e.label) > 10], [])
        _, root = f4_svg()
        f = flowcheck()
        boxes = f.node_boxes(root)
        for path in (p for p in root.iter(NS + "path") if p.get("class") == "edge"):
            pts = f.points(path.get("d"))
            for a, b in zip(pts, pts[1:]):
                self.assertEqual([box for box in boxes if f.crosses(a, b, box)], [], path.get("d"))
        labels = f.label_boxes(root)
        for i, (s, box) in enumerate(labels):
            self.assertFalse(any(f.overlap(box, n) for n in boxes), s)
            self.assertFalse(any(f.overlap(box, o) for _, o in labels[i + 1:]), s)

    def test_figure_wrapped_and_index(self):
        fig = page().ids["f4"]
        self.assertEqual(check().spaced(next(n for n in fig.iter() if "fig-n" in n.classes())), "Figure 4.1")
        self.assertTrue(any(n.tag == "figcaption" for n in fig.iter()))
        self.assertEqual(page().ids["f4-data"].tag, "details")
        data = next(n for n in fig.iter() if n.tag == "a" and check().spaced(n) == "Data")
        self.assertIn(data.attrs["href"].removeprefix("#"), page().ids)
        diagram = next(n for n in fig.iter() if "diagram" in n.classes())
        self.assertEqual((diagram.attrs.get("role"), diagram.attrs.get("tabindex")), ("region", "0"))
        summary = next(n for n in index_section().iter() if n.tag == "summary")
        source = re.search(r"<summary>(Column definitions[^<]*)</summary>", report()).group(1)
        self.assertEqual(check().spaced(summary), source)
        n = int(re.search(r"(\d+) rows", source).group(1))
        self.assertEqual(len([r for r in summary.parent.iter() if r.tag == "tr" and r.closest("tbody")]), n)
        for table in (t for t in page().root.iter() if t.tag == "table"):
            region = table.parent
            self.assertEqual((region.attrs.get("role"), bool(region.attrs.get("aria-label"))), ("region", True))
            for th in (c for c in table.iter() if c.tag == "th"):
                self.assertEqual(th.attrs.get("scope"), "col" if th.closest("thead") else "row")
            self.assertEqual([a for td in table.iter() if td.tag == "td" for a in td.iter() if a.tag == "a"], [])


if __name__ == "__main__":
    unittest.main()
