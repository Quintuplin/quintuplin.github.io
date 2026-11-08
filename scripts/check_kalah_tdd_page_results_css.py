#!/usr/bin/env python3
"""Check study.css in headless Chrome: results summary markers, stacked table cells and nested-card borders,
all study pages without sideways page scroll, and every workflow's active presentation at 375, 768 and 1440px.
One Chrome launch loads srcdoc iframes with study.css inlined, plus copies with the guarded styles broken.
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
sys.path.insert(0, str(SCRIPTS))
from kalah_tdd import pagemap, parts  # noqa: E402

STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
FIXTURE = SCRIPTS / "fixtures/kalah-tdd/results-qtable.fixture"
BASE = "/studies/kalah-tdd-study/"
SLUGS = ("results/survey", "results/contrasts", "results/consistency", "results/test-order")
PAGE_SLUGS = tuple(p.slug for p in pagemap.PAGES)
MEASURES = "methodology/measures"
WIDTHS = (375, 768, 1440)
MODE = os.environ.get("KALAH_COLOR_MODE", "light")
CHROMES = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "C:/Program Files/Google/Chrome/Application/chrome.exe", "google-chrome", "google-chrome-stable", "chromium",
           "chromium-browser")
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
addEventListener("load", async () => {
  const out = {}, resizes = [];
  const resized = () => new Promise(resolve => {
    const pending = new Set(resizes.map(r => r.region));
    if (!pending.size) return resolve();
    const observers = [], delivered = entries => {
      for (const entry of entries) pending.delete(entry.target);
      if (!pending.size) { observers.forEach(observer => observer.disconnect()); resolve(); }
    };
    for (const region of pending) {
      const observer = new region.ownerDocument.defaultView.ResizeObserver(delivered);
      observers.push(observer); observer.observe(region); region.getBoundingClientRect();
    }
  });
  for (const f of document.querySelectorAll("iframe")) {
    const d = f.contentDocument, w = f.contentWindow, cs = (el, p) => w.getComputedStyle(el, p);
    const forced = w.matchMedia("(forced-colors: active)").matches;
    const fails = [], counts = {summaries: 0, cols: 0, qtables: 0, nested: 0};
    const check = (name, ok, what) => { if (!ok) fails.push([name, what]); };
    const first = (td) => check("stacked-first-cell", cs(td).position === "static" &&
      (cs(td).backgroundColor === "rgba(0, 0, 0, 0)" ||
       forced && cs(td).backgroundColor === cs(td.closest("table")).backgroundColor),
      td.textContent.slice(0, 40) + " " + cs(td).position + "/" + cs(td).backgroundColor + "/" + cs(td.closest("table")).backgroundColor);
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
    const formatted = d.getElementById("format-table");
    if (formatted) {
      const cells = [...formatted.querySelectorAll("td.number")], region = formatted.parentElement;
      counts.numbers = cells.length;
      check("table-format", region.scrollWidth <= region.clientWidth && cells.length === 2, "numeric records fit");
      for (const cell of cells) {
        const range = d.createRange(); range.selectNodeContents(cell);
        check("table-format", range.getClientRects().length === 1 && cs(cell).overflowWrap === "normal" &&
          cs(cell).fontVariantNumeric.includes("tabular-nums"), cell.textContent);
      }
      if (f.width <= 640) check("table-format", cs(region).borderTopWidth === "0px", "record cards have one border");
    }
    const matrix = d.getElementById("format-matrix");
    if (matrix) {
      const region = matrix.parentElement;
      check("matrix-format", matrix.classList.contains("matrix") && cs(matrix.querySelector("thead")).display ===
        "table-header-group" && cs(matrix.querySelector("tbody tr")).display === "table-row", "matrix keeps table semantics");
      check("matrix-format", region.scrollWidth <= region.clientWidth, "a compact numeric matrix fits without forced widths");
      for (const cell of matrix.querySelectorAll("td.number"))
        check("matrix-format", cs(cell).whiteSpace === "nowrap", "numeric token stays whole");
    }
    // Study dot charts hold their drawn width, so chart text stays at its 12px size and the region scrolls instead.
    for (const svg of d.querySelectorAll(".diagram svg.plot")) {
      counts.charts = (counts.charts || 0) + 1;
      const scale = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
      for (const t of svg.querySelectorAll("text"))
        check("chart-text", parseFloat(cs(t).fontSize) * scale >= 11.5, svg.closest("figure").id + " " + t.textContent.slice(0, 30));
    }
    for (const svg of d.querySelectorAll("#rep-consistency .plot > svg")) {
      const labels = [...svg.querySelectorAll("text")].filter(t => t.textContent === "Relative spread, 1 = pooled reference spread");
      counts.consistencyAxis = labels.length;
      check("consistency-axis", labels.length === 1, "one visible pooled reference axis label");
      for (const label of labels) {
        const a = label.getBoundingClientRect(), b = svg.getBoundingClientRect();
        check("consistency-axis", a.width > 0 && a.left >= b.left - 1 && a.right <= b.right + 1 &&
          a.top >= b.top - 1 && a.bottom <= b.bottom + 1, "axis label fits the SVG");
      }
    }
    const shown = (el) => {
      for (let p = el; p; p = p.parentElement) {
        const s = cs(p);
        if (s.display === "none" || s.visibility !== "visible" || Number(s.opacity) === 0) return false;
      }
      return el.getClientRects().length > 0;
    };
    const workflows = [];
    for (const svg of d.querySelectorAll(".diagram svg.flow")) {
      const region = svg.closest(".diagram"), id = svg.closest("figure").id;
      const compact = [...region.children].find(el => el !== svg && el.querySelector("[data-node]"));
      const presentations = [svg, compact].filter(Boolean), active = presentations.filter(shown);
      const measurement = id === "f4", natural = svg.viewBox.baseVal.width;
      const readable = [...svg.querySelectorAll("text")].every(t => parseFloat(cs(t).fontSize) >= 12);
      const expected = f.dataset.name.startsWith("no-js ") || natural > region.clientWidth || !readable ? compact : svg;
      counts.workflowRegions = (counts.workflowRegions || 0) + 1;
      const fits = region.scrollWidth <= region.clientWidth;
      check("workflow-fit", fits, id + " " + region.scrollWidth + " > " + region.clientWidth);
      check("workflow-presentations", presentations.length === 2 && active.length === 1,
        id + " " + presentations.length + " available, " + active.length + " visible");
      check("workflow-selection", active.length === 1 && active[0] === expected, id + " natural width " + natural);
      if (measurement) {
        counts.measurementRegions = (counts.measurementRegions || 0) + 1;
        check("measurement-fit", fits, region.scrollWidth + " > " + region.clientWidth);
      }
      const box = region.getBoundingClientRect(), left = box.left + region.clientLeft, right = left + region.clientWidth;
      let texts = 0, smallest = Infinity;
      for (const presentation of active) {
        const walker = d.createTreeWalker(presentation, w.NodeFilter.SHOW_TEXT);
        for (let t = walker.nextNode(); t; t = walker.nextNode()) {
          const el = t.parentElement, label = t.textContent.trim();
          if (!label || el.closest("title, desc, script, style")) continue;
          texts++;
          if (measurement) counts.measurementTexts = (counts.measurementTexts || 0) + 1;
          const range = d.createRange();
          range.selectNodeContents(t);
          const rect = range.getBoundingClientRect(), matrix = el.getScreenCTM?.();
          const scale = matrix ? Math.hypot(matrix.a, matrix.b) :
            (el.offsetWidth ? el.getBoundingClientRect().width / el.offsetWidth : 1);
          const size = parseFloat(cs(el).fontSize) * scale;
          smallest = Math.min(smallest, size);
          const visible = shown(el), readable = visible && rect.width > 0 && rect.height > 0 &&
            rect.left >= left - 1 && rect.right <= right + 1;
          const where = id + " " + label + " bounds " + rect.left.toFixed(1) + ".." + rect.right.toFixed(1) +
            " outside " + left.toFixed(1) + ".." + right.toFixed(1) + (visible ? "" : " [hidden]");
          check("workflow-text", size >= 11.9, id + " " + label + " rendered at " + size.toFixed(2) + "px");
          check("workflow-label", readable, where);
          if (measurement) {
            check("measurement-text", size >= 11.9, label + " rendered at " + size.toFixed(2) + "px");
            check("measurement-label", readable, where);
          }
        }
      }
      check("workflow-text-count", texts > 0, id + " has no active labels");
      workflows.push({id, natural, clientWidth: region.clientWidth, scrollWidth: region.scrollWidth, texts, smallest,
        active: active.map(el => el === svg ? "svg" : "compact")});
      if (!f.dataset.name.startsWith("no-js ")) resizes.push({region, svg, compact, presentations, shown, check, id,
        width: region.style.maxWidth, readable});
    }
    const ids = [...d.querySelectorAll("[id]")].map(el => el.id);
    if (workflows.length) check("workflow-ids", ids.length === new Set(ids).size, "duplicate page ids");
    const root = d.documentElement;
    check("sideways-scroll", root.scrollWidth <= root.clientWidth, root.scrollWidth + " > " + root.clientWidth);
    out[f.dataset.name] = {counts, fails, workflows,
      environment: {scheme: cs(root).colorScheme, forced: w.matchMedia("(forced-colors: active)").matches}};
  }
  for (const r of resizes) r.region.style.maxWidth = "180px";
  await resized();
  for (const r of resizes) {
    const active = r.presentations.filter(r.shown);
    r.check("workflow-resize", active.length === 1 && active[0] === r.compact, r.id + " after narrowing to 180px");
    r.region.style.maxWidth = r.width;
  }
  await resized();
  for (const r of resizes) {
    const active = r.presentations.filter(r.shown);
    const expected = r.svg.viewBox.baseVal.width > r.region.clientWidth || !r.readable ? r.compact : r.svg;
    r.check("workflow-resize", active.length === 1 && active[0] === expected, r.id + " after restoring width");
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


@functools.cache
def workflow_slugs():
    return tuple(slug for slug in PAGE_SLUGS if re.search(r'<svg\b[^>]*class="flow"', html(slug)))


def doc(slug, style, extra=""):
    """A page with style inlined for study.css, extra before </main> and the font links dropped, so no server or
    network is needed."""
    page = html(slug)
    if page.count(LINK) != 1 or page.count("</main>") != 1:
        raise AssertionError(f"{slug} has no single study.css link and main")
    page = page.replace('<html lang="en">', f'<html lang="en" data-theme="{"dark" if MODE == "dark" else "light"}">', 1)
    return FONTS.sub("", page).replace(LINK, f"<style>{style}</style>").replace("</main>", extra + "</main>")


def frames():
    """(name, width, document) for every probed frame."""
    fixture = FIXTURE.read_text(encoding="utf-8")
    out = [(f"{slug} {w}", w, doc(slug, css())) for slug in PAGE_SLUGS for w in WIDTHS]
    out.append(("fixture 375", 375, doc("results/contrasts", css(), fixture)))
    out += [("mutated contrasts 375", 375, doc("results/contrasts", mutated())),
            ("mutated fixture 375", 375, doc("results/contrasts", mutated(), fixture))]
    clipped = (css() + "\n#f4 .diagram > *{min-width:1600px!important;width:1600px!important;max-width:none!important}"
               "\n#f4 .diagram :is(text,[data-node],[data-node] *){font-size:4px!important}")
    out.append(("clipped measurement 375", 375, doc(MEASURES, clipped)))
    out += [("no-js " + name, w, page)
            for name, w, page in out if name.rsplit(" ", 1)[0] in workflow_slugs()]
    forced = (css() + "\n.diagram:has(svg.flow) > *{min-width:1600px!important;width:1600px!important;max-width:none!important}")
    out.append(("forced workflow overflow 375", 375, doc("experimental-design", forced)))
    hidden = css() + "\n.diagram svg.flow text:first-of-type,.diagram [data-node]{visibility:hidden!important}"
    out.append(("hidden workflow label 375", 375, doc("experimental-design", hidden)))
    formatted = parts.table('<table id="format-table" class="cols"><thead><tr><th>Method</th><th>Score</th><th>Notes</th>'
                            '</tr></thead><tbody><tr><td data-th="Method">Functions first, classes later</td>'
                            '<td data-th="Score">1,234.50</td><td data-th="Notes">A descriptive cell wraps naturally.</td></tr>'
                            '<tr><td data-th="Method">Most informative next test</td><td data-th="Score">15/15</td>'
                            '<td data-th="Notes">A longer explanation keeps the score intact.</td></tr></tbody></table>', 'Scores')
    out += [(f"formatted table {w}", w, doc("results/contrasts", css(), formatted)) for w in WIDTHS]
    out.append(("mutated narrative 375", 375, doc("results/contrasts", mutated(), formatted)))
    matrix = parts.table('<table class="cols" id="format-matrix"><thead><tr><th>Method</th><th>M</th><th>E</th></tr></thead>'
                         '<tbody><tr><td>A</td><td>470,362</td><td>5</td></tr><tr><td>B</td><td>at bound</td><td>2</td></tr></tbody></table>', 'Numeric comparison')
    out += [(f"numeric matrix {w}", w, doc("results/contrasts", css(), matrix)) for w in WIDTHS]
    out.append(("small svg text 1440", 1440, doc("designs/annealed", css() + "\nsvg.flow text{font-size:11px!important}")))
    out.append(("obsolete axis 375", 375, doc("results/consistency", css()).replace(
        ">Relative spread, 1 = pooled reference spread</text>", ">Relative spread, 1 is the average</text>")))
    return out


@functools.cache
def probe():
    """{frame name: {"counts", "fails", "summaries in html"}} from one headless Chrome launch."""
    if MODE not in ("light", "dark", "forced"):
        raise ValueError(f"unknown KALAH_COLOR_MODE {MODE!r}")
    for slug in PAGE_SLUGS:
        if 'name="kalah-tdd-stub"' in html(slug):
            raise AssertionError(f"{slug} is a stub; the probe needs the built study pages")
    made = frames()
    iframes = []
    for name, w, d in made:
        policy = ' sandbox="allow-same-origin"' if name.startswith("no-js ") else ""
        iframes.append(f'<iframe{policy} data-name="{name}" width="{w}" height="800" srcdoc="{escape(d)}"></iframe>')
    iframes = "".join(iframes)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        top = Path(tmp) / "probe.html"
        top.write_text(f'<!doctype html><html><head><meta charset="utf-8"></head><body>{iframes}{PROBE}</body></html>',
                       encoding="utf-8")
        start = time.monotonic()
        flags = ["--force-high-contrast"] if MODE == "forced" else []
        run = subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                              *flags,
                              f"--user-data-dir={tmp}/profile", "--window-size=1400,1000", "--virtual-time-budget=10000",
                              "--dump-dom", top.as_uri()], capture_output=True, encoding="utf-8", timeout=120, check=False)
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


def real(width=None, slugs=SLUGS):
    return [f"{slug} {w}" for slug in slugs for w in WIDTHS if width in (None, w)]


def workflow_frames():
    names = real(slugs=workflow_slugs())
    return names + ["no-js " + name for name in names]


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

    def test_requested_colour_mode_is_active(self):
        for name in real(slugs=PAGE_SLUGS):
            with self.subTest(name):
                environment = probe()[name]["environment"]
                if MODE == "forced":
                    self.assertTrue(environment["forced"])
                else:
                    self.assertEqual(environment["scheme"], MODE)
                    self.assertFalse(environment["forced"])

    def test_numeric_tokens_and_record_cards_remain_readable(self):
        for width in WIDTHS:
            with self.subTest(width):
                self.assertEqual(fails(f"formatted table {width}", "table-format"), [])
        for check in ("stacked-head", "stacked-first-cell", "stacked-label"):
            self.assertEqual(fails("formatted table 375", check), [])

    def test_numeric_matrices_keep_comparison_rows(self):
        for width in WIDTHS:
            with self.subTest(width):
                self.assertEqual(fails(f"numeric matrix {width}", "matrix-format"), [])

    def test_small_svg_labels_select_compact(self):
        name = "small svg text 1440"
        self.assertEqual(probe()[name]["workflows"][0]["active"], ["compact"])
        for check in ("workflow-selection", "workflow-text", "workflow-label"):
            self.assertEqual(fails(name, check), [])

    def test_consistency_axis_names_the_pooled_reference_and_fits(self):
        for width in WIDTHS:
            name = f"results/consistency {width}"
            with self.subTest(width):
                self.assertEqual(probe()[name]["counts"].get("consistencyAxis"), 1)
                self.assertEqual(fails(name, "consistency-axis"), [])
        self.assertTrue(fails("obsolete axis 375", "consistency-axis"))

    def test_stacked_cols_375(self):
        for name in real(375):
            with self.subTest(name):
                for check in ("stacked-head", "stacked-first-cell", "stacked-label"):
                    self.assertEqual(fails(name, check), [])
        self.assertGreater(sum(probe()[name]["counts"]["cols"] for name in real(375, PAGE_SLUGS)), 0)

    def test_qtable_fixture_375(self):
        self.assertEqual(fails("fixture 375", "stacked-first-cell"), [])
        self.assertEqual(fails("fixture 375", "nested-border"), [])
        self.assertEqual(probe()["fixture 375"]["counts"]["qtables"], 1)
        self.assertEqual(probe()["fixture 375"]["counts"]["nested"], 1)

    def test_no_sideways_scroll(self):
        for name in real(slugs=PAGE_SLUGS) + ["fixture 375"]:
            with self.subTest(name):
                self.assertEqual(fails(name, "sideways-scroll"), [])

    def test_measurement_pipeline_fits_region(self):
        for name in real(slugs=(MEASURES,)):
            with self.subTest(name):
                self.assertEqual(probe()[name]["counts"].get("measurementRegions"), 1)
                self.assertEqual(fails(name, "measurement-fit"), [])

    def test_measurement_labels_are_readable(self):
        for name in real(slugs=(MEASURES,)):
            with self.subTest(name):
                self.assertGreater(probe()[name]["counts"].get("measurementTexts", 0), 17)
                self.assertEqual(fails(name, "measurement-text"), [])
                self.assertEqual(fails(name, "measurement-label"), [])

    def test_probe_rejects_clipped_measurement(self):
        name = "clipped measurement 375"
        self.assertEqual(probe()[name]["counts"].get("measurementRegions"), 1)
        for check in ("measurement-fit", "measurement-label", "measurement-text"):
            with self.subTest(check):
                self.assertTrue(fails(name, check))

    def test_every_workflow_region_fits(self):
        for width in WIDTHS:
            for prefix in ("", "no-js "):
                names = [prefix + name for name in real(width, workflow_slugs())]
                self.assertEqual(sum(probe()[name]["counts"].get("workflowRegions", 0) for name in names), 19)
        for name in workflow_frames():
            with self.subTest(name):
                self.assertEqual(fails(name, "workflow-fit"), [])

    def test_active_workflow_labels_remain_readable(self):
        for name in workflow_frames():
            with self.subTest(name):
                for check in ("workflow-text-count", "workflow-text", "workflow-label"):
                    self.assertEqual(fails(name, check), [])

    def test_exactly_one_workflow_presentation_is_visible(self):
        for name in workflow_frames():
            with self.subTest(name):
                for check in ("workflow-presentations", "workflow-selection", "workflow-resize", "workflow-ids"):
                    self.assertEqual(fails(name, check), [])

    def test_probe_detects_forced_workflow_overflow(self):
        name = "forced workflow overflow 375"
        self.assertEqual(probe()[name]["counts"].get("workflowRegions"), 2)
        self.assertTrue(all(r["scrollWidth"] >= 1600 for r in probe()[name]["workflows"]))
        self.assertEqual(len(fails(name, "workflow-fit")), 2)
        self.assertTrue(fails(name, "workflow-label"))
        self.assertTrue(any(what.endswith(" [hidden]") for _, what in fails("hidden workflow label 375", "workflow-label")))

    def test_chart_text_full_size(self):
        for name in real():
            with self.subTest(name):
                self.assertEqual(fails(name, "chart-text"), [])
        self.assertEqual([probe()[f"{s} 375"]["counts"].get("charts", 0) for s in SLUGS], [0, 1, 0, 1])

    def test_probe_catches_regression(self):
        failed = {n: {f[0] for f in fails(n)} for n in ("mutated contrasts 375", "mutated fixture 375", "mutated narrative 375")}
        expected = {"summary-marker"} | ({"stacked-first-cell"} if probe()["mutated contrasts 375"]["counts"]["cols"] else set())
        self.assertEqual(failed["mutated contrasts 375"], expected)
        self.assertEqual(failed["mutated narrative 375"], {"summary-marker", "stacked-first-cell"})
        self.assertEqual(failed["mutated fixture 375"], set(GUARDED))
        for env, known in (({"CHROME": "/no/such/chrome"}, CHROMES), ({}, ())):
            with self.subTest(env), self.assertRaisesRegex(FileNotFoundError, "set CHROME to"):
                chrome(env, known)


if __name__ == "__main__":
    unittest.main()
