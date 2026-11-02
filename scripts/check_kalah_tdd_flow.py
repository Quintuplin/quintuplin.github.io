#!/usr/bin/env python3
"""Check the Kalah TDD flowchart primitives (#57): text version, ids, escaping, loop labels and study.css colours.

Usage: check_kalah_tdd_flow.py
"""
import functools
import importlib
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
CSS = SCRIPTS.parent / "studies/kalah-tdd-study/study.css"
UNSAFE = 'a <b> & "c"'
NS = "{http://www.w3.org/2000/svg}"


@functools.cache
def flow():
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("kalah_tdd.figures.flow")


def sample():
    f = flow()
    nodes = [f.node("args", "Read args", lane="Host"), f.node("batch", "Run batch per clone", lane="Clone"),
             f.node("stage", "Stage agents", lane="Clone", note="S and L stages"),
             f.node("odd", UNSAFE, lane=UNSAFE), f.node("report", "Report", lane="Host")]
    edges = [f.edge("args", "batch"), f.edge("batch", "stage", "spawns"), f.edge("stage", "odd", UNSAFE),
             f.edge("odd", "report")]
    loops = [f.loop("stage", "unit"), f.loop("odd", "clone", back_to="batch")]
    return nodes, edges, loops


def long_chart():
    """Twelve nodes: eleven steps in lane A that wrap into rows, a lane B node under s5, a self loop and a back loop."""
    f = flow()
    nodes = [f.node(f"s{i}", f"Step {i} of the harness pipeline", lane="A") for i in range(11)]
    nodes.insert(6, f.node("v", "Side step", lane="B", col=5))
    edges = [f.edge(f"s{i}", f"s{i + 1}", "next") for i in range(10)] + [f.edge("s5", "v", "down"), f.edge("v", "s6")]
    loops = [f.loop("s9", "unit"), f.loop("s10", "clone", back_to="s8")]
    return nodes, edges, loops


def render(prefix="f1"):
    nodes, edges, loops = sample()
    return flow().svg(prefix, "Harness " + UNSAFE, "Desc " + UNSAFE, nodes, edges, loops)


def node_boxes(root):
    """Each node rect as (x, y, width, height), in node order."""
    return [tuple(float(r.get(k)) for k in ("x", "y", "width", "height"))
            for r in root.iter(NS + "rect") if r.get("class") == "node"]


def points(d):
    """The corners of an M/H/V path."""
    pts = []
    for cmd, arg in re.findall(r"([MHV])([\d.,-]+)", d):
        x, y = pts[-1] if pts else (0, 0)
        pts.append(tuple(map(float, arg.split(","))) if cmd == "M" else (float(arg), y) if cmd == "H" else (x, float(arg)))
    return pts


def on_edge(p, box):
    (px, py), (x, y, w, h) = p, box
    return x <= px <= x + w and y <= py <= y + h and (px in (x, x + w) or py in (y, y + h))


def crosses(a, b, box):
    """Whether the horizontal or vertical segment a-b enters the inside of box."""
    (x, y, w, h), (ax, ay), (bx, by) = box, a, b
    if ay == by:
        return y < ay < y + h and max(min(ax, bx), x) < min(max(ax, bx), x + w)
    return x < ax < x + w and max(min(ay, by), y) < min(max(ay, by), y + h)


def text_doc():
    return flow().text_version("Harness " + UNSAFE, *sample())


def items():
    """Each text version list item as plain text, in order."""
    root = ET.fromstring(text_doc())
    return ["".join(li.itertext()) for li in root.iter("li")]


class Flow(unittest.TestCase):
    def test_text_version_matches_nodes(self):
        nodes, _, _ = sample()
        got = items()
        self.assertEqual(len(got), len(nodes))
        for item, n in zip(got, nodes):
            self.assertTrue(item.startswith(n.label), (item, n.label))
        self.assertEqual(text_doc().count("Text version"), 1)

    def test_text_version_names_its_chart(self):
        summary = ET.fromstring(text_doc()).find("summary")
        self.assertEqual(summary.text, "Text version: Harness " + UNSAFE)
        self.assertIn("<summary>Text version: Harness a &lt;b&gt; &amp; &quot;c&quot;</summary>", text_doc())

    def test_text_version_names_edges_and_loops(self):
        nodes, edges, loops = sample()
        labels = {n.id: n.label for n in nodes}
        index = {n.id: i for i, n in enumerate(nodes)}
        got = items()
        # The part after the node's own label names each target.
        after = {n.id: got[index[n.id]][len(n.label):] for n in nodes}
        for e in edges:
            self.assertIn(labels[e.dst], after[e.src], e)
            self.assertIn(e.label, after[e.src], e)
        for lp in loops:
            self.assertIn(f"repeat per {lp.unit}", after[lp.node], lp)
            self.assertIn(labels[lp.back_to or lp.node], after[lp.node], lp)

    def test_ids_unique_and_prefixed(self):
        out = render("f5-classic")
        ids = re.findall(r'\bid="([^"]*)"', out)
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([i for i in ids if not i.startswith("f5-classic-")], [])
        root = ET.fromstring(out)
        self.assertEqual(root.get("role"), "img")
        self.assertEqual(root.get("aria-labelledby"), "f5-classic-title f5-classic-desc")
        self.assertRaises(ValueError, flow().svg, 'x" onload="y', "t", "d", *sample())

    def test_ids_differ_by_prefix(self):
        self.assertEqual(set(re.findall(r'\bid="([^"]*)"', render("a"))) & set(re.findall(r'\bid="([^"]*)"', render("b"))), set())

    def test_escapes_text(self):
        out, text = render(), text_doc()
        for doc in (out, text):
            self.assertNotIn(UNSAFE, doc)
            ET.fromstring(doc)
        root = ET.fromstring(out)
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(root.find(ns + "title").text, "Harness " + UNSAFE)
        self.assertEqual(root.find(ns + "desc").text, "Desc " + UNSAFE)
        self.assertIn(UNSAFE, "".join(root.itertext()))
        self.assertIn(UNSAFE, items()[3])

    def test_loop_label(self):
        root = ET.fromstring(render())
        ns = "{http://www.w3.org/2000/svg}"
        texts = [" ".join("".join(t.itertext()).split()) for t in root.iter(ns + "text")]
        self.assertIn("repeat per unit", texts)
        self.assertIn("repeat per clone", texts)
        loops = [p for p in root.iter(ns + "path") if p.get("class") == "loop"]
        self.assertEqual(len(loops), 2)
        self.assertTrue(all(p.get("marker-end") for p in loops))

    def test_classes_defined_in_study_css(self):
        css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
        defined = set(re.findall(r"\.(-?[A-Za-z_][\w-]*)", css))
        used = {c for v in re.findall(r'\bclass="([^"]*)"', render() + text_doc()) for c in v.split()}
        self.assertTrue({"flow", "lane", "node", "edge", "loop", "head"} <= used, used)
        self.assertEqual(used - defined, set())

    def test_no_colour_literals(self):
        out = re.sub(r'url\(#[\w-]+\)|href="#[\w-]+"|id="[\w-]+"|aria-labelledby="[^"]*"', "", render())
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,8}\b|\b(rgba?|hsla?)\(", out))
        self.assertIsNone(re.search(r"\s(fill|stroke|style|color|stop-color)=", out))

    def test_deterministic(self):
        self.assertEqual(render().encode(), render().encode())
        self.assertEqual(text_doc(), text_doc())

    def test_rejects_unknown_nodes(self):
        f = flow()
        nodes = [f.node("a", "A")]
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes, [f.edge("a", "b")], [])
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes, [], [f.loop("b", "unit")])
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes + nodes, [], [])

    def test_long_chart_wraps(self):
        root = ET.fromstring(flow().svg("p", "t", "d", *long_chart()))
        self.assertLessEqual(float(root.get("viewBox").split()[2]), 900)
        boxes = {n.id: box for n, box in zip(long_chart()[0], node_boxes(root))}
        # Each row continues below the last, starting again at the left.
        self.assertEqual(boxes["s4"][0], boxes["s0"][0])
        self.assertGreater(boxes["s4"][1], boxes["s3"][1])
        self.assertGreater(boxes["s8"][1], boxes["v"][1])

    def test_rejects_edges_through_nodes(self):
        f = flow()
        x = [f.node(i, i.upper(), lane="x") for i in "abc"]
        far = [x[0], f.node("d", "D", lane="x", col=4)]
        down = [f.node("a", "A", lane="x"), f.node("b", "B", lane="y", col=0), f.node("c", "C", lane="z", col=0)]
        bad = {"backward": (x, [f.edge("b", "a")], []), "backward a row": (far, [f.edge("d", "a")], []),
               "skips an occupied column": (x, [f.edge("a", "c")], []),
               "elbow skips an occupied column": (x[:2] + [f.node("c", "C", lane="y")], [f.edge("a", "c")], []),
               "vertical through a lane": (down, [f.edge("a", "c")], []),
               "loop into a lower lane": (down, [], [f.loop("a", "unit", back_to="b")]),
               "loop into another row": (far, [], [f.loop("d", "unit", back_to="a")]),
               "loop up through a node": (down[:2] + [f.node("c", "C", lane="y", col=1)], [], [f.loop("c", "unit", back_to="a")]),
               "loop up through its own node": (down[:2], [f.edge("a", "b")], [f.loop("b", "unit", back_to="a")])}
        for case, args in bad.items():
            with self.subTest(case):
                self.assertRaises(ValueError, f.svg, "p", "t", "d", *args)
                self.assertRaises(ValueError, f.text_version, "t", *args)
        # Adjacent lanes, an empty skipped column and a loop up a clear column still draw.
        f.svg("p", "t", "d", down, [f.edge("a", "b"), f.edge("b", "c")])
        f.svg("p", "t", "d", [x[0], f.node("c", "C", lane="x", col=2)], [f.edge("a", "c")])
        f.svg("p", "t", "d", [x[0], f.node("b", "B", lane="y", col=1)], [], [f.loop("b", "unit", back_to="a")])

    def test_vertical_edge_label_starts_right_of_line(self):
        root = ET.fromstring(flow().svg("p", "t", "d", *long_chart()))
        down = [p for p in root.iter(NS + "path") if p.get("class") == "edge" and "H" not in p.get("d")]
        self.assertEqual(len(down), 1)
        x = float(re.match(r"M([\d.]+),", down[0].get("d")).group(1))
        label = next(t for t in root.iter(NS + "text") if "".join(t.itertext()) == "down")
        self.assertGreater(float(label.get("x")), x)
        self.assertEqual(label.get("text-anchor"), "start")

    def test_routes_run_between_nodes(self):
        f = flow()
        # An elbow from lane x past a lane y node in the middle column.
        elbow = ([f.node("a", "A", lane="x"), f.node("b", "B", lane="y"), f.node("c", "C", lane="y")],
                 [f.edge("a", "c"), f.edge("b", "c")], [])
        for name, (nodes, edges, loops) in {"sample": sample(), "long": long_chart(), "elbow": elbow}.items():
            root = ET.fromstring(f.svg("p", "t", "d", nodes, edges, loops))
            boxes = dict(zip([n.id for n in nodes], node_boxes(root)))
            ends = [(e.src, e.dst) for e in edges] + [(lp.node, lp.back_to or lp.node) for lp in loops]
            paths = [p for p in root.iter(NS + "path") if p.get("class") in ("edge", "loop")]
            self.assertEqual(len(paths), len(ends))
            for (src, dst), p in zip(ends, paths):
                with self.subTest(name, path=p.get("d")):
                    pts = points(p.get("d"))
                    self.assertTrue(on_edge(pts[0], boxes[src]) and on_edge(pts[-1], boxes[dst]))
                    hits = [i for a, b in zip(pts, pts[1:]) for i, box in boxes.items() if crosses(a, b, box)]
                    self.assertEqual(hits, [])

    def test_rejects_shared_cell(self):
        f = flow()
        nodes = [f.node("a", "A", lane="x"), f.node("b", "B", lane="x", col=0)]
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes)
        f.svg("p", "t", "d", [nodes[0], f.node("b", "B", lane="y", col=0)])


if __name__ == "__main__":
    unittest.main()
