#!/usr/bin/env python3
"""Check the Kalah TDD experimental design page (#63): its report items, spec, runs, collect steps and figures 2.1 to 2.3.

Usage: check_kalah_tdd_page_design.py
"""
import functools
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import check_kalah_tdd_study as study  # noqa: E402
from check_kalah_tdd_flow import NS, crosses, label_boxes, node_boxes, overlap, points  # noqa: E402
from kalah_tdd import snapshot  # noqa: E402

SLUG = "experimental-design"
PAGE = SCRIPTS.parent / "studies/kalah-tdd-study" / SLUG / "index.html"
CSS = SCRIPTS.parent / "studies/kalah-tdd-study/study.css"
FIGURE = re.compile(r'<figure id="([^"]+)".*?</figure>', re.S)
SVG = re.compile(r"<svg\b.*?</svg>", re.S)


@functools.cache
def html():
    return PAGE.read_text(encoding="utf-8")


@functools.cache
def page():
    return study.parse(html())


@functools.cache
def snap():
    return snapshot.load()


def facts():
    return snap().facts


def main_html():
    return html().split('<main id="main">', 1)[-1].split("</main>", 1)[0]


def main_text():
    return study.squash(study.Tree(main_html()).root.text())


def figures():
    """{figure id: figure html} in page order."""
    return {m.group(1): m.group(0) for m in FIGURE.finditer(main_html())}


def table(id):
    """(header cells, body rows of cell texts) of the table with this id."""
    node = page().ids.get(id)
    if node is None or node.tag != "table":
        raise AssertionError(f"no table with id {id}")
    head = [study.spaced(c) for c in node.iter() if c.tag == "th" and c.closest("thead")]
    rows = [[study.spaced(c) for c in tr.elements() if c.tag in ("th", "td")]
            for tr in node.iter() if tr.tag == "tr" and not tr.closest("thead")]
    return head, rows


@functools.cache
def css_rules():
    """(selector, declarations) of each study.css rule, the rules inside @media blocks included."""
    return re.findall(r"([^{}]+)\{([^{}]*)\}", CSS.read_text(encoding="utf-8"))


def svg_root(fig):
    return ET.fromstring(SVG.search(fig).group(0))


def flows():
    return {id: fig for id, fig in figures().items() if re.search(r'<svg\b[^>]*class="flow"', fig)}


def text_items(fig):
    root = ET.fromstring(re.search(r"<details\b.*?</details>", fig, re.S).group(0))
    return ["".join(li.itertext()) for li in root.iter("li")]


def node_labels(root):
    """Each node's label, its wrapped lines joined, in node order."""
    kids, out = list(root), []
    for rect, text in zip(kids, kids[1:]):
        if rect.tag == NS + "rect" and rect.get("class") == "node":
            out.append(" ".join(t.text for t in text.iter(NS + "tspan")))
    return out


def paths(root, cls):
    """(corner points, the label text after the path or None) for each path of the class."""
    kids = list(root) + [None]
    return [(points(p.get("d")), "".join(t.itertext()) if t is not None and t.tag == NS + "text" else None)
            for p, t in zip(kids, kids[1:]) if p.tag == NS + "path" and p.get("class") == cls]


def marks(root):
    """{title text: (cx, cy)} for each svg element that holds its own title, the svg's own title aside."""
    return {"".join(t.itertext()): (el.get("cx"), el.get("cy")) for el in root.iter()
            if el is not root and (t := el.find(NS + "title")) is not None}


class Design(unittest.TestCase):
    def test_page_built(self):
        self.assertFalse(page().stub, "experimental-design is still a stub")

    def test_covers_its_items(self):
        items, errors = study.inventory(snap().files)
        mine = [i for i in items if i.page == SLUG]
        self.assertEqual(errors, [])
        # 8 study stage rows, 12 course context rows and the course context summary; a dropped mapping shows here.
        self.assertEqual(len(mine), 21)
        covered, checked = study.coverage(mine, {SLUG: html()})
        self.assertEqual(covered, [])
        self.assertEqual(checked, 21)

    def test_study_question(self):
        report = snap().files[snapshot.REPORT]
        intro = re.search(r'<h1 id="kalah-tdd-experiment">.*?</h1>(.*?)<h2', report, re.S).group(1)
        paragraphs = re.findall(r"<p>(.*?)</p>", intro, re.S)
        self.assertEqual(len(paragraphs), 2)
        for p in paragraphs:
            self.assertIn(study.squash(study.Tree(p).root.text()), main_text())

    def test_spec_sections(self):
        heads = {(n.tag, study.spaced(n)) for n in page().root.iter() if n.tag in ("h3", "h4")}
        text = main_text()
        for section in facts()["analysis"]["spec"]:
            if section["level"] > 1:
                self.assertIn((f"h{section['level'] + 1}", section["title"]), heads)
            for raw in section["text"].splitlines():
                line = raw.strip().removeprefix("- ").replace("`", "")
                if line and not raw.strip().startswith("```"):
                    with self.subTest(line=line[:50]):
                        self.assertIn(study.squash(line), text)

    def test_variants_table_under_variants(self):
        """The play() variants table reads as part of the spec's Variants section, not of the last change case."""
        main = main_html()
        before = main[:main.index('<table id="variants"')]
        self.assertEqual(re.findall(r'<h[2-6] id="([^"]+)"', before)[-1], "spec-variants")

    def test_runs_table_keeps_every_run(self):
        head, rows = table("runs-table")
        runs = facts()["runs"]
        self.assertEqual(len(rows), 9)
        self.assertEqual(sorted(r[0] for r in rows), sorted(runs))
        col = {h: i for i, h in enumerate(head)}
        for row in rows:
            run = runs[row[0]]
            with self.subTest(run=row[0]):
                caps = run["caps"]
                self.assertEqual(row[col["Iterations cap"]], str(caps["iterations"]))
                self.assertEqual(row[col["Cycles cap"]], str(caps["cycles"]))
                self.assertEqual(row[col["Starts cap"]], str(caps["starts"]))
                self.assertEqual(row[col["Model"]], run["model"])
                self.assertEqual(row[col["Effort"]], run["effort"])
                self.assertEqual(row[col["Builds"]], str(len(run["methods"])))
                self.assertEqual(row[col["Methods doc"]], snapshot.run_doc(snap(), row[0]))
                commit = run.get("harness", {}).get("commit")
                self.assertEqual(row[col["Harness commit"]], commit[:7] if commit else "not recorded")

    def test_collect_steps_table(self):
        head, rows = table("collect-steps")
        self.assertEqual(head, ["Mode", "Order", "Step", "Skipped after a failed fetchBack"])
        want = [[mode, str(k), s["name"], "yes" if s["skippable"] else "no"]
                for mode, steps in facts()["pipeline"]["collect"].items() for k, s in enumerate(steps, 1)]
        self.assertEqual(rows, want)
        self.assertEqual(len(rows), 23)

    def test_three_numbered_figures(self):
        figs = figures()
        self.assertEqual([re.search(r'<p class="fig-n">(.*?)</p>', f).group(1) for f in figs.values()],
                         ["Figure 2.1", "Figure 2.2", "Figure 2.3"])
        ids = re.findall(r'\bid="([^"]+)"', html())
        self.assertEqual(sorted(i for i in set(ids) if ids.count(i) > 1), [])
        for id, fig in figs.items():
            with self.subTest(id):
                self.assertRegex(fig, r"<figcaption><p>.+?</p>")
                self.assertRegex(fig, r"</p><h3>[^<]+</h3>")
                root = svg_root(fig)
                self.assertTrue(root.find(NS + "title").text and root.find(NS + "desc").text)
                for href in re.findall(r'<a href="#([^"]+)"[^>]*>Data</a>', fig):
                    self.assertIn(href, ids)

    def test_text_versions_match_nodes(self):
        self.assertEqual(len(flows()), 2)
        for id, fig in flows().items():
            labels, items = node_labels(svg_root(fig)), text_items(fig)
            with self.subTest(id):
                self.assertEqual(len(items), len(labels))
                for item, label in zip(items, labels):
                    self.assertTrue(item.startswith(label + "."), (item, label))

    def test_flow_render_limits(self):
        self.assertEqual(list(flows()), ["pipeline-flow", "replicate-flow"])
        for id, fig in flows().items():
            root = svg_root(fig)
            with self.subTest(id):
                self.assertLessEqual(float(root.get("viewBox").split()[2]), 872)
                nodes, labels = node_boxes(root), label_boxes(root)
                for i, (text, box) in enumerate(labels):
                    self.assertFalse([n for n in nodes if overlap(box, n)], f"label {text!r} on a node")
                    self.assertFalse([t for t, b in labels[i + 1:] if overlap(box, b)], f"label {text!r} on a label")
                for cls in ("edge", "loop"):
                    for pts, _ in paths(root, cls):
                        for a, b in zip(pts, pts[1:]):
                            self.assertFalse([n for n in nodes if crosses(a, b, n)], f"{cls} {pts} crosses a node")
                edges = paths(root, "edge")
                self.assertEqual([t for _, t in edges if t and len(t) > 10], [])
                # A wrap edge runs M H V H V H, along the gap below its row at its third corner.
                gaps = sorted({pts[2][1] for pts, _ in edges if len(pts) == 6})
                row = lambda y: sum(g < y for g in gaps)
                wraps = [row(pts[0][1]) for pts, _ in edges if len(pts) == 6]
                self.assertEqual(len(wraps), len(set(wraps)), "two wrap edges leave one row")
                elbows = [pts[-1] for pts, t in edges if len(pts) == 4 and t]
                self.assertEqual(len(elbows), len(set(elbows)), "two labelled elbows share a target")
                for pts, _ in paths(root, "loop"):
                    self.assertEqual(row(pts[0][1]), row(pts[-1][1]), f"loop {pts} leaves its row")

    def test_arms_map_matches_table(self):
        fig = figures()["arms-map"]
        root, (head, rows) = svg_root(fig), table("arms-table")
        want = {f"{r[0]}, {run}: {cell}": cell for r in rows for run, cell in zip(head[1:], r[1:]) if cell}
        got = marks(root)
        self.assertEqual(sorted(got), sorted(want))
        builds = sum(int(re.match(r"\d+", cell).group(0)) for cell in want.values())
        runs = facts()["runs"]
        self.assertEqual(builds, sum(len(r["methods"]) for k, r in runs.items() if "/" not in k))
        self.assertEqual(builds, 62)
        rebuilt = "Held-out TDD, rep-2: 5 builds, 5 rebuilt"
        self.assertIn(rebuilt, got)
        rings = [(c.get("cx"), c.get("cy")) for c in root.iter(NS + "circle") if "ring" in c.get("class", "").split()]
        self.assertEqual(rings, [got[rebuilt]])

    def test_arms_map_fits(self):
        """The map fits a phone column near 1:1: a narrow viewBox, every text inside it, each row label above its marks."""
        root = svg_root(figures()["arms-map"])
        width, height = map(float, root.get("viewBox").split()[2:])
        self.assertLessEqual(width, 320)
        circles = [(float(c.get("cx")), float(c.get("cy")), float(c.get("r"))) for c in root.iter(NS + "circle")]
        self.assertLessEqual(max(x + r for x, _, r in circles), width)
        texts = list(root.iter(NS + "text"))
        for t in texts:
            x, n = float(t.get("x")), len(t.text)
            left = x - 3.5 * n if t.get("text-anchor") == "middle" else x
            self.assertTrue(0 <= left and left + 7 * n <= width, t.text)
        heads = sorted((float(t.get("x")), len(t.text)) for t in texts if t.get("text-anchor") == "middle")
        for (a, n), (b, m) in zip(heads, heads[1:]):
            self.assertLessEqual(a + 3.5 * n, b - 3.5 * m, "column heads overlap")
        labels = [float(t.get("y")) for t in texts if t.get("class") == "lbl"]
        self.assertEqual(len(labels), len(table("arms-table")[1]))
        for y, below in zip(labels, labels[1:] + [height + 10]):
            row = [(cy, r) for _, cy, r in circles if y < cy < below]
            with self.subTest(y=y):
                self.assertTrue(row)
                self.assertGreaterEqual(min(cy - r for cy, r in row), y + 3, "a mark covers its row label")
                self.assertLessEqual(max(cy + r for cy, r in row), below - 10, "a mark covers the next row label")

    def test_svg_min_width_opt_in(self):
        """A min-width on figure svgs names its svg class, so plots that later pages pass to parts.figure keep fitting."""
        sels = [s.strip() for sel, decl in css_rules() if re.search(r"(^|;)\s*min-width", decl)
                for s in sel.split(",") if "svg" in s]
        self.assertTrue(sels)
        self.assertEqual([s for s in sels if not re.search(r"\bsvg\.[\w-]+$", s)], [])

    def test_only_regions_scroll(self):
        """Every element a class rule scrolls sideways is a labelled .diagram or .table-scroll region, not a nested div."""
        scrollers = {c for sel, decl in css_rules() if re.search(r"(^|;)\s*overflow(-x)?:\s*auto", decl)
                     for s in sel.split(",") for c in re.findall(r"\.([\w-]+)", s.split()[-1])}
        self.assertLessEqual({"diagram", "table-scroll"}, scrollers)
        inner = [n.tag + "." + ".".join(n.classes()) for n in page().root.iter()
                 if n.closest("main") and scrollers & set(n.classes()) and not {"diagram", "table-scroll"} & set(n.classes())]
        self.assertEqual(inner, [])

    def test_svg_classes_in_css(self):
        css = CSS.read_text(encoding="utf-8")
        used = {c for svg in SVG.findall(main_html()) for v in re.findall(r'\bclass="([^"]*)"', svg) for c in v.split()}
        self.assertTrue(used)
        self.assertEqual(sorted(c for c in used if not re.search(rf"\.{re.escape(c)}(?![\w-])", css)), [])

    def test_scroll_regions_focusable(self):
        regions = [n for n in page().root.iter() if {"diagram", "table-scroll"} & set(n.classes())]
        self.assertGreaterEqual(len(regions), 6)
        for n in regions:
            with self.subTest(n.attrs.get("aria-label")):
                self.assertEqual((n.attrs.get("tabindex"), n.attrs.get("role")), ("0", "region"))
                self.assertTrue(n.attrs.get("aria-label"))


if __name__ == "__main__":
    unittest.main()
