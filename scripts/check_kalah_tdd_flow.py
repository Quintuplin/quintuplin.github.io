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


def render(prefix="f1"):
    nodes, edges, loops = sample()
    return flow().svg(prefix, "Harness " + UNSAFE, "Desc " + UNSAFE, nodes, edges, loops)


def items():
    """Each text version list item as plain text, in order."""
    root = ET.fromstring(flow().text_version(*sample()))
    return ["".join(li.itertext()) for li in root.iter("li")]


class Flow(unittest.TestCase):
    def test_text_version_matches_nodes(self):
        nodes, _, _ = sample()
        got = items()
        self.assertEqual(len(got), len(nodes))
        for item, n in zip(got, nodes):
            self.assertTrue(item.startswith(n.label), (item, n.label))
        self.assertEqual(flow().text_version(*sample()).count("Text version"), 1)

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
        out, text = render(), flow().text_version(*sample())
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
        used = {c for v in re.findall(r'\bclass="([^"]*)"', render() + flow().text_version(*sample())) for c in v.split()}
        self.assertTrue({"flow", "lane", "node", "edge", "loop", "head"} <= used, used)
        self.assertEqual(used - defined, set())

    def test_no_colour_literals(self):
        out = re.sub(r'url\(#[\w-]+\)|href="#[\w-]+"|id="[\w-]+"|aria-labelledby="[^"]*"', "", render())
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,8}\b|\b(rgba?|hsla?)\(", out))
        self.assertIsNone(re.search(r"\s(fill|stroke|style|color|stop-color)=", out))

    def test_deterministic(self):
        self.assertEqual(render().encode(), render().encode())
        self.assertEqual(flow().text_version(*sample()), flow().text_version(*sample()))

    def test_rejects_unknown_nodes(self):
        f = flow()
        nodes = [f.node("a", "A")]
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes, [f.edge("a", "b")], [])
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes, [], [f.loop("b", "unit")])
        self.assertRaises(ValueError, f.svg, "p", "t", "d", nodes + nodes, [], [])


if __name__ == "__main__":
    unittest.main()
