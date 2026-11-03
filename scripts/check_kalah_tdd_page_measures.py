#!/usr/bin/env python3
"""Check the Kalah TDD measures page (#84): metric cards kept from the snapshot, dfns, formulas, doc versions,
refusals, Figure 4.1 and the column index.

Usage: check_kalah_tdd_page_measures.py
"""
import copy
import functools
import importlib
import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
SLUG = "methodology/measures"
HEADINGS = ["measurement-pipeline", "columns", "tests", "static-analysis-and-mutation", "size-and-speed", "cost",
            "review-ratings", "combined-and-consistency", "records", "test-order-measures", "table-fields",
            "builds-and-methods", "contrasts-and-tests", "ratings", "run-records", "test-list-and-stages", "column-index"]
# Labels the G10b results pages add from facts, outside the snapshot report, by the page G10-plan.md gives them.
G10B_LABELS = {"results/contrasts": {"figure title": ("Holm p of each planned contrast",), "axis label": ("Holm p",),
                                     "table header": ("Run", "Outcome", "Contrast", "U", "Holm p")},
               "results/test-order": {"figure title": ("APFD-I and APFDc-H by test-list order", "Stage flow of a tcp-1 arm"),
                                      "axis label": ("Hidden-pass curve area",),
                                      "table header": ("Order", "APFD-I", "APFDc-H", "Arm", "Candidate", "Checks",
                                                       "Relies", "Estimate", "Clause", "Risk", "Usage", "Setting",
                                                       "Value", "Stage", "Runs as", "Steps", "Details", "Note")}}
# The metrics plan.md names for this page, as dfn names.
PLAN_METRICS = {"functional mark", "hidden pass", "seen tests", "unseen pass", "acceptance pass", "strict pmd compliance",
                "strict pmd violations", "mutation score", "k/n", "adjusted mutation", "weighted tokens",
                "cost to completion", "e", "m", "m_io", "cqp", "cqp accepted", "apfd-i", "apfdc-h", "kendall distance",
                "relative spread", "consistency score c", "clear presentation", "explanatory language", "consistent code",
                "used content", "simple constructs", "minimal duplication", "modular structure", "problem alignment"}
ABSENT = "Module: not stated in the snapshot."
SITE_WRITTEN = ("Formula, Inputs, Module and Also labelled lines, this lead and the Figure 4.1 caption are written by "
                "this site.")
STRAY = ('<div class="entry"><p class="sub"><b>{}</b>. Source: stray.json. Tag: recomputed.</p>'
         '<p><b>Definition:</b> A row no family holds.</p></div>')
FILE = re.compile(r"[\w-]+\.(?:tsv|json|txt|csv|calls)\b")
NS = "{http://www.w3.org/2000/svg}"


@functools.cache
def module(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)


def kalah(name):
    return module(f"kalah_tdd.{name}")


def check():
    return module("check_kalah_tdd_study")


def flowcheck():
    return module("check_kalah_tdd_flow")


@functools.cache
def build():
    spec = importlib.util.spec_from_file_location("build_kalah_tdd_study", SCRIPTS / "build_kalah_tdd_study.py")
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out


@functools.cache
def snap():
    return kalah("snapshot").load()


def page_entry():
    return next(p for p in kalah("pagemap").PAGES if p.slug == SLUG)


def render(s):
    return build().render_page(page_entry(), s, kalah("links").index(s))


@functools.cache
def html():
    return render(snap())


@functools.cache
def page():
    parsed = check().parse(html())
    if parsed.stub:
        raise AssertionError(f"{SLUG} is still a stub")
    return parsed


def body(s):
    """The measures body on an in-memory snapshot, so a refusal raises."""
    return measures().body(page_entry(), s, kalah("links").index(s))


def measures():
    return kalah("pages.measures")


def index_section():
    return check().Tree(kalah("snapshot").section(html(), "column-index")).root


def report():
    return snap().files[kalah("snapshot").REPORT]


def entries(fragment):
    root = check().Tree(fragment).root
    return [n for n in root.iter() if "entry" in n.classes()]


def name_of(entry):
    return check().spaced(next(n for n in entry.iter() if n.tag == "b"))


def glossary():
    """{name: entry node} of the report glossary."""
    return {name_of(e): e for e in entries(kalah("snapshot").section(report(), "glossary"))}


def method_entries(files):
    """Distinct method page Column definitions entries, in first-seen order."""
    seen = {}
    for name, text in sorted(files.items()):
        if name.startswith(check().METHODS) and (i := text.find("<summary>Column definitions")) >= 0:
            for e in entries(text[i:text.index("</details>", i)]):
                seen.setdefault(check().squash(e.text()), e)
    return list(seen.values())


def source_entries():
    return entries(kalah("snapshot").section(report(), "columns")) + method_entries(snap().files) + list(glossary().values())


def cards():
    """The metric cards: every outer entry outside the Table fields cards."""
    return [n for n in page().root.iter() if "entry" in n.classes() and n.closest(cls="entry") is None
            and n.closest(cls="fields") is None]


def field_cards():
    return [n for n in page().root.iter() if "entry" in n.classes() and n.closest(cls="fields") is not None]


@functools.cache
def label_sections():
    """{(page slug, anchor): html} for each results and data page anchor, less the sections of anchors inside it,
    so each label belongs to one anchor as the page map places it."""
    s, out = kalah("snapshot"), {}
    for p in kalah("pagemap").PAGES:
        for a in p.anchors if check().is_label_page(p.slug) else ():
            own = s.section(report(), a)
            for b in check().ANCHORS:
                if b != a and re.search(rf'<h[1-6]\b[^>]*{s.ID_ATTR}{re.escape(b)}"', own):
                    own = own.replace(s.section(report(), b), "")
            out[(p.slug, a)] = own
    return out


def label_pages():
    pages = {}
    for (slug, _), own in label_sections().items():
        pages[slug] = pages.get(slug, "") + own
    return pages


@functools.cache
def snapshot_labels():
    """[(anchor, what, text)] for every label MetricDefs counts in the label sections."""
    return [(a, what, text) for (_, a), own in label_sections().items()
            for what, text in check().labels(check().Tree(own).root) if re.search(r"[^\W\d_]", text)]


def g10b_page(labels):
    """A page holding a G10b page's labels in the shape check_kalah_tdd_study.labels reads."""
    figures = "".join(f"<figure><figcaption><h3>{t}</h3></figcaption></figure>" for t in labels["figure title"])
    axes = "".join(f'<line class="axis"></line><text text-anchor="middle">{t}</text>' for t in labels["axis label"])
    heads = "".join(f"<th>{t}</th>" for t in labels["table header"])
    return f"<main>{figures}<svg>{axes}</svg><table><thead><tr>{heads}</tr></thead></table></main>"


def g10b_texts():
    return [t for labels in G10B_LABELS.values() for ts in labels.values() for t in ts]


def dfn_words(dfn):
    """A dfn's names as check_kalah_tdd_study.dfn_names reads them."""
    names = {check().spaced(dfn), (dfn.attrs.get("id") or "").replace("-", " ")}
    names |= set((dfn.attrs.get("data-alias") or "").split("|"))
    return {n.strip().casefold() for n in names if n.strip()}


def aliases(dfn):
    return [a for a in (dfn.attrs.get("data-alias") or "").split("|") if a]


QUOTES = ("The glossary row ", "The report section ", "Function ", "List phase step ", "Each method page ")


def flat(node):
    """A node's text as written, so "Tag: <span>x</span>." reads "Tag: x."."""
    return " ".join(node.text().split())


def said(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def anchor_title(anchor):
    root = check().Tree(kalah("snapshot").section(report(), anchor)).root
    return check().spaced(next(n for n in root.iter() if check().heading(n)))


def first_p(node):
    return next(n for n in node.iter() if n.tag == "p")


def subs(card, prefix):
    return [n for n in card.iter() if n.tag == "p" and "sub" in n.classes() and check().spaced(n).startswith(prefix)]


def tagged_texts(root):
    """{(tag, squashed text)} for every element under root."""
    text = {}
    check().squashed(root, text)
    return {(n.tag, text.get(id(n))) for n in root.iter()}


def lead():
    main = html()[html().index('<main id="main">'):]
    return re.sub(r"<[^>]+>", " ", main[:main.index("<h2")])


def runs_named(s, text):
    """Each facts run named in text, in first-mention order; a run inside a longer run name is no mention."""
    names = sorted(s.facts["runs"], key=len, reverse=True)
    found = re.findall(r"(?<![\w/-])(" + "|".join(map(re.escape, names)) + r")(?![\w/-])", text)
    return list(dict.fromkeys(found))


def f4_svg():
    fig = re.search(r'<figure id="f4".*?</figure>', html(), re.S).group(0)
    return fig, ET.fromstring(re.search(r"<svg.*?</svg>", fig, re.S).group(0))


def with_report(s, old, new):
    files = dict(s.files)
    files[kalah("snapshot").REPORT] = files[kalah("snapshot").REPORT].replace(old, new)
    return s._replace(files=files)


def source_field(entry):
    m = re.search(r"Source: (.*?)\. Tag:", check().spaced(first_p(entry)))
    return m.group(1) if m else ""


class Measures(unittest.TestCase):
    def test_built_not_stub(self):
        self.assertFalse(check().parse(html()).stub)
        self.assertEqual(len(re.findall(r"<h1\b", html())), 1)
        self.assertEqual(re.findall(r'<h[23] id="([^"]+)"', html().split('<main id="main">')[1]), HEADINGS)

    def test_coverage_counts_measures(self):
        items, errors = check().inventory(snap().files)
        mine = [i for i in items if i.page == SLUG]
        self.assertEqual(len(mine), 33)
        found, checked = check().coverage(mine, {SLUG: html()})
        self.assertEqual(found, [])
        self.assertEqual(checked, len(mine))

    def test_method_rows_kept(self):
        items, _ = check().inventory(snap().files)
        rows = {i.key: i.shown for i in items if i.page == check().SHARED and i.source.startswith(check().METHODS)}
        self.assertEqual(len(rows), 12)
        for key in rows:
            self.assertEqual(page().texts[key], 1, rows[key])
        key = next(iter(rows))
        root = check().Tree(html()).root
        text = {}
        check().squashed(root, text)
        node = next(n for n in root.iter() if text.get(id(n)) == key and text.get(id(n.parent)) != key)
        node.parent.kids.remove(node)
        dropped = check().Page(False, check().texts(list(root.iter()), root), {}, Counter(), root)
        self.assertIsNotNone(check().lacks((("row", key, rows[key]), 1), dropped))

    def test_plan_metrics_have_dfn(self):
        self.assertLessEqual(PLAN_METRICS, check().dfn_names(page()))
        ids = [n.attrs.get("id") for n in page().root.iter() if n.tag == "dfn"]
        self.assertNotIn(None, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([i for i in ids if page().ids[i].tag != "dfn"], [])

    def test_columns_anchor_and_intro(self):
        self.assertEqual(page().ids["columns"].tag, "h2")
        intro = re.search(r"<p>.*?</p>", kalah("snapshot").section(report(), "columns"), re.S).group(0)
        self.assertIn(intro, kalah("snapshot").section(html(), "columns"))
        self.assertEqual(kalah("links").index(snap())[kalah("snapshot").REPORT]["columns"], (SLUG, "columns"))

    def test_keeps_all_source_text(self):
        have = tagged_texts(page().root)
        section = check().Tree(kalah("snapshot").section(report(), "columns")).root
        chunks = tagged_texts(section)
        wanted = [(t, s) for t, s in chunks if t in ("p", "li", "dt", "dd") and s]
        self.assertGreater(len(wanted), 64)
        self.assertEqual([w for w in wanted if w not in have], [])

    def test_tags_from_source(self):
        lines = {check().squash(first_p(e).text()): e for e in source_entries()}
        found = cards()
        self.assertGreaterEqual(len(found), 32 + 10 + 4)
        for card in found:
            sub = first_p(card)
            with self.subTest(check().spaced(sub)):
                self.assertIn(check().squash(sub.text()), lines)
                kind = re.search(r"Tag:(\w+)\.", check().squash(sub.text())).group(1)
                pills = [check().spaced(n) for n in sub.iter() if "tag" in n.classes()]
                self.assertEqual(pills, [kind])
                if "Source:" not in check().spaced(sub):
                    self.assertEqual(kind, "verified")
        rows = {name_of(e): e for e in entries(kalah("snapshot").section(report(), "columns"))}
        for tr in (n for n in index_section().iter() if n.tag == "tr" and n.closest("tbody")):
            cells = [check().spaced(c) for c in tr.elements()]
            sub = check().squash(first_p(rows[cells[0]]).text())
            with self.subTest(cells[0]):
                self.assertIn(check().squash(f"Source: {cells[1]}. Tag: {cells[2]}."), sub)

    def test_module_named_or_absent(self):
        rows = glossary()
        for card in cards():
            inner = card.elements()[0]
            source = check().spaced(inner)
            lines = subs(card, "Module:")
            with self.subTest(check().spaced(first_p(card))):
                self.assertEqual(len(lines), 1)
                line = lines[0]
                cited = [check().spaced(n) for n in line.iter() if n.tag == "i"]
                text = " ".join([source] + [check().spaced(rows[c]) for c in cited])
                if check().spaced(line) == ABSENT:
                    self.assertIsNone(re.search(r"\S+\.py\b", source))
                    name = name_of(card)
                    for row in (r for r in rows if name in r or r == measures().CITES.get(name)):
                        self.assertIsNone(re.search(r"\S+\.py\b", check().spaced(rows[row])), row)
                else:
                    named = [check().spaced(n) for n in line.iter() if n.tag == "code"]
                    self.assertTrue(named)
                    for m in named:
                        self.assertIn(m, text)

    def test_weight_text_kept(self):
        weight_text = snap().facts["pipeline"]["weight_text"]
        card = page().ids["weighted-tokens"].closest(cls="entry")
        self.assertIn(weight_text, check().spaced(card))
        want = {k: v for k, v in re.findall(r"(input|cache creation|cache read|output) ([\d.]+)", weight_text)}
        self.assertEqual(len(want), 4)

        def weights(root_html):
            card = check().parse(root_html).ids["weighted-tokens"].closest(cls="entry")
            code = check().spaced(next(n for n in subs(card, "Formula:")[0].iter() if n.tag == "code"))
            return {k.strip(): v for v, k in re.findall(r"([\d.]+) × ([a-z ]+?)(?= \+|$)", code)}

        self.assertEqual(weights(html()), want)
        s = with_report(snap(), "output 5 per token", "output 6 per token")
        facts = copy.deepcopy(s.facts)
        facts["pipeline"]["weight_text"] = weight_text.replace("output 5", "output 6")
        self.assertEqual(weights(render(s._replace(facts=facts)))["output"], "6")

    def test_formula_numbers_from_source(self):
        m_row = check().spaced(next(e for e in entries(kalah("snapshot").section(report(), "columns")) if name_of(e) == "M"))
        doc = next(f["doc"] for f in snap().facts["analysis"]["functions"] if f["name"] == "error_count")
        cited = {"weighted-tokens": snap().facts["pipeline"]["weight_text"], "m": m_row, "e": doc}
        found = {}
        for card in cards():
            for line in subs(card, "Formula:"):
                dfn = next(n for n in card.iter() if n.tag == "dfn")
                code = next(n for n in line.iter() if n.tag == "code")
                found[dfn.attrs["id"]] = code
        self.assertEqual(set(found), set(cited))
        for key, code in found.items():
            with self.subTest(key):
                for number in re.findall(r"\d+(?:\.\d+)?", check().spaced(code)):
                    self.assertRegex(cited[key], rf"(?<![\d.]){re.escape(number)}(?![\d.])")
                hrefs = [n.attrs["href"] for n in code.iter() if n.tag == "a"]
                self.assertTrue(hrefs)
                for href in hrefs:
                    self.assertEqual(page().ids[href.removeprefix("#")].tag, "dfn", href)

    def test_e_operands_read_from_columns(self):
        card = page().ids["e"].closest(cls="entry")
        code = next(n for n in subs(card, "Formula:")[0].iter() if n.tag == "code")
        links = [n for n in code.iter() if n.tag == "a"]
        self.assertEqual(len(links), 4)
        for a in links:
            column = check().spaced(page().ids[a.attrs["href"].removeprefix("#")])
            with self.subTest(check().spaced(a)):
                self.assertEqual(a.attrs.get("title"), f"read from {column}")

    def test_doc_versions_cover_named_runs(self):
        text = lead()
        self.assertIn(f"methods doc {snap().doc}", " ".join(text.split()))
        main = html()[html().index('<main id="main">'):]
        rest = runs_named(snap(), re.sub(r"<[^>]+>", " ", main[main.index("<h2"):]))
        self.assertTrue(rest)
        listed = re.findall(r"(\S+) ([0-9a-f]{8})\b", text.split("doc versions")[1])
        self.assertEqual([r for r, _ in listed], runs_named(snap(), text.split("doc versions")[1]))
        self.assertEqual(sorted(r for r, _ in listed), sorted(set(rest + runs_named(snap(), text))))
        for run, doc in listed:
            self.assertEqual(doc, kalah("snapshot").run_doc(snap(), run), run)
        self.assertEqual(measures().named_runs(snap(), "tcp-1-list2 and rep-2/rebuild"), ["tcp-1-list2", "rep-2/rebuild"])

    def test_site_lines_tagged(self):
        main = check().Tree(html()[html().index('<main id="main">'):html().index('<h2 id="measurement-pipeline"')]).root
        said = [p for p in main.iter() if p.tag == "p" and SITE_WRITTEN in check().spaced(p)]
        self.assertEqual(len(said), 1)
        self.assertEqual([check().spaced(n) for n in said[0].iter() if "tag" in n.classes()], ["unchecked"])

    def test_refuses_unassigned_row(self):
        at = report().index("</div></details>", report().index("<summary>Column definitions"))
        s = snap()._replace(files={**snap().files, kalah("snapshot").REPORT:
                                   report()[:at] + STRAY.format("Stray column") + report()[at:]})
        self.assertIn("Stray column", kalah("snapshot").section(s.files[kalah("snapshot").REPORT], "columns"))
        with self.assertRaisesRegex(ValueError, "Stray column"):
            body(s)
        name = next(n for n in sorted(snap().files) if n.startswith(check().METHODS)
                    and "<summary>Column definitions" in snap().files[n])
        files = dict(snap().files)
        at = files[name].index("</div></details>", files[name].index("<summary>Column definitions"))
        files[name] = files[name][:at] + STRAY.format("Stray method row") + files[name][at:]
        with self.assertRaisesRegex(ValueError, "Stray method row"):
            body(snap()._replace(files=files))

    def test_refuses_missing_source(self):
        kendall = glossary()["Kendall distance"]
        start = report().index("<b>Kendall distance</b>")
        start = report().rindex('<div class="entry">', 0, start)
        end = report().index("</div>", start) + len("</div>")
        self.assertIn("Kendall", report()[start:end])
        self.assertTrue(kendall)
        with self.assertRaisesRegex(ValueError, "Kendall distance"):
            body(with_report(snap(), report()[start:end], ""))
        facts = copy.deepcopy(snap().facts)
        facts["analysis"]["functions"] = [f for f in facts["analysis"]["functions"] if f["name"] != "error_count"]
        with self.assertRaisesRegex(ValueError, "error_count"):
            body(snap()._replace(facts=facts))
        facts = copy.deepcopy(snap().facts)
        facts["pipeline"]["weight_text"] = "Weighted tokens count every token alike."
        with self.assertRaisesRegex(ValueError, "weight_text"):
            body(snap()._replace(facts=facts))
        # One kind unparsed, quoted in the report too so only the weight parse can refuse it.
        old, new = "and output 5 per token", "and output at a higher rate per token"
        facts = copy.deepcopy(snap().facts)
        facts["pipeline"]["weight_text"] = facts["pipeline"]["weight_text"].replace(old, new)
        with self.assertRaisesRegex(ValueError, "weight_text"):
            body(with_report(snap(), old, new)._replace(facts=facts))

    def test_refuses_missing_columns_parts(self):
        intro = re.search(r"<p>.*?</p>", kalah("snapshot").section(report(), "columns"), re.S).group(0)
        for old, new, says in (("<summary>Column definitions, 32 rows", "<summary>Definitions, 32 rows", "fold summary"),
                               ("Column definitions, 32 rows", "Column definitions, all rows", "row count"),
                               (intro, "", "intro")):
            with self.subTest(says), self.assertRaisesRegex(ValueError, says):
                body(with_report(snap(), old, new))

    def test_pipeline_text_version_matches(self):
        fig, root = f4_svg()
        nodes = flowcheck().node_boxes(root)
        items = re.findall(r"<li>", re.search(r'<details id="f4-data">.*?</details>', fig, re.S).group(0))
        self.assertEqual(len(nodes), len(items))
        self.assertEqual(len(nodes), len(measures().pipeline(snap())[0]))
        self.assertIsNotNone(root.find(NS + "title"))
        self.assertIsNotNone(root.find(NS + "desc"))
        ids = [e.get("id") for e in root.iter() if e.get("id")]
        self.assertTrue(ids)
        self.assertEqual([i for i in ids if not i.startswith("f4-")], [])

    def test_pipeline_from_sources(self):
        nodes, edges = measures().pipeline(snap())
        sources = {}
        for e in source_entries():  # a glossary row of the same name must not blank a column's Source
            sources.setdefault(name_of(e), source_field(e))
        self.assertTrue(sources["Functional mark /15"])
        for n in nodes:
            fields = " ".join(sources[c] for c in measures().LANES[n.lane])
            for name in FILE.findall(f"{n.label} {n.note}"):
                with self.subTest(node=n.id, file=name):
                    self.assertIn(name, fields)
        doc = {f["name"]: f["doc"] for f in snap().facts["analysis"]["functions"]}
        for target, (kind, name, inputs) in measures().COMPOSITES.items():
            sentence = doc[name] if kind == "function" else check().spaced(glossary()[name])
            self.assertEqual({e.src for e in edges if e.dst == target}, set(inputs), target)
            for terms in inputs.values():
                for term in terms:
                    self.assertIn(term, sentence, target)
        with self.assertRaisesRegex(ValueError, r"pmd\.txt"):
            body(snap()._replace(files={k: v.replace("pmd.txt", "lint.txt") for k, v in snap().files.items()}))
        with self.assertRaisesRegex(ValueError, r"curve\.py"):
            body(with_report(snap(), "curve.py", "curves.py"))
        for old, new in (("curve.py", "learning_curve.py"), ("harness/report/curve.py", "src/harness/report/curve.py"),
                         ("awards.py", "old_awards.py")):
            with self.subTest(new), self.assertRaisesRegex(ValueError, rf"names \S*{re.escape(old)} but"):
                body(with_report(snap(), old, new))

    def test_caption_names_undrawn(self):
        m = measures()
        # The caption prose only: the text version inside figcaption also names every node.
        caption = check().spaced(first_p(next(n for n in page().ids["f4"].iter() if n.tag == "figcaption")))
        families = m.FAMILIES + (m.TEST_ORDER,)
        # Drawn as the generator counts it: lane cards and cards a node is, which the caption names by their sentence.
        on_node = {n.label for n in m.pipeline(snap())[0]} & {c for _, _, names in families for c in names}
        drawn = {c for names in m.LANES.values() for c in names} | on_node
        for name in on_node:
            with self.subTest(name):
                self.assertRegex(caption, rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        for _, title, names in families:
            if not drawn & set(names) and title in caption:
                continue
            for name in (n for n in names if n not in drawn):
                with self.subTest(name):
                    self.assertRegex(caption, rf"(?<![\w-]){re.escape(name)}(?![\w-])")

    def test_undrawn_sentence_well_formed(self):
        m = measures()
        families = m.FAMILIES + (m.TEST_ORDER,)
        undrawn = functools.partial(m.MeasurePipeline.undrawn, SimpleNamespace(nodes=[]))
        with mock.patch.object(m, "LANES", {title: names[:1] for _, title, names in families}):
            sentence = undrawn()
        self.assertNotIn("famil", sentence)
        self.assertRegex(sentence, r"^[^,]+(, [^,]+)* and [^,]+ are not drawn\.$")
        with mock.patch.object(m, "LANES", {title: names for _, title, names in families if title != "Records"}):
            self.assertEqual(undrawn(), "The Records family is not drawn.")

    def test_pipeline_routes_and_limits(self):
        nodes, edges = measures().pipeline(snap())
        cols = kalah("figures.flow").COLS
        self.assertEqual([n.id for n in nodes if n.col is None or not 0 <= n.col < cols], [])
        self.assertEqual([e.label for e in edges if len(e.label) > 10], [])
        _, root = f4_svg()
        f = flowcheck()
        boxes = f.node_boxes(root)
        for path in (p for p in root.iter(NS + "path") if p.get("class") == "edge"):
            pts = f.points(path.get("d"))
            for a, b in zip(pts, pts[1:]):
                self.assertEqual([box for box in boxes if f.crosses(a, b, box)], [], path.get("d"))
        labels = f.label_boxes(root)
        for i, (s, box) in enumerate(labels):
            self.assertFalse(any(f.overlap(box, n) for n in boxes), s)
            self.assertFalse(any(f.overlap(box, o) for _, o in labels[i + 1:]), s)

    def test_figure_wrapped_and_index(self):
        fig = page().ids["f4"]
        self.assertEqual(check().spaced(next(n for n in fig.iter() if "fig-n" in n.classes())), "Figure 4.1")
        self.assertTrue(any(n.tag == "figcaption" for n in fig.iter()))
        self.assertEqual(page().ids["f4-data"].tag, "details")
        data = next(n for n in fig.iter() if n.tag == "a" and check().spaced(n) == "Data")
        self.assertIn(data.attrs["href"].removeprefix("#"), page().ids)
        diagram = next(n for n in fig.iter() if "diagram" in n.classes())
        self.assertEqual((diagram.attrs.get("role"), diagram.attrs.get("tabindex")), ("region", "0"))
        summary = next(n for n in index_section().iter() if n.tag == "summary")
        source = re.search(r"<summary>(Column definitions[^<]*)</summary>", report()).group(1)
        self.assertEqual(check().spaced(summary), source)
        n = int(re.search(r"(\d+) rows", source).group(1))
        self.assertEqual(len([r for r in summary.parent.iter() if r.tag == "tr" and r.closest("tbody")]), n)
        for table in (t for t in page().root.iter() if t.tag == "table"):
            region = table.parent
            self.assertEqual((region.attrs.get("role"), bool(region.attrs.get("aria-label"))), ("region", True))
            for th in (c for c in table.iter() if c.tag == "th"):
                self.assertEqual(th.attrs.get("scope"), "col" if th.closest("thead") else "row")
            self.assertEqual([a for td in table.iter() if td.tag == "td" for a in td.iter() if a.tag == "a"], [])

    def test_snapshot_labels_defined(self):
        errors, checked = check().metric_defs({**label_pages(), SLUG: html()})
        self.assertEqual(errors, [])
        self.assertEqual(checked, len(snapshot_labels()))
        self.assertEqual(len({(what, text) for _, what, text in snapshot_labels()}), 104)
        self.assertGreater(check().metric_defs({**label_pages(), SLUG: html().replace("data-alias=", "data-x=")})[0], [])

    def test_g10b_labels_defined(self):
        later = {slug: g10b_page(labels) for slug, labels in G10B_LABELS.items()}
        for slug, labels in G10B_LABELS.items():
            self.assertEqual(list(check().labels(check().Tree(later[slug]).root)),
                             [(what, t) for what, texts in labels.items() for t in texts])
        errors, checked = check().metric_defs({**later, SLUG: html()})
        self.assertEqual(errors, [])
        self.assertEqual(checked, len(g10b_texts()))

    def test_figure_titles_name_a_metric(self):
        records = {measures().slug(n) for id, _, names in measures().FAMILIES if id == "records" for n in names}
        metric = set()
        for dfn in (n for n in page().root.iter() if n.tag == "dfn"):
            if dfn.attrs["id"] not in records and dfn.closest(cls="fields") is None:
                metric |= dfn_words(dfn)
        within = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(metric, key=len, reverse=True))) + r")(?!\w)")
        titles = sorted({text for _, what, text in snapshot_labels() if what == "figure title"})
        self.assertEqual(len(titles), 12)
        for title in titles:
            with self.subTest(title):
                self.assertRegex(title.casefold(), within)

    def test_aliases_are_labels(self):
        texts = [t for _, _, t in snapshot_labels()] + g10b_texts()
        wanted = {check().folded(t) for t in texts} | {check().bare(t) for t in texts}
        titles = [t.casefold() for _, what, t in snapshot_labels() if what == "figure title"]
        in_title = lambda alias: any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", t) for t in titles)
        dfns = [n for n in page().root.iter() if n.tag == "dfn"]
        self.assertGreater(sum(bool(aliases(d)) for d in dfns), 15)
        for dfn in dfns:
            card = dfn.closest(cls="entry")
            lines = subs(card, "Also labelled:")
            with self.subTest(dfn.attrs["id"]):
                for alias in aliases(dfn):  # a label, or the words a figure title names a metric by
                    self.assertTrue(alias.casefold() in wanted or in_title(alias.casefold()), alias)
                self.assertEqual([check().spaced(n) for n in lines],
                                 [f"Also labelled: {'; '.join(aliases(dfn))}."] if aliases(dfn) else [])
                if dfn.closest(cls="fields") is not None and not aliases(dfn):
                    self.assertIn(check().spaced(dfn).casefold(), wanted)
        # Each bench strip dot is one bench run, so its axis label names Run ms.
        self.assertIn("bench run time", dfn_words(page().ids["run-ms"]))
        self.assertNotIn("bench run time", dfn_words(page().ids["bench-median-ms"]))

    def test_field_cards(self):
        found = field_cards()
        self.assertGreater(len(found), 40)
        heads = {}
        for (_, a), own in label_sections().items():
            for what, text in check().labels(check().Tree(own).root):
                if what == "table header":
                    heads.setdefault(text.casefold(), []).append(anchor_title(a))
        later = {}  # {label: {kind: [page titles]}}
        for slug, labels in G10B_LABELS.items():
            for what, ts in labels.items():
                for t in ts:
                    later.setdefault(t.casefold(), {}).setdefault(what, []).append(kalah("pagemap").BY_SLUG[slug].title)
        report_root, quoted = check().Tree(report()).root, 0
        for card in found:
            dfn = next(n for n in card.iter() if n.tag == "dfn")
            name = check().spaced(dfn)
            with self.subTest(name):
                self.assertEqual([check().spaced(n) for n in first_p(card).iter() if "tag" in n.classes()], ["unchecked"])
                titles = list(dict.fromkeys(t for n in [name] + aliases(dfn) for t in heads.get(n.casefold(), [])))
                lines = [check().spaced(p) for p in card.iter() if p.tag == "p"]
                where = [t for t in lines if " on Results: " in t or t.startswith("Table header in: ")]
                want = [f"{what[:1].upper()}{what[1:]} on {said(pages)}."
                        for what, pages in later.get(name.casefold(), {}).items()]
                self.assertTrue(titles or want)
                if titles:
                    at = [where[0].find(t) for t in titles]
                    self.assertNotIn(-1, at, where)
                    titles = [t for _, t in sorted(zip(at, titles))]
                    want.insert(0, f"Table header in: {said(titles)}.")
                self.assertEqual(where, [" ".join(want)])
                for p in (p for p in card.iter() if p.tag == "p" and "sub" in p.classes()):
                    text = flat(p)
                    pills = [check().spaced(n) for n in p.iter() if "tag" in n.classes()]
                    quoted += text.startswith(QUOTES)
                    if m := re.fullmatch(r"The glossary row (.+?) says: (.+) Tag: (\w+)\.", text):
                        row = glossary()[m.group(1)]
                        self.assertIn(m.group(2), flat(row))
                        self.assertEqual(pills, [re.search(r"Tag: (\w+)\.", flat(row)).group(1)])
                    elif m := re.fullmatch(r"The report section (.+?) says: (.+) Tag: (\w+)\.", text):
                        head = next(n for n in report_root.iter() if check().heading(n) and check().spaced(n) == m.group(1))
                        section = check().Tree(kalah("snapshot").section(report(), head.attrs["id"])).root
                        para = next(q for q in section.iter() if q.tag == "p" and m.group(2) in flat(q))
                        self.assertEqual(pills, [re.search(r"Tag: (\w+)\.", flat(para)).group(1)])
                    elif m := re.fullmatch(r"Function (\w+) doc: (.+)", text):
                        docs = {f["name"]: f["doc"] for a in ("functions", "stats") for f in snap().facts["analysis"][a]}
                        self.assertEqual(m.group(2), " ".join(docs[m.group(1)].split()))
                    elif m := re.fullmatch(r"List phase step (\d+) of run (\S+): (.+)", text):
                        step = snap().facts["runs"][m.group(2)]["list_phase"][int(m.group(1)) - 1]
                        self.assertEqual(m.group(3), " ".join(step.split()))
                    elif m := re.fullmatch(r"Each method page of run (\S+) says: (.+)", text):
                        pages = [t for n, t in snap().files.items() if n.startswith(f"runs/{m.group(1)}/methods/")]
                        self.assertTrue(pages)
                        for t in pages:
                            paras = [flat(q) for q in check().Tree(t).root.iter() if q.tag == "p"]
                            self.assertTrue(any(m.group(2) in q and "Tag:" not in q for q in paras))
                        self.assertEqual(pills, [])
                    else:
                        self.assertFalse(text.startswith(QUOTES), text)  # a quote line in no known shape
        self.assertGreater(quoted, 20)
        lines = lambda id: [check().spaced(p) for p in page().ids[id].closest(cls="entry").iter() if p.tag == "p"]
        self.assertIn("Table header on Results: planned contrasts.", lines("run"))
        self.assertTrue(any(t.startswith("Table header in: ") and t.endswith(" Table header on Results: test order (tcp-1).")
                            for t in lines("value")), lines("value"))
        agent = " ".join(lines("agent-time"))
        self.assertIn("Each method page of run full-1 says: Agent time sums each agent's first to last timestamp", agent)
        self.assertNotIn("no definition", agent)

    def test_refuses_duplicate_dfn_id(self):
        m = measures()
        (id, title, fields), *rest = m.FIELDS
        for extra, says in ((m.Field("Slug", "Again."), r"dfn ids \['slug'\]"), (m.Field("Cost", "A heading."), "'cost'")):
            with self.subTest(says), mock.patch.object(m, "FIELDS", ((id, title, fields + (extra,)), *rest)):
                with self.assertRaisesRegex(ValueError, says):
                    body(snap())

    def test_value_covers_settings(self):
        # The tcp-1 settings table puts seed, lister, list sha and doc version under Value, which are no numbers.
        card = page().ids["value"].closest(cls="entry")
        definition = next(check().spaced(p) for p in card.iter() if p.tag == "p" and check().spaced(p).startswith("Definition:"))
        self.assertIn("setting", definition)

    def test_field_refuses_missing_source(self):
        for old, new, name in (("Its slug is its short lowercase name", "Its slug is its short name", "Slug"),
                               ("q is the share of bootstrap alphas", "q is the fraction of bootstrap alphas", "Finals q"),
                               ("Agent id</th>", "Agent key</th>", "Agent id")):
            with self.subTest(name), self.assertRaisesRegex(ValueError, rf"field '{re.escape(name)}'"):
                body(with_report(snap(), old, new))
        facts = copy.deepcopy(snap().facts)
        facts["runs"]["tcp-1-list"]["list_phase"][4] = "Guess each candidate's size."
        with self.assertRaisesRegex(ValueError, "field 'Estimate'"):
            body(snap()._replace(facts=facts))
        name = check().METHODS + "classic.html"  # one method page reworded is enough to refuse
        files = {**snap().files, name: snap().files[name].replace("Agent time sums each", "Agent time adds each")}
        with self.assertRaisesRegex(ValueError, "field 'Agent time'"):
            body(snap()._replace(files=files))


if __name__ == "__main__":
    unittest.main()
