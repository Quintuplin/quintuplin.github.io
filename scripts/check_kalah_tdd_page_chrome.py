#!/usr/bin/env python3
"""Check the Kalah TDD page chrome (#113): skip link first, labelled part lists, a source line naming the page's
runs, folds that open on a followed link, and pagers back to the landing contents list.

Usage: check_kalah_tdd_page_chrome.py
"""
import functools
import importlib
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BASE = "/studies/kalah-tdd-study/"
# A details fold around the #cell target, and the contents disclosure the opener also drives.
DOM = """
const listeners = {}, clicks = [];
const fold = {tagName: "DETAILS", open: false, parentElement: null};
const cell = {tagName: "TD", parentElement: fold};
const toc = {open: false, querySelector: () => null};
globalThis.location = {hash: "#cell"};
globalThis.matchMedia = () => ({matches: false, addEventListener() {}});
globalThis.addEventListener = (type, f) => { listeners[type] = f; };
globalThis.document = {readyState: "complete", getElementById: (id) => ({toc, cell})[id] || null,
                       addEventListener: (type, f) => clicks.push(f)};
"""
RUN = """
const seen = [fold.open];
fold.open = false; location.hash = "#cell"; listeners.hashchange(); seen.push(fold.open);
fold.open = false; clicks[0]({target: {closest: () => ({hash: "#cell"})}}); seen.push(fold.open);
fold.open = false; clicks[0]({target: {closest: () => ({hash: "#elsewhere"})}}); seen.push(fold.open);
console.log(JSON.stringify(seen));
"""


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


@functools.cache
def rendered():
    """{slug: html} of one fresh build."""
    out = script("build_kalah_tdd_study").render_pages(snap())
    return {path.removesuffix("index.html").rstrip("/"): html for path, html in out.items()}


@functools.cache
def parsed(slug):
    return study().parse(rendered()[slug])


def body(slug):
    return re.search(r'<main id="main">(.*)</main>', rendered()[slug], re.S).group(1)


class Chrome(unittest.TestCase):
    def test_skipLinkFirst(self):
        for slug in rendered():
            with self.subTest(slug):
                sheet = next(n for n in parsed(slug).root.iter() if "sheet" in n.classes())
                first = next(n for n in sheet.iter() if n.tag in ("a", "button", "summary", "input"))
                self.assertEqual((first.attrs.get("class"), first.attrs.get("href")), ("skip", "#main"))
                self.assertIs(sheet.elements()[0], first)

    def test_partListsLabelled(self):
        for slug in rendered():
            with self.subTest(slug):
                ids = parsed(slug).ids
                nav = next(n for n in ids["toc"].iter() if n.tag == "nav")
                lists = [n for n in nav.elements() if n.tag == "ol"]
                self.assertEqual(len(lists), len(kalah("pagemap").PARTS))
                for ol, part in zip(lists, kalah("pagemap").PARTS):
                    label = ids[ol.attrs["aria-labelledby"]]
                    self.assertEqual((label.tag, label.classes(), study().spaced(label)), ("p", ["part"], part))

    def test_sourceLineNamesPageRuns(self):
        sha = snap().sha[:7]
        for slug in rendered():
            with self.subTest(slug):
                runs = kalah("snapshot").named_runs(snap(), body(slug)) or [snap().run]
                prov = next(n for n in parsed(slug).root.iter() if "prov" in n.classes())
                said = runs[0] if len(runs) == 1 else f"{', '.join(runs[:-1])} and {runs[-1]}"
                self.assertEqual(study().spaced(prov),
                                 f"Source run{'s' if len(runs) > 1 else ''} {said} at tdd-experiment {sha}")
        self.assertEqual(kalah("snapshot").named_runs(snap(), body("results/consistency")), [])

    def test_hashOpensClosedDetails(self):
        # Pins the opener: a hash on load, a hash change or a followed link opens every fold around its target.
        opener = re.fullmatch(r"<script>(.*)</script>", kalah("chrome").OPENER, re.S).group(1)
        out = subprocess.run(["node"], input=DOM + opener + RUN, capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), [True, True, True, False])

    def test_pagerContentsTargetsList(self):
        self.assertEqual(parsed("").ids["contents"].tag, "h2")
        for slug in rendered():
            with self.subTest(slug):
                homes = [n.attrs["href"] for n in parsed(slug).root.iter() if "pager-home" in n.classes()]
                self.assertEqual(homes, [f"{BASE}#contents"] * 2)


if __name__ == "__main__":
    unittest.main()
