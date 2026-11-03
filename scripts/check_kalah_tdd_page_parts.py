#!/usr/bin/env python3
"""Check the shared Kalah TDD page parts (#79): table regions, claim tags, part figure numbers, figure frames and doc versions.

Usage: check_kalah_tdd_page_parts.py
"""
import functools
import importlib
import importlib.util
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
UNSAFE = 'a <b> & "c"'
SVG = '<svg viewBox="0 0 1 1"><title>t</title></svg>'
CAPTIONED = re.compile(r'<figure id="[^"]+">.*?</figure>', re.S)


@functools.cache
def kalah(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(f"kalah_tdd.{name}")


@functools.cache
def snap():
    return kalah("snapshot").load()


def report():
    return snap().files[kalah("snapshot").REPORT]


def frame(text=("One", UNSAFE)):
    return kalah("parts").figure("3.1", "loop", "The loop", SVG, "How a stage <em>runs</em>.", "#loop-data", text)


class Parts(unittest.TestCase):
    def test_table_is_named_scroll_region(self):
        self.assertEqual(kalah("parts").table("<table></table>", UNSAFE),
                         '<div class="table-scroll" role="region" tabindex="0" aria-label="a &lt;b&gt; &amp; &quot;c&quot;">'
                         "<table></table></div>")

    def test_tag_names_claim_kind(self):
        for kind in ("recomputed", "verified", "unchecked"):
            self.assertEqual(kalah("parts").tag(kind), f'<span class="tag">{kind}</span>')

    def test_tag_rejects_unknown_kind(self):
        for kind in ("Verified", "checked", ""):
            with self.subTest(kind), self.assertRaises(ValueError):
                kalah("parts").tag(kind)

    def test_numbers_count_by_part(self):
        parts, pagemap = kalah("parts"), kalah("pagemap")
        landing = parts.numbers("")
        self.assertEqual([next(landing), next(landing)], ["1.1", "1.2"])
        self.assertEqual(next(parts.numbers("experimental-design")), "2.1")
        for page in pagemap.PAGES:
            html = (STUDY / page.slug / "index.html").read_text(encoding="utf-8")
            with self.subTest(page.slug):
                self.assertIn(f"Part {pagemap.number(page.slug)} of {len(pagemap.PAGES)} ", html)

    def test_figure_frame(self):
        html = frame()
        self.assertTrue(html.startswith('<figure id="loop" aria-label="Figure 3.1: The loop"><p class="fig-n">Figure 3.1</p>'
                                        "<h3>The loop</h3>"), html)
        self.assertIn(f'<div class="diagram" role="region" tabindex="0" aria-label="Figure 3.1 diagram">{SVG}</div>'
                      "<figcaption><p>How a stage <em>runs</em>.</p>"
                      '<div class="fig-foot"><a href="#loop-data" aria-label="Data for Figure 3.1">Data</a></div>', html)
        self.assertTrue(html.endswith("</details></figcaption></figure>"), html)
        self.assertNotRegex(html, r"<h3\b[^>]*\bid=", "a figure title with an id would join the sidebar")

    def test_figure_title_is_a_label(self):
        spec = importlib.util.spec_from_file_location("check_kalah_tdd_study", SCRIPTS / "check_kalah_tdd_study.py")
        study = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(study)
        self.assertIn(("figure title", "The loop"), list(study.labels(study.parse(f"<main>{frame()}</main>").root)))

    def test_figure_text_version_from_flow_or_list(self):
        flow = kalah("figures.flow")
        nodes = [flow.node("a", "Start"), flow.node("b", "End")]
        given = flow.text_version("The loop", nodes, [flow.edge("a", "b")])
        self.assertIn(given + "</figcaption>", frame(given))
        self.assertIn(flow.details("The loop", "<li>One</li><li>a &lt;b&gt; &amp; &quot;c&quot;</li>") + "</figcaption>", frame())
        self.assertEqual(flow.details("T", "<li>x</li>"), "<details><summary>Text version: T</summary><ol><li>x</li></ol></details>")

    def test_source_figure_keeps_svg_bytes(self):
        figures = CAPTIONED.findall(report())
        self.assertEqual(len(figures), 14)
        for k, fig in enumerate(figures, 1):
            out = kalah("parts").source_figure(f"4.{k}", fig)
            with self.subTest(fig[:40]):
                self.assertEqual(re.findall(r"<svg\b.*?</svg>", out, re.S), re.findall(r"<svg\b.*?</svg>", fig, re.S))
                self.assertEqual(re.findall(r"<summary>Table view.*?</summary>", out), re.findall(r"<summary>Table view.*?</summary>", fig))
                self.assertEqual(re.findall(r'<div class="plot">.*?</div>', out, re.S), re.findall(r'<div class="plot">.*?</div>', fig, re.S))

    def test_source_figure_foot(self):
        fig = next(f for f in CAPTIONED.findall(report()) if f.startswith('<figure id="pmd-cost">'))
        out = kalah("parts").source_figure("4.2", fig)
        self.assertTrue(out.startswith('<figure id="pmd-cost" aria-label="Figure 4.2: PMD violations against weighted tokens">'
                                       '<figcaption><p class="fig-n">Figure 4.2</p><h3>'), out[:200])
        legend = re.search(r'<div class="legend">.*?</div>', fig, re.S).group(0)
        self.assertIn(f'<div class="fig-foot">{legend}<a href="#pmd-cost-data" aria-label="Data for Figure 4.2">Data</a></div>'
                      '<details id="pmd-cost-data"><summary>Table view', out)
        self.assertTrue(out.endswith("</details></figure>"))

    def test_source_figure_rejects_other_shapes(self):
        diagram = re.search(r'<figure class="diagram">.*?</figure>', report(), re.S).group(0)
        fig = CAPTIONED.search(report()).group(0)
        for shape in (diagram, fig.replace('<div class="legend">', '<div class="key">'), fig + fig, "<p>no figure</p>"):
            with self.subTest(shape[:40]), self.assertRaises(ValueError):
                kalah("parts").source_figure("4.1", shape)

    def test_doc_versions(self):
        s = snap()
        self.assertEqual(s.doc, "12f026f6")
        runs = {"full-1": "64606950", "pilot-1": "64606950", "pilot-2": "64606950", "tcp-1": "1f11dd37",
                "tcp-1-list": "1f11dd37", "rep-1": "12f026f6", "rep-2": "12f026f6", "rep-2/rebuild": "12f026f6",
                "tcp-1-list2": "12f026f6"}
        self.assertEqual({run: kalah("snapshot").run_doc(s, run) for run in s.facts["runs"]}, runs)


if __name__ == "__main__":
    unittest.main()
