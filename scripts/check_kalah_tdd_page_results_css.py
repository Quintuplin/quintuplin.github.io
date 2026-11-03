#!/usr/bin/env python3
"""Check study.css computed styles on the built Kalah TDD results pages in headless Chrome (#89): summary markers,
stacked .cols and .qtable first cells at 375px, the nested-card border and no sideways scroll at 375 and 768px.
One Chrome launch loads every page as a srcdoc iframe with study.css inlined, plus a copy with the guarded rules removed.
$CHROME names the Chrome binary when it is not in a known place.

Usage: check_kalah_tdd_page_results_css.py
"""
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from html import escape
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
FIXTURE = SCRIPTS / "fixtures/kalah-tdd/results-qtable.fixture"
BASE = "/studies/kalah-tdd-study/"
SLUGS = ("results/survey", "results/contrasts", "results/consistency", "results/test-order")
WIDTHS = (375, 768)
CHROMES = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable",
           "chromium", "chromium-browser")
# The rules the probe guards, each removed in the mutated copy.
GUARDED = {
    "summary-marker": 'summary::before{content:"\\25B8";content:"\\25B8" / "";flex:none;transition:transform .15s}',
    "stacked-first-cell": ":is(.qtable,.cols) td:first-child{position:static;background:none}",
    "nested-border": ".table-scroll .qtable,.qtable .table-scroll{margin:0;border:0;border-radius:0;background:none}",
}
FONTS = re.compile(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.[^"]*"[^>]*>\n')
LINK = f'<link rel="stylesheet" href="{BASE}study.css">'
# Runs in the top page once every frame has loaded and writes {frame: {"counts", "fails"}} into #out.
PROBE = """<pre id="out"></pre><script>
addEventListener("load", () => {
  const out = {};
  for (const f of document.querySelectorAll("iframe")) {
    const d = f.contentDocument, w = f.contentWindow, cs = (el, p) => w.getComputedStyle(el, p);
    const fails = [], counts = {summaries: 0, cols: 0, qtables: 0, nested: 0};
    const check = (name, ok, what) => { if (!ok) fails.push([name, what]); };
    const first = (td) => check("stacked-first-cell", cs(td).position === "static" &&
      cs(td).backgroundColor === "rgba(0, 0, 0, 0)", td.textContent.slice(0, 40));
    for (const det of d.querySelectorAll("details")) det.open = true;
    for (const s of d.querySelectorAll("summary")) {
      counts.summaries++;
      const c = cs(s, "::before").content;
      check("summary-marker", c !== "none" && c !== "normal" && cs(s).listStyleType === "none", s.textContent.slice(0, 40));
    }
    if (f.width <= 640) {
      for (const t of d.querySelectorAll("table.cols")) {
        counts.cols++;
        for (const head of t.querySelectorAll("thead")) check("stacked-head", cs(head).display === "none", t.textContent.slice(0, 40));
        for (const td of t.querySelectorAll("tr > td:first-child")) first(td);
        for (const td of t.querySelectorAll("td + td")) {
          const c = cs(td, "::before").content;
          check("stacked-label", c.includes(td.dataset.th) || c.startsWith("attr(data-th)"), td.dataset.th + " " + c);
        }
      }
      for (const q of d.querySelectorAll(".qtable")) {
        counts.qtables++;
        for (const td of q.querySelectorAll("tr > td:first-child")) first(td);
      }
    }
    for (const n of d.querySelectorAll(".table-scroll .qtable, .qtable .table-scroll")) {
      counts.nested++;
      const s = cs(n);
      check("nested-border", [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth].every(b => b === "0px"),
        n.className);
    }
    const root = d.documentElement;
    check("sideways-scroll", root.scrollWidth <= root.clientWidth, root.scrollWidth + " > " + root.clientWidth);
    out[f.dataset.name] = {counts, fails};
  }
  document.getElementById("out").textContent = JSON.stringify(out);
});
</script>"""


def chrome(env=os.environ, known=CHROMES):
    """The Chrome binary: $CHROME, else the first known install."""
    if given := env.get("CHROME"):
        if found := shutil.which(given):
            return found
        raise FileNotFoundError(f"CHROME={given} is not an executable; set CHROME to the Chrome binary")
    if found := next(filter(None, map(shutil.which, known)), None):
        return found
    raise FileNotFoundError("no Chrome found; set CHROME to the Chrome binary")


@functools.cache
def css():
    return (STUDY / "study.css").read_text(encoding="utf-8")


def mutated():
    """study.css with the guarded rules removed, each refused when study.css no longer holds it."""
    out = css()
    for name, rule in GUARDED.items():
        if out.count(rule) != 1:
            raise AssertionError(f"study.css no longer holds the {name} rule {rule!r} once")
        out = out.replace(rule, "")
    return out


def html(slug):
    return (STUDY / slug / "index.html").read_text(encoding="utf-8")


def doc(slug, style, extra=""):
    """A page with style inlined for study.css, extra before </main> and the font links dropped, so no server or
    network is needed."""
    page = html(slug)
    if page.count(LINK) != 1 or page.count("</main>") != 1:
        raise AssertionError(f"{slug} has no single study.css link and main")
    return FONTS.sub("", page).replace(LINK, f"<style>{style}</style>").replace("</main>", extra + "</main>")


def frames():
    """(name, width, document) for every probed frame."""
    fixture = FIXTURE.read_text(encoding="utf-8")
    out = [(f"{slug} {w}", w, doc(slug, css())) for slug in SLUGS for w in WIDTHS]
    out.append(("fixture 375", 375, doc("results/contrasts", css(), fixture)))
    out += [("mutated contrasts 375", 375, doc("results/contrasts", mutated())),
            ("mutated fixture 375", 375, doc("results/contrasts", mutated(), fixture))]
    return out


@functools.cache
def probe():
    """{frame name: {"counts", "fails", "summaries in html"}} from one headless Chrome launch."""
    for slug in SLUGS:
        if 'name="kalah-tdd-stub"' in html(slug):
            raise AssertionError(f"{slug} is a stub; the probe needs the built results pages")
    made = frames()
    iframes = "".join(f'<iframe data-name="{name}" width="{w}" height="800" srcdoc="{escape(d)}"></iframe>'
                      for name, w, d in made)
    with tempfile.TemporaryDirectory() as tmp:
        top = Path(tmp) / "probe.html"
        top.write_text(f'<!doctype html><html><head><meta charset="utf-8"></head><body>{iframes}{PROBE}</body></html>',
                       encoding="utf-8")
        start = time.monotonic()
        run = subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                              f"--user-data-dir={tmp}/profile", "--window-size=1400,1000", "--virtual-time-budget=10000",
                              "--dump-dom", top.as_uri()], capture_output=True, text=True, timeout=120, check=False)
        print(f"Chrome probe of {len(made)} frames took {time.monotonic() - start:.2f} s", file=sys.stderr)
    m = re.search(r'<pre id="out">(.*?)</pre>', run.stdout, re.S)
    if run.returncode or not m or not m.group(1):
        raise AssertionError(f"Chrome probe gave no result (exit {run.returncode}): {run.stderr[-500:]}")
    out = json.loads(m.group(1).replace("&quot;", '"').replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&"))
    for name, _, d in made:
        out[name]["summaries in html"] = d.count("<summary")
    return out


def fails(name, check=None):
    return [f for f in probe()[name]["fails"] if check in (None, f[0])]


def real(width=None):
    return [f"{slug} {w}" for slug in SLUGS for w in WIDTHS if width in (None, w)]


class ResultsCss(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe()

    def test_summary_markers(self):
        for name in real() + ["fixture 375"]:
            with self.subTest(name):
                self.assertEqual(fails(name, "summary-marker"), [])
                self.assertEqual(probe()[name]["counts"]["summaries"], probe()[name]["summaries in html"])
        # One contents summary per frame; the rest are figure table views.
        self.assertGreater(sum(probe()[n]["counts"]["summaries"] - 1 for n in real()), 0)

    def test_stacked_cols_375(self):
        for name in real(375):
            with self.subTest(name):
                for check in ("stacked-head", "stacked-first-cell", "stacked-label"):
                    self.assertEqual(fails(name, check), [])
        self.assertEqual([probe()[f"{s} 375"]["counts"]["cols"] > 0 for s in SLUGS], [True, True, True, False])

    def test_qtable_fixture_375(self):
        self.assertEqual(fails("fixture 375", "stacked-first-cell"), [])
        self.assertEqual(fails("fixture 375", "nested-border"), [])
        self.assertEqual(probe()["fixture 375"]["counts"]["qtables"], 1)
        self.assertEqual(probe()["fixture 375"]["counts"]["nested"], 1)

    def test_no_sideways_scroll(self):
        for name in real() + ["fixture 375"]:
            with self.subTest(name):
                self.assertEqual(fails(name, "sideways-scroll"), [])

    def test_probe_catches_regression(self):
        failed = {n: {f[0] for f in fails(n)} for n in ("mutated contrasts 375", "mutated fixture 375")}
        self.assertEqual(failed["mutated contrasts 375"], {"summary-marker", "stacked-first-cell"})
        self.assertEqual(failed["mutated fixture 375"], set(GUARDED))
        for env, known in (({"CHROME": "/no/such/chrome"}, CHROMES), ({}, ())):
            with self.subTest(env), self.assertRaisesRegex(FileNotFoundError, "set CHROME to"):
                chrome(env, known)


if __name__ == "__main__":
    unittest.main()
