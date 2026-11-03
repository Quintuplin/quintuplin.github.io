#!/usr/bin/env python3
"""Check the Kalah TDD analysis and validity page (#66): report Limits kept whole, code-derived gaps from facts.json,
award rules and code docstrings verbatim, every test sentence quoted from its report section, and Figures F6 and F7
built from the facts with clear routes.

Usage: check_kalah_tdd_page_analysis.py
"""
import copy
import functools
import importlib
import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SLUG = "methodology/analysis"
BASE = "/studies/kalah-tdd-study/"
HERE = BASE + SLUG + "/"
NONE = "not stated in the snapshot"
HEADINGS = [("h2", "award-scoring"), ("h3", "award-rules"), ("h3", "awards-code"), ("h2", "statistical-tests"),
            ("h3", "test-use"), ("h3", "stats-functions"), ("h2", "threats"), ("h3", "limits"), ("h3", "record-gaps")]
GAPS = ("gap-rebuild", "gap-docs", "gap-harness", "gap-code-limits")


@functools.cache
def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kalah(name):
    script("build_kalah_tdd_study")
    return importlib.import_module(f"kalah_tdd.{name}")


def analysis():
    return kalah("pages.analysis")


@functools.cache
def snap():
    return kalah("snapshot").load()


@functools.cache
def idx():
    return kalah("links").index(snap())


def page():
    return kalah("pagemap").BY_SLUG[SLUG]


def render(s=None):
    return script("build_kalah_tdd_study").render_page(page(), s or snap(), idx())


@functools.cache
def html():
    return render()


@functools.cache
def parsed():
    return script("check_kalah_tdd_study").parse(html())


def root():
    return parsed().root


def report():
    return snap().files[kalah("snapshot").REPORT]


def facts():
    return snap().facts


def spaced(node):
    return " ".join(node.text(" ").split())


def squash(text):
    return "".join(text.split())


def plain(fragment):
    """Text of report HTML with tags dropped, as the quoted sentences read."""
    return " ".join(unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def rows(label):
    """Cell texts of each body row of the table in the scroll region with this aria-label."""
    region = next((n for n in root().iter() if n.attrs.get("role") == "region" and n.attrs.get("aria-label") == label), None)
    if region is None:
        raise AssertionError(f"no table region labelled {label!r}")
    return [[spaced(td) for td in tr.elements() if td.tag == "td"] for tr in region.iter()
            if tr.tag == "tr" and any(td.tag == "td" for td in tr.elements())]


def by_id(id):
    return parsed().ids[id]


def mutated(change):
    """The snapshot with a deep copy of its facts and files changed in memory."""
    s = snap()._replace(facts=copy.deepcopy(snap().facts), files=dict(snap().files))
    change(s)
    return s


def refuses(case, change, name):
    with case.subTest(name), case.assertRaisesRegex(ValueError, re.escape(name)):
        analysis().body(page(), mutated(change), idx())


def award(s, title):
    return next(a for a in s.facts["analysis"]["awards"] if a["title"] == title)


def doc(s, group, name):
    return next(f for f in s.facts["analysis"][group] if f["name"] == name)


def has_run(text, run):
    return re.search(rf"(?<![\w/-]){re.escape(run)}(?![\w/-])", text) is not None


def svg(prefix):
    m = re.search(rf'<svg\b[^>]*aria-labelledby="{prefix}-title {prefix}-desc".*?</svg>', html(), re.S)
    if not m:
        raise AssertionError(f"no {prefix} flowchart on the page")
    return m.group(0), ET.fromstring(m.group(0))


def figure(n):
    return next(f for f in root().iter() if f.tag == "figure" and f.attrs.get("aria-label", "").startswith(f"Figure {n}:"))


def segments(svg_root):
    flow = script("check_kalah_tdd_flow")
    out = []
    for k, p in enumerate(q for q in svg_root.iter(flow.NS + "path") if q.get("class") in ("edge", "loop")):
        pts = flow.points(p.get("d"))
        out += [(k, a, b) for a, b in zip(pts, pts[1:])]
    return out


def cross(s, t):
    """Whether a horizontal and a vertical segment meet inside both, away from their ends."""
    (a, b), (c, d) = s, t
    if a[1] == b[1] and c[0] == d[0]:
        return min(a[0], b[0]) < c[0] < max(a[0], b[0]) and min(c[1], d[1]) < a[1] < max(c[1], d[1])
    if a[0] == b[0] and c[1] == d[1]:
        return cross(t, s)
    return False


def charts():
    return {"f6": analysis().awards_flow(snap()), "f7": analysis().test_flow(snap())}


class Analysis(unittest.TestCase):
    def test_built_not_stub(self):
        self.assertFalse(parsed().stub)
        nodes = list(root().iter())
        self.assertEqual(sum(n.tag == "h1" for n in nodes), 1)
        main = next(n for n in nodes if n.tag == "main")
        heads = [(n.tag, n.attrs.get("id")) for n in main.iter() if n.tag in ("h2", "h3") and n.attrs.get("id")]
        self.assertEqual(heads, HEADINGS)
        ids = re.findall(r'(?<![\w-])id="([^"]+)"', html())
        self.assertEqual(len(ids), len(set(ids)))
        toc = by_id("toc")
        hrefs = {a.attrs.get("href") for a in toc.iter() if a.tag == "a"}
        for id in ("award-scoring", "statistical-tests", "threats"):
            self.assertIn(HERE + "#" + id, hrefs)

    def test_coverage_counts_analysis(self):
        study = script("check_kalah_tdd_study")
        items, _ = study.inventory(snap().files)
        mine = [i for i in items if i.page == SLUG]
        self.assertEqual(len(mine), 20)
        errors, checked = study.coverage(mine, {SLUG: html()})
        self.assertEqual(errors, [])
        self.assertEqual(checked, len(mine))

    def test_limits_verbatim(self):
        section = kalah("snapshot").section(report(), "limits")
        entries = re.findall(r'<div class="entry">(.*?)</div>', section, re.S)
        self.assertEqual(len(entries), 20)
        texts = parsed().texts
        self.assertGreaterEqual(texts[squash("What this study cannot show, stated once for the whole page.")], 1)
        for e in entries:
            with self.subTest(e[:40]):
                self.assertGreaterEqual(texts[squash(plain(e))], 1)
        self.assertEqual(by_id("limits").tag, "h3")
        self.assertEqual(idx()[kalah("snapshot").REPORT]["limits"], (SLUG, "limits"))

    def test_record_gaps_from_facts(self):
        runs = facts()["runs"]
        rebuild, rep2 = runs["rep-2/rebuild"], runs["rep-2"]
        text = spaced(by_id("gap-rebuild"))
        for wave in rebuild["waves"]:
            for build in wave:
                self.assertIn(build, text)
        self.assertIn({m["method"] for m in rebuild["methods"].values()}.pop(), text)
        for sha in (rebuild["harness"]["commit"][:7], rep2["harness"]["commit"][:7], rebuild["harness_delta"]["sha256"][:8]):
            self.assertIn(sha, text)
        self.assertIn(rebuild["harness"]["claude_version"].split()[0], text)
        docs = spaced(by_id("gap-docs"))
        sentences = re.split(r"(?<=\.) ", docs)
        for run in runs:
            with self.subTest(run):
                holding = [s for s in sentences if has_run(s, run)]
                self.assertEqual(len(holding), 1, holding)
                self.assertTrue(holding[0].startswith(kalah("snapshot").run_doc(snap(), run)), holding[0])
        mark = next(s for s in sentences if s.startswith(snap().doc))
        self.assertIn("these pages quote", mark)
        harness = spaced(by_id("gap-harness"))
        self.assertEqual({r for r in runs if has_run(harness, r)},
                         {r for r, v in runs.items() if not v.get("harness", {}).get("commit")})
        for gap in GAPS:
            with self.subTest(gap):
                tags = [spaced(t) for t in by_id(gap).iter() if "tag" in t.classes()]
                self.assertEqual(tags, ["recomputed"])

    def test_refuses_record_shape(self):
        def two_methods(s):
            next(iter(s.facts["runs"]["rep-2/rebuild"]["methods"].values()))["method"] = "Classic greedy TDD"

        def same_commit(s):
            s.facts["runs"]["rep-2/rebuild"]["harness"]["commit"] = s.facts["runs"]["rep-2"]["harness"]["commit"]

        def no_harness(s):
            del s.facts["runs"]["rep-2/rebuild"]["harness"]

        def no_limit(s):
            f = doc(s, "stats", "mann_whitney_exact")
            f["doc"] = f["doc"].replace(" The C(n, len(xs)) splits suit small samples only.", "")

        for change, name in ((two_methods, "rep-2/rebuild"), (same_commit, "rep-2/rebuild"), (no_harness, "rep-2/rebuild"),
                             (no_limit, "mann_whitney_exact")):
            refuses(self, change, name)

    def test_award_rules_from_facts(self):
        got = rows("Award rules")
        awards = facts()["analysis"]["awards"]
        self.assertEqual([r[0] for r in got], [a["title"] for a in awards])
        counted = set(analysis().COUNTED.values())
        self.assertEqual(set(analysis().COUNTED), {c["name"] for c in facts()["analysis"]["criteria"]})
        for row, a in zip(got, awards):
            with self.subTest(a["title"]):
                self.assertEqual(row[1], a["rule"].replace("{limit}", "").strip())
                self.assertEqual(row[2] == "Yes", a["title"] in counted)
        after = [a.attrs.get("href") for p in by_id("award-scoring").closest("section").iter() if p.tag == "p"
                 and "consistency limit" in spaced(p) for a in p.iter() if a.tag == "a"]
        self.assertEqual(after, [BASE])

    def test_refuses_unmapped_award(self):
        def criterion(s):
            s.facts["analysis"]["criteria"].append({"name": "fastest", "doc": None, "returns": "record['wall']"})

        def renamed(s):
            award(s, "Fewest errors")["title"] = "Fewer errors"

        def second(s):
            award(s, "Cheapest")["rule"] += " {limit}"

        def absent(s):
            a = award(s, "Most consistent design")
            a["rule"] = a["rule"].replace(" {limit}", "")

        for change, name in ((criterion, "fastest"), (renamed, "Fewer errors"), (second, "Cheapest"),
                             (absent, "Most consistent design")):
            refuses(self, change, name)

    def test_code_tables_verbatim(self):
        a = facts()["analysis"]
        for label, group, absent in (("awards.py functions", "functions", "No docstring in awards.py."),
                                     ("stats.py functions", "stats", "No docstring in stats.py.")):
            with self.subTest(label):
                self.assertEqual(rows(label), [[f["name"], f["doc"] or absent] for f in a[group]])
                for f in a[group]:
                    if f["doc"]:
                        self.assertEqual(parsed().texts[squash(f["doc"])], 1, f["name"])
        consts = {r[0]: r[1] for r in rows("awards.py constants")}
        for name, value in a["constants"].items():
            self.assertEqual(consts[name], ", ".join(value) if isinstance(value, list) else str(value))

    def test_test_use_rows_cite_source(self):
        got = rows("Where each test is used")
        use = analysis().TEST_USE
        self.assertEqual(len(got), len(use))
        names = {f["name"] for f in facts()["analysis"]["stats"]}
        for row, u in zip(got, use):
            question, data, test, function, correction, reported, sentence = row
            with self.subTest(question):
                self.assertEqual(question, u.question)
                self.assertIn(sentence, plain(kalah("snapshot").section(report(), u.section)))
                for words in u.words:
                    self.assertIn(words, test)
                    self.assertIn(words, sentence)
                self.assertTrue(function == NONE or set(function.split(", ")) <= names, function)
                self.assertEqual(reported, kalah("pagemap").BY_SLUG[u.reported].title)

        def reworded(s):
            s.files[kalah("snapshot").REPORT] = report().replace("seeded permutation chi-square", "seeded shuffle chi-square")

        refuses(self, reworded, "survey-full-1")

    def test_f6_from_facts(self):
        nodes, _, _ = analysis().awards_flow(snap())
        words = " ".join(n.label + " " + n.note for n in nodes)
        a = facts()["analysis"]
        for name in [c["name"] for c in a["criteria"]] + a["constants"]["MEDALS"]:
            self.assertIn(name, words)
        self.assertRegex(words, rf"\btop {a['constants']['TOP']}\b")
        fig = figure("5.1")
        self.assertEqual(sum(li.tag == "li" for li in fig.iter() if li.closest("details")), len(nodes))
        out, svg_root = svg("f6")
        ns = script("check_kalah_tdd_flow").NS
        self.assertTrue(svg_root.find(ns + "title").text and svg_root.find(ns + "desc").text)
        ids = re.findall(r'\bid="([^"]*)"', out)
        self.assertTrue(ids)
        self.assertEqual([i for i in ids if not i.startswith("f6-")], [])

    def test_f7_from_rows(self):
        nodes, _, _ = analysis().test_flow(snap())
        drawn = [u for u in analysis().TEST_USE if u.functions]
        self.assertEqual(list(dict.fromkeys(n.lane for n in nodes)), [u.lane for u in drawn])
        names = {f["name"] for f in facts()["analysis"]["stats"]}
        functions = [n for n in nodes if n.col == 1]
        self.assertEqual(len(functions), len(drawn))
        for n, u in zip(functions, drawn):
            self.assertEqual(n.label.split(", "), list(u.functions))
            self.assertLessEqual(set(u.functions), names)
        out, _ = svg("f7")
        self.assertEqual([i for i in re.findall(r'\bid="([^"]*)"', out) if not i.startswith("f7-")], [])

    def test_flows_routes_and_limits(self):
        flow, cols = script("check_kalah_tdd_flow"), kalah("figures.flow").COLS
        for prefix, (nodes, edges, loops) in charts().items():
            with self.subTest(prefix):
                _, svg_root = svg(prefix)
                self.assertTrue(all(n.col is not None and n.col < cols for n in nodes))
                self.assertTrue(all(len(e.label) <= 10 for e in edges))
                boxes = dict(zip([n.id for n in nodes], flow.node_boxes(svg_root)))
                ends = [(e.src, e.dst) for e in edges] + [(lp.node, lp.back_to or lp.node) for lp in loops]
                paths = [p for p in svg_root.iter(flow.NS + "path") if p.get("class") in ("edge", "loop")]
                self.assertEqual(len(paths), len(ends))
                for (src, dst), p in zip(ends, paths):
                    pts = flow.points(p.get("d"))
                    self.assertTrue(flow.on_edge(pts[0], boxes[src]) and flow.on_edge(pts[-1], boxes[dst]), p.get("d"))
                    self.assertEqual([i for a, b in zip(pts, pts[1:]) for i, box in boxes.items() if flow.crosses(a, b, box)], [])
                segs = segments(svg_root)
                self.assertEqual([(s, t) for i, s in enumerate(segs) for t in segs[i + 1:]
                                  if s[0] != t[0] and cross(s[1:], t[1:])], [])
                labels = flow.label_boxes(svg_root)
                for s, box in labels:
                    self.assertEqual([n for n in boxes.values() if flow.overlap(box, n)], [], s)
                    self.assertEqual([seg for seg in segs if flow.crosses(seg[1], seg[2], box)], [], s)
                self.assertEqual([(s, t) for i, (s, a) in enumerate(labels) for t, b in labels[i + 1:] if flow.overlap(a, b)], [])

    def test_figures_wrapped(self):
        ids = parsed().ids
        for n in ("5.1", "5.2"):
            with self.subTest(n):
                fig = figure(n)
                self.assertTrue(any(k.tag == "figcaption" for k in fig.iter()))
                summaries = [spaced(s) for s in fig.iter() if s.tag == "summary"]
                self.assertTrue(any(s.startswith("Text version: ") for s in summaries), summaries)
                data = [a.attrs["href"] for a in fig.iter() if a.tag == "a" and spaced(a) == "Data"]
                self.assertEqual(len(data), 1)
                self.assertIn(data[0].removeprefix("#"), ids)
        main = next(n for n in root().iter() if n.tag == "main")
        tables = [t for t in main.iter() if t.tag == "table"]
        self.assertTrue(tables)
        for t in tables:
            region = t.closest(cls="table-scroll")
            self.assertTrue(region is not None and region.attrs.get("role") == "region" and region.attrs.get("aria-label"))
            self.assertTrue(all(th.attrs.get("scope") in ("col", "row") for th in t.iter() if th.tag == "th"))
        self.assertEqual([td for td in main.iter() if td.tag == "a" and td.closest("td")], [])

    def test_no_metric_redefinition(self):
        self.assertNotIn("<dfn", html())
        main = next(n for n in root().iter() if n.tag == "main")
        lead = next(n for n in main.iter() if n.tag == "p")
        hrefs = {a.attrs.get("href") for a in lead.iter() if a.tag == "a"}
        self.assertLessEqual({BASE + "methodology/measures/", BASE + "glossary/"}, hrefs)
        for href in re.findall(r'href="([^"]*)"', html()):
            if href.startswith(BASE) and not href.startswith(HERE + "#"):
                self.assertNotIn("#", href)

    def test_deterministic(self):
        self.assertEqual(analysis().body(page(), snap(), idx()), analysis().body(page(), snap(), idx()))
        self.assertEqual(render().encode(), render().encode())


if __name__ == "__main__":
    unittest.main()
