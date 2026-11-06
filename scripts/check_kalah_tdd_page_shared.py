#!/usr/bin/env python3
"""Check the Kalah TDD page helpers shared across pages (#112): block splitting in kalah_tdd.blocks and the named runs
and doc versions in kalah_tdd.snapshot.

Usage: check_kalah_tdd_page_shared.py
"""
import functools
import importlib
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SHAPED = '<div class="shaped"><div class="entry"><p>x</p></div></div>'


@functools.cache
def kalah(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(f"kalah_tdd.{name}")


@functools.cache
def snap():
    return kalah("snapshot").load()


def fake(*runs):
    """A snapshot whose facts hold only these runs, each built under doc sha256 d<i>."""
    facts = {"runs": {run: {"doc_sha256": f"d{i}" * 8} for i, run in enumerate(runs)}}
    return kalah("snapshot").Snapshot("sha", runs[0], {}, facts, "doc")


class Blocks(unittest.TestCase):
    def test_elements_keep_order(self):
        html = f'<p>a</p>\n{SHAPED} <ul><li>u</li></ul>\n<p class="sub">b</p>'
        self.assertEqual(kalah("blocks").elements("s", html),
                         [("p", "", "<p>a</p>"), ("div", ' class="shaped"', SHAPED), ("ul", "", "<ul><li>u</li></ul>"),
                          ("p", ' class="sub"', '<p class="sub">b</p>')])

    def test_elements_of_nothing(self):
        self.assertEqual(kalah("blocks").elements("s", " \n"), [])

    def test_elements_refuse_loose_text(self):
        for html in ("<p>a</p> loose <p>b</p>", "loose<p>a</p>", "<p>a</p>loose", "<p>a"):
            with self.subTest(html), self.assertRaisesRegex(ValueError, r"^section s holds an unrecognised block '"):
                kalah("blocks").elements("s", html)

    def test_close_counts_nesting(self):
        html = '<div><div>a</div><p>b</p><div><div>c</div></div></div><div>d</div>'
        self.assertEqual(kalah("blocks").close(html, "div", len("<div>")), html.index("<div>d"))

    def test_close_skips_longer_tag(self):
        html = "<p><pre>a</pre>b</p>c"
        self.assertEqual(kalah("blocks").close(html, "p", len("<p>")), html.index("c"))

    def test_close_without_end(self):
        self.assertEqual(kalah("blocks").close("<div><div>a</div>", "div", len("<div>")), -1)

    def test_plain_keeps_separator(self):
        # results passes " " and glossary_data passes "", as their page text differs today.
        plain = kalah("blocks").plain
        self.assertEqual(plain("a<b>c</b>", " "), "a c")
        self.assertEqual(plain("a<b>c</b>", ""), "ac")
        self.assertEqual(plain(" <p>x &amp;\n y</p> ", ""), "x & y")

    def test_open_reads_tag_and_attrs(self):
        m = kalah("blocks").OPEN.match(' \n<div class="shaped">x</div>')
        self.assertEqual(m.groups(), ("div", ' class="shaped"'))


class Runs(unittest.TestCase):
    def test_named_runs_skip_longer_name(self):
        named = kalah("snapshot").named_runs
        self.assertEqual(named(fake("tcp-1", "tcp-10"), "<p>tcp-10 only</p>"), ["tcp-10"])
        self.assertEqual(named(fake("tcp-1", "tcp-10"), "<p>tcp-10 then tcp-1</p>"), ["tcp-10", "tcp-1"])
        self.assertEqual(named(snap(), "<p>tcp-1-list2 and tcp-1-list</p>"), ["tcp-1-list2", "tcp-1-list"])

    def test_named_runs_first_mention_order(self):
        html = "<p>rep-2/rebuild, <b>full-1</b> and rep-2, then full-1 again.</p>"
        self.assertEqual(kalah("snapshot").named_runs(snap(), html), ["rep-2/rebuild", "full-1", "rep-2"])

    def test_named_runs_skip_paths_and_words(self):
        html = '<p><a href="runs/full-1/report.html">report</a> of xfull-1 and full-1x.</p>'
        self.assertEqual(kalah("snapshot").named_runs(snap(), html), [])

    def test_named_runs_read_text_between_tags(self):
        self.assertEqual(kalah("snapshot").named_runs(snap(), "<b>a</b>tcp-1<i>b</i>"), ["tcp-1"])

    def test_doc_versions(self):
        html = "<p>Runs <b>tcp-1-list</b> and full-1, then tcp-1 and full-1 again.</p>"
        self.assertEqual(kalah("snapshot").doc_versions(snap(), html),
                         ["tcp-1-list 1f11dd37", "full-1 64606950", "tcp-1 1f11dd37"])
        self.assertEqual(kalah("snapshot").doc_versions(snap(), "<p>No run.</p>"), [])


if __name__ == "__main__":
    unittest.main()
