#!/usr/bin/env python3
"""Check the four Kalah TDD results pages (#89): each report results section kept verbatim with its heading as h2,
its figures numbered by part with svg bytes unchanged, free tables in labelled regions and question links pointed
at the questions page. The contrasts headline, the test order figures and the tcp-1 facts tables come from #90.

Usage: check_kalah_tdd_page_results.py [--render]
--render prints the four pages, which test_deterministic compares across hash seeds.
"""
import copy
import functools
import importlib
import importlib.util
import os
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
BASE = "/studies/kalah-tdd-study/"
SLUGS = ("results/survey", "results/contrasts", "results/consistency", "results/test-order")
# Report results items on the four pages, from check_kalah_tdd_study.inventory at the snapshot sha.
RESULTS_ITEMS = 283
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
P_OR_ENTRY = re.compile(r'<p\b[^>]*>.*?</p>|<div class="entry">.*?</div>', re.S)
# Headings the pages add before and after the report sections (#90), and the figures and question links they add.
ADDED_H2 = {"results/contrasts": (("holm",), ()), "results/test-order": ((), ("tcp-design",))}
NEW_FIGS = {"results/contrasts": ["fig-7-1"], "results/test-order": ["fig-9-1", "fig-9-2"]}
ADDED_Q = {"results/test-order": 1}
NS = "{http://www.w3.org/2000/svg}"
CLAUSE = re.compile(r"(?:(M|adjusted mutation) )?against (.+?): U (\d+), Holm p ([\d.]+)")
# The run of each contrast section, and the outcome of a cell that names none.
CONTRAST_RUNS = {"planned-contrasts-rep-1": ("rep-1", "adjusted mutation"), "planned-contrasts-rep-2": ("rep-2", None)}
Q20 = re.compile(r"APFD-I on the calls basis was ([\d.]+) for (\w+), ([\d.]+) for (\w+), ([\d.]+) for (\w+), ([\d.]+) "
                 r"for (\w+) and ([\d.]+) for (\w+)\. APFDc-H was ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+) and ([\d.]+) "
                 r"in the same order\.")
# Short number and id columns of the generated tables, which must not split mid-token at phone widths.
SHORT = {"Run", "U", "Holm p", "Order", "APFD-I", "APFDc-H", "Clause", "Risk", "Usage", "Candidate", "Estimate",
         "Stage", "Steps"}


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


def report():
    return snap().files[kalah("snapshot").REPORT]


def page(slug):
    return kalah("pagemap").BY_SLUG[slug]


@functools.cache
def html(slug):
    return (STUDY / slug / "index.html").read_text(encoding="utf-8")


def own(id):
    """The report section of this heading up to its first nested heading with an id."""
    snapshot = kalah("snapshot")
    sec = snapshot.section(report(), id)
    nested = snapshot.HEADING.search(sec, 1)
    return sec[:nested.start()] if nested else sec


def sources(slug):
    return [own(a) for a in page(slug).anchors]


def nodes(slug):
    return list(study().parse(html(slug)).root.iter())


def headings(slug):
    return [n for n in nodes(slug) if study().heading(n)]


def render():
    build = script("build_kalah_tdd_study")
    s = snap()
    idx = kalah("links").index(s)
    return "".join(build.render_page(page(slug), s, idx) for slug in SLUGS)


def main_of(slug):
    return study().parse(html(slug)).ids["main"]


def cells(tr):
    return tuple(" ".join(c.text(" ").split()) for c in tr.elements() if c.tag in ("th", "td"))


def body_rows(table):
    return [cells(tr) for tr in table.iter() if tr.tag == "tr" and tr.closest("tbody")]


def table_after(slug, id):
    """The body rows of the first table outside a figure after the element with this id."""
    seen = False
    for n in main_of(slug).iter():
        seen = seen or n.attrs.get("id") == id
        if seen and n.tag == "table" and not n.closest("figure"):
            return body_rows(n)
    raise AssertionError(f"no table after #{id} on {slug}")


def all_rows(slug):
    return {r for t in main_of(slug).iter() if t.tag == "table" for r in body_rows(t)}


def figure_of(slug, id):
    """(the figure html, its svg parsed)."""
    fig = re.search(rf'<figure id="{id}" .*?</figure>', html(slug), re.S).group(0)
    return fig, ET.fromstring(SVG.search(fig).group(0))


def classes(e):
    return (e.get("class") or "").split()


def marks(root):
    return [e for e in root.iter() if "mk" in classes(e)]


def centre(e):
    return float(e.get("cx")) if e.get("cx") else float(e.get("x")) + float(e.get("width")) / 2


def axis_x(root, lo, hi):
    """The x of a value on the chart's one axis line, which spans lo to hi."""
    line = next(e for e in root.iter(NS + "line") if "axis" in classes(e))
    x0, x1 = float(line.get("x1")), float(line.get("x2"))
    return lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)


def report_clauses():
    """({(run, outcome, method, against): (U, Holm p)} from the report contrast cells and entries, {run: lead text})."""
    out, leads = {}, {}
    for id, (run, default) in CONTRAST_RUNS.items():
        sec = own(id)
        leads[run] = unescape(re.sub(r"<[^>]+>", "", re.search(r"<p>(.*?)</p>", sec, re.S).group(1)))
        found = (re.findall(r'<td data-th="Method">([^<]*)</td>(?:(?!</tr>).)*?<td data-th="Planned contrast">([^<]*)</td>', sec)
                 + re.findall(r'<p class="sub"><b>([^<]*)</b>.*?<p><b>Planned contrast:</b> ([^<]*)</p>', sec, re.S))
        for method, cell in found:
            for clause in unescape(cell).split("; "):
                m = CLAUSE.fullmatch(clause)
                out[(run, m[1] or default, unescape(method), m[2])] = (m[3], m[4])
    return out, leads


def q20_values():
    """{order: (APFD-I, APFDc-H)} as the report Q20 answer states them."""
    answer = re.search(r'<div class="answer" id="q20">(.*?)</div>', report(), re.S).group(1)
    g = Q20.search(" ".join(unescape(re.sub(r"<[^>]+>", " ", answer)).split())).groups()
    return {g[2 * i + 1]: (g[2 * i], g[10 + i]) for i in range(5)}


class Results(unittest.TestCase):
    def test_built_not_stub(self):
        for slug in SLUGS:
            with self.subTest(slug):
                parsed = study().parse(html(slug))
                self.assertFalse(parsed.stub, f"{slug} is a stub")
                levels = [study().heading(h) for h in headings(slug)]
                self.assertEqual(levels.count(1), 1)
                self.assertEqual(levels[0], 1)
                self.assertFalse([b for a, b in zip(levels, levels[1:]) if b > a + 1], f"heading skipped: {levels}")
                ids = [n.attrs["id"] for n in nodes(slug) if n.attrs.get("id")]
                self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
                main = parsed.ids["main"]
                h2 = [n.attrs.get("id") for n in main.iter() if n.tag == "h2"]
                before, after = ADDED_H2.get(slug, ((), ()))
                self.assertEqual(h2, [*before, *page(slug).anchors, *after])
                current = next(n for n in parsed.ids["toc"].iter() if n.attrs.get("aria-current") == "page")
                listed = [a.attrs["href"] for a in current.parent.iter() if a.tag == "a" and a is not current]
                sub = [n.attrs["id"] for n in main.iter() if n.tag in ("h2", "h3") and n.attrs.get("id")]
                self.assertEqual(listed, [f"{BASE}{slug}/#{a}" for a in sub])

    def test_coverage_counts_results(self):
        items, errors = study().inventory(snap().files)
        self.assertEqual(errors, [])
        items = [i for i in items if i.page in SLUGS]
        self.assertEqual(len(items), RESULTS_ITEMS)
        errors, checked = study().coverage(items, {slug: html(slug) for slug in SLUGS})
        self.assertEqual(errors, [])
        self.assertEqual(checked, RESULTS_ITEMS)

    def test_source_figures_numbered(self):
        for slug in SLUGS:
            want = [f for sec in sources(slug) for f in re.findall(r'<figure id="[^"]+">.*?</figure>', sec, re.S)]
            figs = re.findall(r'<figure id="([^"]+)" aria-label="Figure (\d+\.\d+): [^"]*">(.*?)</figure>', html(slug), re.S)
            part = kalah("pagemap").number(slug)
            new = NEW_FIGS.get(slug, [])
            with self.subTest(slug):
                ids = [re.match(r'<figure id="([^"]+)"', w).group(1) for w in want]
                # A headline figure comes first; Figure 9.2 closes the test order page.
                self.assertEqual([f[0] for f in figs], new[:1] + ids + new[1:])
                self.assertEqual([f[1] for f in figs], [f"{part}.{k}" for k in range(1, len(figs) + 1)])
                bodies = {id: body for id, _, body in figs}
                for id, source in zip(ids, want):
                    self.assertEqual(SVG.findall(bodies[id]), SVG.findall(source), id)
                ids = set(study().parse(html(slug)).ids)
                for target in re.findall(r'<a href="#([^"]+)"[^>]*>Data</a>', html(slug)):
                    self.assertIn(target, ids)
        self.assertEqual([len(re.findall(r'<figure id="[^"]+" aria-label="Figure', html(s))) for s in SLUGS], [3, 9, 1, 2])

    def test_section_text_verbatim(self):
        squash = study().squash
        for slug in SLUGS:
            texts = study().parse(html(slug)).texts
            want = [squash(study().Tree(m).root.text()) for sec in sources(slug) for m in P_OR_ENTRY.findall(sec)]
            with self.subTest(slug):
                self.assertTrue(want)
                self.assertEqual([t for t in want if not texts[t]], [])
        main = study().parse(html("results/survey")).ids["main"]
        intro = re.search(r"<p>(.*?)</p>", own("arguments"), re.S).group(1)
        h2 = next(n for n in main.iter() if n.attrs.get("id") == "arguments")
        after = h2.parent.elements()[h2.parent.elements().index(h2) + 1]
        self.assertEqual(squash(after.text()), squash(study().Tree(intro).root.text()))

    def test_free_tables_wrapped(self):
        for slug in SLUGS:
            for table in (n for n in nodes(slug) if n.tag == "table"):
                region = table.closest("div", "table-scroll")
                in_view = table.closest("details") and table.closest("figure")
                with self.subTest(slug):
                    self.assertTrue(in_view or (region and region.attrs.get("role") == "region"
                                                and region.attrs.get("aria-label")), "a free table outside a region")
        main = study().parse(html("results/contrasts")).ids["main"]
        free = [t for t in main.iter() if t.tag == "table" and not t.closest("figure")]
        self.assertEqual(len(free), 3)
        rep1 = [t for t in free if t.closest("div", "table-scroll").attrs.get("aria-label") == "Planned contrasts (rep-1)"]
        self.assertEqual(len(rep1), 2)
        self.assertEqual(len({id(t.closest("div", "table-scroll")) for t in rep1}), 1, "the rep-1 tables share one region")

    def test_short_cells_nowrap(self):
        seen = set()
        for slug in ("results/contrasts", "results/test-order"):
            made = [t for t in main_of(slug).iter() if t.tag == "table" and not t.closest("figure") and not t.classes()]
            for table in made:
                rows = [[c for c in tr.elements() if c.tag in ("th", "td")] for tr in table.iter() if tr.tag == "tr"]
                for i, head in enumerate(" ".join(c.text().split()) for c in rows[0]):
                    with self.subTest(slug, column=head):
                        self.assertEqual({"nowrap" in r[i].classes() for r in rows}, {head in SHORT})
                    seen.add(head)
        self.assertEqual(SHORT - seen, set())

    def test_question_links(self):
        total = 0
        for slug in SLUGS:
            hrefs = re.findall(r'href="([^"]*)"', html(slug))
            q = [h for h in hrefs if re.search(r"#q\d+$", h)]
            want = sum(len(re.findall(r'href="#q\d+"', sec)) for sec in sources(slug)) + ADDED_Q.get(slug, 0)
            with self.subTest(slug):
                self.assertEqual(len(q), want)
                self.assertEqual([h for h in q if not re.fullmatch(rf"{BASE}questions/#q\d+", h)], [])
                self.assertEqual([h for h in hrefs if "report.html" in h], [])
            total += want
        self.assertGreater(total, 0)

    def test_refuses_unknown_block(self):
        results = kalah("pages.results")
        for block in ("<ul><li>b</li></ul>", "stray text", '<div class="shaped"><table></table><div class="entry"></div></div>',
                      '<p class="lead">x</p>'):
            with self.subTest(block), self.assertRaises(ValueError) as caught:
                results.split("made-up", f'<h3 id="made-up">Made up</h3><p>a</p>{block}<p>c</p>')
            self.assertIn("made-up", str(caught.exception))
            self.assertIn(block[:12], str(caught.exception))
        kinds = [k for k, _ in results.split("made-up", '<h3 id="made-up">Made up</h3>\n<p>a</p>\n'
                                                       '<div class="shaped"><div class="entry"><p>e</p></div></div>')]
        self.assertEqual(kinds, ["p", "entries"])

    def test_contrasts_lead_links_landing(self):
        main = study().parse(html("results/contrasts")).ids["main"]
        lead = main.elements()[0]
        self.assertEqual(lead.tag, "p")
        self.assertEqual([a.attrs["href"] for a in lead.iter() if a.tag == "a"], [f"{BASE}#rep-1-mutation"])
        self.assertEqual(kalah("links").index(snap())[kalah("snapshot").REPORT]["rep-1-mutation"], ("", "rep-1-mutation"))
        self.assertNotIn('id="rep-1-mutation"', html("results/contrasts"))

    def test_deterministic(self):
        # Set order follows the hash seed, so a second process with another seed shows any order the pages rely on.
        # -I would ignore PYTHONHASHSEED, so the child gets -s -P, the parent's -B and an environment of the seed alone.
        seed = "1" if os.environ.get("PYTHONHASHSEED") == "0" else "0"
        flags = ["-s", "-P"] + ["-B"] * sys.flags.dont_write_bytecode
        child = subprocess.run([sys.executable, *flags, __file__, "--render"], env={"PYTHONHASHSEED": seed},
                               capture_output=True, check=False)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        mine = render()
        self.assertNotIn("kalah-tdd-stub", mine)
        self.assertEqual(child.stdout, mine.encode())

    def test_contrast_holm_from_tables(self):
        clauses, leads = report_clauses()
        rows = table_after("results/contrasts", "contrast-holm")
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(clauses), 16)
        norm = lambda outcome: outcome if outcome == "M" else outcome.lower()
        for run, outcome, contrast, u, p in rows:
            with self.subTest(contrast, outcome=outcome):
                a, b = contrast.split(" against ")
                self.assertEqual(clauses[(run, norm(outcome), a, b)], (u, p))
                other_u, other_p = clauses[(run, norm(outcome), b, a)]
                self.assertEqual(other_p, p)
                self.assertEqual(int(u) + int(other_u), 25, "U of both sides sums to 5 by 5 replicates")
                self.assertRegex(leads[run], rf"Holm p {re.escape(p)}(?!\d)")
        self.assertEqual({(r[0], norm(r[1]), frozenset(r[2].split(" against "))) for r in rows},
                         {(run, o, frozenset((a, b))) for run, o, a, b in clauses})

    def test_contrast_refuses_mismatch(self):
        results = kalah("pages.results")
        self.assertEqual(len(results.holm(report())), 8)
        cases = {"side p": ("against Anchor Engineering: U 0, Holm p 0.016", "against Anchor Engineering: U 0, Holm p 0.017"),
                 "side U": ("against Anchor Engineering: U 0, Holm p 0.016", "against Anchor Engineering: U 1, Holm p 0.016"),
                 "one side dropped": ("; adjusted mutation against Coarse-to-fine TDD: U 14, Holm p 1.000", ""),
                 "lead": ("U 25 and Holm p 0.016", "U 25 and Holm p 0.018")}
        for name, (old, new) in cases.items():
            with self.subTest(name), self.assertRaises(ValueError) as caught:
                self.assertIn(old, report())
                results.holm(report().replace(old, new))
            self.assertRegex(str(caught.exception), "Anchor Engineering|Coarse-to-fine TDD")
        # Both sides of Held-out TDD's contrast give Holm p 0.02, which the lead's 0.024 must not pass for.
        prefix = report()
        for old in ("against Classic greedy TDD: U 0, Holm p 0.024", "against Held-out TDD: U 25, Holm p 0.024"):
            self.assertEqual(prefix.count(old), 1)
            prefix = prefix.replace(old, old.removesuffix("4"))
        with self.assertRaises(ValueError) as caught:
            results.holm(prefix)
        self.assertIn("Held-out TDD", str(caught.exception))
        both = report().replace("; adjusted mutation against Coarse-to-fine TDD: U 14, Holm p 1.000", "").replace(
            "; adjusted mutation against Classic greedy TDD: U 11, Holm p 1.000", "")
        with self.assertRaises(ValueError) as caught:
            results.holm(both)
        self.assertIn("rep-2", str(caught.exception))
        self.assertIn("Coarse-to-fine TDD", str(caught.exception))

    def test_f71_headline_first(self):
        main = main_of("results/contrasts")
        figs = [n for n in main.iter() if n.tag == "figure"]
        self.assertEqual(figs[0].attrs["id"], "fig-7-1")
        self.assertTrue(figs[0].attrs["aria-label"].startswith("Figure 7.1: "))
        heads = [n for n in main.iter() if study().heading(n)]
        self.assertEqual([h.attrs.get("id") for h in heads[:2]], ["holm", None])
        self.assertIs(figs[0].closest("section"), heads[0].parent)
        table_head = next(h for h in heads if h.attrs.get("id") == "contrast-holm")
        self.assertEqual((table_head.tag, table_head.parent), ("h3", heads[0].parent))
        fig, root = figure_of("results/contrasts", "fig-7-1")
        mk = marks(root)
        self.assertEqual(len(mk), 8)
        p = [float(re.search(r"Holm p ([\d.]+)", e.find(NS + "title").text).group(1)) for e in mk]
        self.assertEqual(sorted(p), sorted(float(r[4]) for r in table_after("results/contrasts", "contrast-holm")))
        self.assertEqual([("hollow" in classes(e)) for e in mk], [v >= 0.05 for v in p])
        ref = [e for e in root.iter(NS + "line") if "refline" in classes(e)]
        self.assertEqual(len(ref), 1)
        self.assertAlmostEqual(float(ref[0].get("x1")), axis_x(root, 0, 1)(0.05), delta=0.1)
        self.assertEqual(len(re.findall(r"<li>", fig)), 8)
        self.assertEqual(re.findall(r'<a href="([^"]+)" aria-label="Data for Figure 7.1">', fig), ["#contrast-holm"])

    def test_dots_svg(self):
        dots = kalah("figures.dots")
        unsafe = 'a <b> & "c"'
        two = [dots.Mark(unsafe, 0, "lo " + unsafe), dots.Mark(unsafe, 0.5, "mid", series=1, hollow=True),
               dots.Mark("c", 1, "hi")]
        root = ET.fromstring(dots.svg("L " + unsafe, "Axis " + unsafe, ("one", unsafe), two, (0, 1), (0, 0.5, 1),
                                      [dots.Ref(0.25, "ref " + unsafe)]))
        self.assertIn("plot", classes(root))
        mk = marks(root)
        self.assertEqual([e.find(NS + "title").text for e in mk], ["lo " + unsafe, "mid", "hi"])
        xs = [centre(e) for e in mk]
        self.assertAlmostEqual(xs[1] - xs[0], xs[2] - xs[1])
        grid = [float(e.get("x1")) for e in root.iter(NS + "line") if "grid" in classes(e)]
        self.assertEqual(grid, xs)
        self.assertEqual([e.tag for e in mk], [NS + "circle", NS + "rect", NS + "circle"])
        self.assertEqual(["hollow" in classes(e) for e in mk], [False, True, False])
        kids = list(root)
        axes = [i for i, e in enumerate(kids) if "axis" in classes(e)]
        self.assertEqual(len(axes), 1)
        after = kids[axes[0] + 1]
        self.assertEqual((after.tag, after.get("text-anchor"), after.text), (NS + "text", "middle", "Axis " + unsafe))
        self.assertAlmostEqual(float([e for e in root.iter(NS + "line") if "refline" in classes(e)][0].get("x1")),
                               axis_x(root, 0, 1)(0.25), delta=0.1)
        texts = ["".join(t.itertext()) for t in root.iter(NS + "text")]
        self.assertIn(unsafe, texts)
        self.assertIn("ref " + unsafe, texts)
        self.assertEqual([t for t in root.iter(NS + "text") if {"s1", "s2"} & set(classes(t))], [])
        self.assertEqual(len([g for g in root.iter(NS + "g") if "key" in classes(g)]), 1)
        one = ET.fromstring(dots.svg("L", "A", ("one",), [dots.Mark("r", 0.2, "t")], (0, 1), (0, 1)))
        self.assertEqual([g for g in one.iter(NS + "g") if "key" in classes(g)], [])
        for bad in ([dots.Mark("r", 1.5, "t")], [dots.Mark("r", 0.5, "t", series=1)]):
            with self.subTest(bad), self.assertRaises(ValueError):
                dots.svg("L", "A", ("one",), bad, (0, 1), (0, 1))

    def test_order_facts_on_page(self):
        facts = snap().facts
        tcp = facts["runs"]["tcp-1"]["tcp"]
        rows, texts = all_rows("results/test-order"), study().parse(html("results/test-order")).texts
        for c in tcp["list"]["clauses"]:
            self.assertIn((c["id"], str(c["risk"]), str(c["usage"])), rows)
        for c in tcp["list"]["candidates"]:
            self.assertIn((c["id"], ", ".join(c["checks"]), ", ".join(c["relies"]) or "none", str(c["estimate"])), rows)
        arms = {m["order"]: arm for arm, m in facts["runs"]["tcp-1"]["methods"].items()}
        self.assertEqual(len(arms), 5)
        for name, order in tcp["orders"].items():
            self.assertIn((name, arms.get(name, "not run"), ", ".join(order)), rows)
        steps = facts["runs"]["tcp-1-list"]["list_phase"] + facts["runs"]["tcp-1"]["methods"]["tcp-1-r01"]["steps"]
        self.assertEqual(len(steps), 10)
        notes = [s["note"] for s in facts["stages"]["tcp-random"]["stages"] if "note" in s]
        self.assertEqual([t for t in steps + notes if not texts[study().squash(t)]], [])
        doc = kalah("snapshot").run_doc
        settings = {("Seed", str(tcp["seed"])), ("Lister", tcp["lister"]), ("List run", tcp["list_tag"]),
                    ("List sha", tcp["sha"][:8])} | {(f"Methods doc, {r}", doc(snap(), r))
                                                     for r in ("tcp-1", "tcp-1-list", "tcp-1-list2")}
        self.assertEqual(settings - rows, set())
        self.assertEqual({doc(snap(), r) for r in ("tcp-1", "tcp-1-list", "tcp-1-list2")}, {"1f11dd37", "12f026f6"})

    def test_order_refuses_mismatch(self):
        results = kalah("pages.results")
        self.assertEqual(len(results.tcp_stages(snap().facts)), 2)
        self.assertEqual(sum(a is None for a in results.tcp_orders(snap().facts).values()), 2)
        stages = copy.deepcopy(snap().facts)
        stages["stages"]["tcp-risk"]["stages"][1]["unit"] = "clause"
        missing = copy.deepcopy(snap().facts)
        del missing["runs"]["tcp-1"]["tcp"]["orders"]["cost"]
        unknown = copy.deepcopy(snap().facts)
        unknown["runs"]["tcp-1"]["tcp"]["orders"]["random"][0] = "T99"
        steps = copy.deepcopy(snap().facts)
        steps["runs"]["tcp-1"]["methods"]["tcp-1-r02"]["steps"][0] += " changed"
        shared = copy.deepcopy(snap().facts)
        self.assertEqual(shared["runs"]["tcp-1"]["methods"]["tcp-1-r01"]["order"], "random")
        shared["runs"]["tcp-1"]["methods"]["tcp-1-r02"]["order"] = "random"
        for name, call, facts, said in (("stages", results.tcp_stages, stages, ["tcp-risk"]),
                                        ("steps", results.tcp_stages, steps, ["tcp-1-r02"]),
                                        ("arm order", results.tcp_orders, missing, ["tcp-1-r03"]),
                                        ("shared order", results.tcp_orders, shared, ["tcp-1-r01", "tcp-1-r02"]),
                                        ("candidate", results.tcp_orders, unknown, ["T99"])):
            with self.subTest(name):
                with self.assertRaises(ValueError) as caught:
                    call(facts)
                for s in said:
                    self.assertIn(s, str(caught.exception))
        q20 = copy.deepcopy(snap().facts)
        q20["runs"]["tcp-1"]["methods"]["tcp-1-r05"]["order"] = "costOnly"
        with self.assertRaises(ValueError) as caught:
            results.tcp_results(report(), q20, "results/test-order", kalah("links").index(snap()), "9.1")
        self.assertIn("Q20 orders", str(caught.exception))

    def test_q20_values(self):
        results = kalah("pages.results")
        want = q20_values()
        self.assertEqual(list(want), ["random", "coverage", "cost", "risk", "usage"])
        self.assertEqual(results.q20(report()), want)
        _, root = figure_of("results/test-order", "fig-9-1")
        ticks = [float(t.text) for t in root.iter(NS + "text") if re.fullmatch(r"[\d.]+", t.text or "")]
        x = axis_x(root, min(ticks), max(ticks))
        got = {(e.find(NS + "title").text, round(centre(e), 1), "hollow" in classes(e)) for e in marks(root)}
        rand = want["random"]
        self.assertEqual(got, {(f"{order}: {name} {v[i]}", round(x(float(v[i])), 1), float(v[i]) <= float(rand[i]))
                               for order, v in want.items() if order != "random"
                               for i, name in enumerate(("APFD-I", "APFDc-H"))})
        ref = sorted(float(e.get("x1")) for e in root.iter(NS + "line") if "refline" in classes(e))
        self.assertEqual(ref, sorted(round(x(float(v)), 1) for v in rand))
        self.assertEqual({r[0] for r in table_after("results/test-order", "tcp-results")}, set(want))
        self.assertEqual(set(table_after("results/test-order", "tcp-results")), {(o, *v) for o, v in want.items()})
        with self.assertRaises(ValueError) as caught:
            results.q20(report().replace("in the same order", "in that order"))
        self.assertIn("Q20", str(caught.exception))

    def test_f92_flow(self):
        checks = script("check_kalah_tdd_flow")
        fig, root = figure_of("results/test-order", "fig-9-2")
        boxes = checks.node_boxes(root)
        self.assertEqual(len(boxes), len(re.findall(r"<li>", fig)))
        self.assertEqual(len(boxes), len(snap().facts["stages"]["tcp-random"]["stages"]))
        texts = ["".join(t.itertext()) for t in root.iter(NS + "text")]
        self.assertIn("repeat per candidate", texts)
        ids = [e.get("id") for e in root.iter() if e.get("id")]
        self.assertTrue(ids)
        self.assertEqual([i for i in ids if not i.startswith("f9-")], [])
        paths = [p for p in root.iter(NS + "path") if p.get("class") in ("edge", "loop")]
        self.assertEqual([p.get("class") for p in paths], ["loop"])
        for p in paths:
            pts = checks.points(p.get("d"))
            self.assertTrue(any(checks.on_edge(pts[0], b) for b in boxes) and any(checks.on_edge(pts[-1], b) for b in boxes))
            self.assertEqual([b for a, c in zip(pts, pts[1:]) for b in boxes if checks.crosses(a, c, b)], [])
        labels = checks.label_boxes(root)
        self.assertEqual(len(labels), 1)
        self.assertEqual([s for s, box in labels for b in boxes if checks.overlap(box, b)], [])
        self.assertEqual(re.findall(r'<a href="([^"]+)" aria-label="Data for Figure 9.2">', fig), ["#tcp-stages"])
        self.assertEqual(len(table_after("results/test-order", "tcp-stages")), 2)


if __name__ == "__main__":
    if sys.argv[1:] == ["--render"]:
        sys.stdout.buffer.write(render().encode())
    else:
        unittest.main()
