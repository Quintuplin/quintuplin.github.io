#!/usr/bin/env python3
"""Check the Kalah TDD methodology page (#64): every stage, run, collect step, review criterion, prompt and test list
from facts.json is on the committed page, and Figure F8 matches the facts and keeps its routes clear.

Usage: check_kalah_tdd_page_methodology.py
"""
import functools
import importlib
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PAGE = SCRIPTS.parent / "studies/kalah-tdd-study/methodology/index.html"
BASE = "/studies/kalah-tdd-study/"
# The methods doc each run was built under (recomputed from doc_sha256 in G6).
DOCS = {"full-1": "64606950", "pilot-1": "64606950", "pilot-2": "64606950", "tcp-1": "1f11dd37",
        "tcp-1-list": "1f11dd37", "rep-1": "12f026f6", "rep-2": "12f026f6", "rep-2/rebuild": "12f026f6",
        "tcp-1-list2": "12f026f6"}
FAMILIES = ("Baseline", "Structure first", "Step size", "Search and validation", "Test-list order")
DISPOSITION = re.compile(r"<b>([^<]+)</b>\. Channel: (\w+)\. High flags: (\d+)\. Verdict: ([^.]+)\.")


@functools.cache
def mod(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)


@functools.cache
def snap():
    return mod("kalah_tdd.snapshot").load()


def facts():
    return snap().facts


@functools.cache
def html():
    return PAGE.read_text(encoding="utf-8")


@functools.cache
def root():
    return mod("check_kalah_tdd_study").parse(html()).root


def spaced(node):
    return " ".join(node.text(" ").split())


def squash(text):
    return "".join(text.split())


def section(id):
    """The section element headed by the h2 with this id."""
    head = next(n for n in root().iter() if n.tag == "h2" and n.attrs.get("id") == id)
    return head.closest("section")


def tables(node, label):
    """Rows of cell texts of each table whose scroll region aria-label starts with label."""
    out = []
    for region in node.iter():
        if region.attrs.get("role") == "region" and region.attrs.get("aria-label", "").startswith(label) \
                and "table-scroll" in region.classes():
            out += [[spaced(td) for td in tr.elements() if td.tag == "td"] for tr in region.iter() if tr.tag == "tr"
                    and any(td.tag == "td" for td in tr.elements())]
    return out


def rows(node, label):
    found = tables(node, label)
    if not found:
        raise AssertionError(f"no table labelled {label!r}")
    return found


def items(node, label):
    ol = next(n for n in node.iter() if n.tag == "ol" and n.attrs.get("aria-label") == label)
    return [spaced(li) for li in ol.elements() if li.tag == "li"]


def terms(node, label):
    """(dt, dd) texts of the dl with this aria-label."""
    dl = next(n for n in node.iter() if n.tag == "dl" and n.attrs.get("aria-label") == label)
    kids = dl.elements()
    return [(spaced(dt), spaced(dd)) for dt, dd in zip(kids[::2], kids[1::2])]


def unmark(text):
    return text.replace("**", "").replace("`", "")


def design(method):
    return next(d for d, s in facts()["stages"].items() if s["method"] == method)


def method_name(d):
    return facts()["stages"][d]["method"]


def families():
    """Method name to family, from the methodologies Summary table."""
    text = next(s["text"] for s in facts()["analysis"]["methodologies"] if s["title"] == "Summary")
    return {cells[0]: cells[1] for line in text.splitlines()[2:]
            if (cells := [c.strip() for c in line.strip("|").split("|")])}


def changes():
    """(run, build, design, stage id, field, value as run) for each stage field a run recorded unlike stages.json."""
    out = []
    for run, r in facts()["runs"].items():
        for build, m in r["methods"].items():
            d = m.get("arm") or design(m["method"])
            now = {st["id"]: st for st in facts()["stages"][d]["stages"]}
            for st in m["stages"]:
                for field in sorted(set(st) | set(now[st["id"]])):
                    if st.get(field) != now[st["id"]].get(field):
                        out.append((run, build, d, st["id"], field, st.get(field)))
    return out


def shown(value):
    return " ".join(" ".join(str(v).split()) for v in value) if isinstance(value, list) else " ".join(str(value).split())


def leaves(schema):
    """(criterion title, item title) for each scored item of the review schema."""
    out = []
    for crit in schema["properties"].values():
        subs = crit["properties"]
        if "score" in subs:
            out.append((crit["title"], crit["title"]))
        else:
            out += [(crit["title"], sub["title"]) for sub in subs.values()]
    return out


def dispositions():
    return DISPOSITION.findall(mod("kalah_tdd.snapshot").section(snap().files[mod("kalah_tdd.snapshot").REPORT],
                                                                  "audit-flag-dispositions"))


def roles():
    return mod("kalah_tdd.pages.harness").roles(snap())


@functools.cache
def svg():
    fig = re.search(r'<figure id="f8".*?</figure>', html(), re.S).group(0)
    return ET.fromstring(re.search(r"<svg\b.*?</svg>", fig, re.S).group(0))


def figure():
    return next(n for n in root().iter() if n.tag == "figure" and n.attrs.get("id") == "f8")


class Data(unittest.TestCase):
    def test_snapshot_counts(self):
        f = facts()
        self.assertEqual(len(f["stages"]), 18)
        self.assertEqual(sum(len(s["stages"]) for s in f["stages"].values()), 58)
        self.assertEqual(len({(run, build) for run, build, *_ in changes()}), 16)
        self.assertEqual(len(f["runs"]), 9)
        self.assertEqual([len(f["pipeline"]["collect"][k]) for k in ("collectOne", "collectList")], [16, 7])
        self.assertEqual(len({json.dumps(r["review_schema"], sort_keys=True) for r in f["runs"].values()}), 1)
        self.assertEqual(len(leaves(f["runs"]["full-1"]["review_schema"])), 11)
        self.assertEqual((len(dispositions()), sum(int(d[2]) for d in dispositions())), (3, 10))

    def test_every_stage_on_page(self):
        f, fam, sec = facts(), families(), section("stages")
        seen = 0
        for family in FAMILIES:
            got = rows(sec, f"Stages: {family}")
            want = [(d, st) for d, s in f["stages"].items() if fam[s["method"]] == family for st in s["stages"]]
            self.assertEqual(len(got), len(want), family)
            for cells, (d, st) in zip(got, want):
                with self.subTest(d, stage=st["id"]):
                    rules = ([f"commit cap {st['commit_cap']}"] if "commit_cap" in st else []) + \
                            ([f"if {st['when']}"] if "when" in st else []) + \
                            [f"with {method_name(w)} steps {', '.join(map(str, n))}" for w, n in st.get("with", {}).items()]
                    self.assertEqual(cells[:2], [method_name(d), st["id"]])
                    self.assertEqual(cells[2].split()[0], st["kind"])
                    self.assertEqual(cells[3:], [", ".join(map(str, st["steps"])) or "none", st.get("unit", "none"),
                                                 st.get("returns", "none"), "; ".join(rules) or "none"])
            notes = [(f"{method_name(d)} {st['id']}", shown(st["note"])) for d, st in want if "note" in st]
            self.assertEqual(terms(sec, f"Stage notes: {family}") if notes else [], notes, family)
            seen += len(got)
        self.assertEqual(seen, 58)

    def test_every_run_stage_change_on_page(self):
        got = rows(section("stages"), "Stages as run")
        for run, build, d, stage, field, value in changes():
            with self.subTest(run, build=build, stage=stage, field=field):
                match = [c for c in got if c[1:] == [method_name(d), stage, field, shown(value)]
                         and f"{run} {build}" in c[0].split(", ")]
                self.assertEqual(len(match), 1)
        self.assertEqual(sum(len(c[0].split(", ")) for c in got), len(changes()))

    def test_every_run_recorded(self):
        f, s = facts(), snap()
        got = rows(section("runs"), "Runs")
        self.assertEqual([c[0] for c in got], list(f["runs"]))
        for cells, (run, r) in zip(got, f["runs"].items()):
            with self.subTest(run):
                caps = r["caps"]
                waves = "; ".join(f"wave {k}: {', '.join(w)}" for k, w in enumerate(r.get("waves", []), 1)) or "none"
                self.assertEqual(cells[1:7], [r["tag"], str(len(r["methods"])), r["model"], r["effort"],
                                              f"iterations {caps['iterations']}, cycles {caps['cycles']}, starts {caps['starts']}",
                                              waves])
                self.assertEqual(cells[7].split()[0], DOCS[run])
                self.assertEqual("methods text on this site" in cells[7], DOCS[run] == s.doc)
                self.assertEqual(cells[8], ", ".join(f["dropped"][run]))
        versions = rows(section("runs"), "Harness versions")
        built = [(run, r) for run, r in f["runs"].items() if r.get("harness")]
        self.assertEqual([c[0] for c in versions], [run for run, _ in built])
        for cells, (run, r) in zip(versions, built):
            h = r["harness"]
            delta = (r.get("harness_delta") or {}).get("sha256", "none")
            self.assertEqual(cells[1:], [h["commit"], h["engine_sha256"], h["runner_tree"], h["claude_version"],
                                         h["guard_base"], delta])

    def test_notation_sentences_kept(self):
        # A sentence split on every period once broke "args.json" into "args. json".
        text = spaced(section("how-a-design-runs"))
        for sentence in re.split(r"(?<=\.) (?=[A-Z])", facts()["pipeline"]["notation"].removesuffix(" Tag: verified.")):
            self.assertIn(sentence, text)

    def test_collect_steps_in_order(self):
        sec = section("collect-audit")
        for name, steps in facts()["pipeline"]["collect"].items():
            with self.subTest(name):
                self.assertEqual(items(sec, f"{name} steps"),
                                 [s["name"] + (" skippable" if s["skippable"] else "") for s in steps])
        # The intro once said only that skippable steps can be skipped. It names when instead.
        intro = spaced(next(n for n in sec.iter() if n.tag == "p"))
        self.assertIn("fetchBack", intro)
        self.assertTrue(intro.endswith("verified"), intro)

    def test_review_schema_complete(self):
        schema, sec = facts()["runs"]["full-1"]["review_schema"], section("blind-review")
        text = squash(spaced(sec))
        for part in (schema["title"], schema["description"]):
            self.assertIn(squash(part), text)
        for crit in schema["properties"].values():
            self.assertIn(squash(f"{crit['title']} {crit['description']}"), text)
        got = rows(sec, "Blind review criteria")
        self.assertEqual([c[:2] for c in got], [[item, crit] for crit, item in leaves(schema)])
        self.assertEqual({tuple(c[2:]) for c in got}, {("1 to 5", "1 to 400 characters")})
        self.assertIn(f'href="{BASE}data/ratings/"', html())

    def test_prompts_and_list_phase(self):
        f, sec = facts(), section("prompts")
        text = squash(spaced(sec))
        for run, r in f["runs"].items():
            if "list_phase" in r:
                self.assertEqual(items(sec, f"{run} list phase"), [" ".join(s.split()) for s in r["list_phase"]])
            for key, value in r.get("tcp", {}).items():
                if key not in ("list", "orders"):
                    self.assertIn(squash(f"{key} {value}"), text, (run, key))
        tcp = f["runs"]["tcp-1"]
        self.assertEqual(rows(sec, "tcp-1 arms"), [[b, m["arm"], m["prompt"], m["order"], m["blind"]]
                                                   for b, m in tcp["methods"].items()])
        self.assertEqual(rows(sec, "tcp-1 candidate orders"), [[o, ", ".join(c)] for o, c in tcp["tcp"]["orders"].items()])
        lst = tcp["tcp"]["list"]
        self.assertEqual(rows(sec, "Clauses"), [[c["id"], str(c["risk"]), str(c["usage"])] for c in lst["clauses"]])
        self.assertEqual(rows(sec, "Candidates"), [[c["id"], ", ".join(c["checks"]), ", ".join(c["relies"]) or "none",
                                                    str(c["estimate"])] for c in lst["candidates"]])

    def test_held_out_text_kept(self):
        sec = section("held-out-split")
        text = squash(spaced(sec))
        held = next(s["text"] for s in facts()["analysis"]["methodologies"] if s["title"] == "Held-out TDD")
        steps = [re.sub(r"^\d+\. ", "", line) for line in held.splitlines() if re.match(r"\d+\. ", line)]
        self.assertEqual(len(steps), 8)
        self.assertEqual(items(sec, "Held-out TDD steps"), [unmark(s) for s in steps])
        for para in held.split("\n\n"):
            self.assertIn(squash(unmark(re.sub(r"(?m)^\d+\. ", "", para))), text)
        for st in facts()["stages"]["held-out"]["stages"]:
            if st["id"] in ("s2", "s3"):
                self.assertIn(squash(st["note"]), text)

    def test_disposition_summary_matches_report(self):
        sec = section("collect-audit")
        found = dispositions()
        self.assertEqual(rows(sec, "Audit flag dispositions"), [list(d) for d in found])
        self.assertIn(f"{len(found)} rows judge {sum(int(d[2]) for d in found)} high flags", spaced(sec))
        self.assertIn(f'href="{BASE}data/#audit-flag-dispositions"', html())

    def test_page_is_built(self):
        r = root()
        self.assertFalse(mod("check_kalah_tdd_study").parse(html()).stub)
        self.assertEqual(sum(1 for n in r.iter() if n.tag == "h1"), 1)
        tables_ = [n for n in r.iter() if n.tag == "table"]
        self.assertGreater(len(tables_), 10)
        for t in tables_:
            p = t.parent
            with self.subTest(table=spaced(t)[:40]):
                self.assertIn("table-scroll", p.classes())
                self.assertEqual((p.attrs.get("role"), p.attrs.get("tabindex")), ("region", "0"))
                self.assertTrue(p.attrs.get("aria-label"))
        for th in (n for n in r.iter() if n.tag == "th"):
            self.assertIn(th.attrs.get("scope"), ("col", "row"))
        for td in (n for t in tables_ for n in t.iter() if n.tag == "td"):
            self.assertTrue(td.attrs.get("data-th"))
        sections = [n for n in r.iter() if n.tag == "section"]
        self.assertEqual(len(sections), 8)
        for s in sections:
            with self.subTest(s.attrs.get("aria-labelledby")):
                self.assertTrue(any(n.tag == "span" and "tag" in n.classes() for n in s.iter()))


class AgentRoles(unittest.TestCase):
    NS = "{http://www.w3.org/2000/svg}"

    def test_text_version_matches(self):
        nodes, _, _ = roles()
        rects = [r for r in svg().iter(self.NS + "rect") if r.get("class") == "node"]
        details = next(n for n in figure().iter() if n.tag == "details")
        lis = [spaced(li) for li in details.iter() if li.tag == "li"]
        self.assertEqual(len(rects), len(lis))
        self.assertEqual(len(rects), len(nodes))
        for li, n in zip(lis, nodes):
            self.assertTrue(li.startswith(n.label), (li, n.label))
        self.assertIsNotNone(svg().find(self.NS + "title"))
        self.assertIsNotNone(svg().find(self.NS + "desc"))
        ids = re.findall(r'\bid="([^"]*)"', ET.tostring(svg(), encoding="unicode"))
        self.assertTrue(ids)
        self.assertEqual([i for i in ids if not i.startswith("f8-")], [])

    def test_from_facts(self):
        f = facts()
        nodes = {n.id: n for n in roles()[0]}
        stages = [st for s in f["stages"].values() for st in s["stages"]]
        kinds = {k: sum(1 for st in stages if st["kind"] == k) for k in ("S", "L", "F", "H", "starts")}
        self.assertEqual(kinds, {"S": 32, "L": 15, "F": 9, "H": 1, "starts": 1})
        units = sorted({st["unit"] for st in stages if st["kind"] == "L"})
        separate = [st["id"] for st in stages if st.get("note", "").startswith("You are the separate agent")]
        starts = {r["caps"]["starts"] for r in f["runs"].values()}
        self.assertEqual(len(starts), 1)
        builds = sum(len(r["methods"]) for r in f["runs"].values())
        steps = {k: [s["name"] for s in v] for k, v in f["pipeline"]["collect"].items()}
        found = dispositions()
        want = {"clone": f"{builds} builds in {len(f['runs'])} runs", "throughout": f"{kinds['F']} stages join every prompt",
                "once": f"{kinds['S']} stages", "harness": f"{kinds['H']} stage",
                "repeat": f"{kinds['L']} stages, units {', '.join(units)}",
                "starts": f"{kinds['starts']} stage, up to {starts.pop()} starts",
                "writer": f"{len(separate)} stages: {', '.join(separate)}",
                "collect": f"collectOne {len(steps['collectOne'])} steps, collectList {len(steps['collectList'])}",
                "audit": f"collectOne step {steps['collectOne'].index('audit') + 1}",
                "review": f"collectOne step {steps['collectOne'].index('review') + 1}",
                "report": f"{len(found)} disposition rows judge {sum(int(d[2]) for d in found)} high flags"}
        self.assertEqual({k: n.note for k, n in nodes.items()}, want)
        for step in ("audit", "review", "report"):
            self.assertIn(step, steps["collectOne"])

    def test_routes_clear(self):
        flow = mod("check_kalah_tdd_flow")
        nodes, edges, loops = roles()
        root = svg()
        boxes = dict(zip([n.id for n in nodes], flow.node_boxes(root)))
        ends = [(e.src, e.dst) for e in edges] + [(lp.node, lp.back_to or lp.node) for lp in loops]
        paths = [p for p in root.iter(self.NS + "path") if p.get("class") in ("edge", "loop")]
        self.assertEqual(len(paths), len(ends))
        segments = []
        for (src, dst), p in zip(ends, paths):
            pts = flow.points(p.get("d"))
            segments += list(zip(pts, pts[1:]))
            with self.subTest(path=p.get("d")):
                self.assertTrue(flow.on_edge(pts[0], boxes[src]) and flow.on_edge(pts[-1], boxes[dst]))
                self.assertEqual([i for a, b in zip(pts, pts[1:]) for i, box in boxes.items() if flow.crosses(a, b, box)], [])
        labels = flow.label_boxes(root)
        self.assertEqual(len(labels), sum(1 for e in edges if e.label) + len(loops))
        for i, (s, box) in enumerate(labels):
            with self.subTest(label=s):
                self.assertEqual([n for n in boxes.values() if flow.overlap(box, n)], [])
                self.assertEqual([t for t, other in labels[i + 1:] if flow.overlap(box, other)], [])
                self.assertEqual([(a, b) for a, b in segments if flow.crosses(a, b, box)], [])

    def test_layout_limits(self):
        f = mod("kalah_tdd.figures.flow")
        nodes, edges, loops = roles()
        self.assertTrue(all(n.col is not None for n in nodes))
        _, cell = f.cells(nodes)
        row = {i: c // f.COLS for i, (_, c) in cell.items()}
        wraps = [(row[e.src], row[e.dst]) for e in edges if row[e.src] != row[e.dst]]
        self.assertEqual(wraps, [(0, 1)])
        self.assertTrue(all(len(e.label) <= 10 for e in edges), [e.label for e in edges])
        self.assertTrue(all(row[lp.node] == row[lp.back_to or lp.node] for lp in loops))

    def test_figure_wrapped(self):
        fig = figure()
        num = next(n for n in fig.iter() if n.tag == "p" and "fig-n" in n.classes())
        self.assertEqual(spaced(num), f"Figure {mod('kalah_tdd.pagemap').number('methodology')}.1")
        self.assertTrue(any(n.tag == "figcaption" for n in fig.iter()))
        details = next(n for n in fig.iter() if n.tag == "details")
        self.assertEqual(details.attrs.get("id"), "f8-data")
        self.assertTrue(spaced(next(n for n in details.iter() if n.tag == "summary")).startswith("Text version"))
        data = [n.attrs["href"] for n in fig.iter() if n.tag == "a" and spaced(n) == "Data"]
        self.assertEqual(data, ["#f8-data"])
        region = next(n for n in fig.iter() if "diagram" in n.classes())
        self.assertEqual((region.attrs.get("role"), region.attrs.get("tabindex")), ("region", "0"))

    def test_role_labels_from_report(self):
        report = re.sub(r"<[^>]+>", " ", snap().files[mod("kalah_tdd.snapshot").REPORT])
        got = rows(section("agent-roles"), "Agent roles")
        self.assertEqual(len(got), 4)
        for cells in got:
            for label in cells[2].split(", "):
                with self.subTest(label):
                    self.assertRegex(report, rf"(?<![\w:-]){re.escape(label)}(?![\w-])")


if __name__ == "__main__":
    unittest.main()
