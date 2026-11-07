#!/usr/bin/env python3
"""Check the Kalah TDD study completeness check (#61) on fixture sources and pages, then run it over the committed study.

Usage: check_check_kalah_tdd_study.py
"""
import importlib.util
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FIXTURES = SCRIPTS / "fixtures/kalah-tdd"
SOURCES = {"runs/full-1/report.html": "source-report", "artifact/showcase.html": "source-showcase",
           "runs/full-1/methods/classic.html": "source-classic"}
PAGES = {"": "page-landing", "results/survey": "page-results-survey", "questions": "page-questions",
         "glossary": "page-glossary", "methodology/measures": "page-measures", "designs/classic": "page-designs-classic"}
STUB = '<meta name="kalah-tdd-stub">'


def study():
    spec = importlib.util.spec_from_file_location("check_kalah_tdd_study", SCRIPTS / "check_kalah_tdd_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(name):
    return (FIXTURES / f"{name}.fixture").read_text(encoding="utf-8")


def edited(texts, edits):
    """texts with each (old, new) string pair applied under its key."""
    texts = dict(texts)
    for key, pairs in edits.items():
        for old, new in pairs:
            assert old in texts[key], f"{old!r} not in {key!r}"
            texts[key] = texts[key].replace(old, new)
    return texts


def sources(**edits):
    return edited({name: read(f) for name, f in SOURCES.items()}, edits)


def pages(edits=None):
    return edited({slug: read(f) for slug, f in PAGES.items()}, edits or {})


def errors(edits=None, final=False, src=None):
    """Coverage and MetricDefs errors on the fixture pages, after the fixture sources inventory cleanly."""
    s = study()
    items, inventory_errors = s.inventory(sources(**(src or {})))
    assert inventory_errors == [], inventory_errors
    site = pages(edits)
    return s.coverage(items, site, final)[0] + s.metric_defs(site)[0]


class Inventory(unittest.TestCase):
    def test_fixture_items(self):
        items, errs = study().inventory(sources())
        self.assertEqual(errs, [])
        self.assertEqual(Counter(i.kind for i in items), {"figure": 1, "row": 5, "table": 4, "tile": 6, "term": 6})
        shared = sorted(i.shown for i in items if i.page == study().SHARED)
        self.assertEqual(shared, ["PMD A static analysis tool for Java.",
                                  "Replicate . Tag: verified. Definition: The replicate build id.",
                                  "Seed One stone in a pit.", "Store The pit that keeps a player's seeds."])
        # A method page maps whole to its design page, even under its own h5 id "headline".
        self.assertEqual({i.page for i in items if "rep-1-r01" in i.shown}, {"designs/classic"})
        figure = next(i for i in items if i.kind == "figure")
        self.assertEqual(figure.page, "results/survey")
        self.assertEqual(len(figure.key[1]), 2, "a figure item carries each mark title")

    def test_row_count_from_summary(self):
        source = sources(**{"runs/full-1/report.html": [("Table view, 2 rows", "Table view, 3 rows")]})
        self.assertRegex(" ".join(study().inventory(source)[1]), "Table view, 3 rows.*2 rows")

    def test_committed_snapshot(self):
        # Guards the default run against a no-op: the real sources yield every item kind.
        s = study()
        sys.path.insert(0, str(SCRIPTS))
        from kalah_tdd import snapshot
        items, errs = s.inventory(snapshot.load().files)
        self.assertEqual(errs, [])
        kinds = Counter(i.kind for i in items)
        self.assertEqual(set(kinds), set(s.KINDS))
        self.assertTrue(all(kinds[k] > 0 for k in s.KINDS), kinds)
        self.assertNotIn(None, {i.page for i in items})


class Coverage(unittest.TestCase):
    def test_fixture_passes(self):
        s = study()
        items = s.inventory(sources())[0]
        site = pages()
        self.assertEqual(s.coverage(items, site), ([], len(items)), "every item on a non-stub page is checked")
        self.assertEqual(s.metric_defs(site), ([], 7), "figure title, 2 axis labels, 3 headers and a tile label")

    def test_droppedRowFails(self):
        row = '<tr><th scope="row">noun-verb</th><td>961,206</td><td>0</td></tr>\n'
        self.assertRegex(" ".join(errors({"results/survey": [(row, "")]})), "results/survey lacks row 'noun-verb 961,206 0'")
        entry = '<div class="entry"><p class="sub"><b>Family</b>'
        self.assertRegex(" ".join(errors({"glossary": [(entry, '<div class="entry"><p class="sub"><b>Families</b>')]})),
                         "glossary lacks term 'Family")
        summary = "Table view, 2 rows and 3 columns"
        self.assertRegex(" ".join(errors({"results/survey": [(summary, "Table view")]})), f"lacks table '{summary}'")

    def test_droppedPrefixRowFails(self):
        # Each item must be one element's whole text, so a row inside a longer row is no copy.
        three = ("Table view, 2 rows", "Table view, 3 rows")
        row = '<tr><th scope="row">classic</th><td>843,734</td><td>1</td></tr>'
        src = {"runs/full-1/report.html": [three, ("<tbody>", "<tbody>" + row)]}
        self.assertRegex(" ".join(errors({"results/survey": [three]}, src=src)), "results/survey lacks row 'classic 843,734 1'")
        kpi = '<div class="kpi"><b>804,727</b><span>Cost to completion</span></div>'
        dropped = {"designs/classic": [(kpi, "<p>804,727 Cost to completion so far</p>")]}
        self.assertRegex(" ".join(errors(dropped)), "designs/classic lacks tile '804,727 Cost to completion'")

    def test_copy_counts(self):
        tile = ('<div class="tile"><span class="sub">Correctness</span><b>11 of 11</b>'
                '<span class="sub">methods with a full functional mark</span></div>')
        twice = {"runs/full-1/report.html": [(tile, tile + tile)]}
        self.assertRegex(" ".join(errors(src=twice)), "landing lacks tile 'Correctness 11 of 11 .*found 1 of 2")
        self.assertEqual(errors({"": [(tile, tile + tile)]}, src=twice), [])
        # A page needs the most copies one source holds, so two sources may share one copy.
        other = {"artifact/showcase.html": [('<div class="grid">', f'<div class="tiles">{tile}</div><div class="grid">')]}
        self.assertEqual(errors(src=other), [])

    def test_shared_items(self):
        terms = '<dl class="terms"><dt>PMD</dt><dd>A static analysis tool for Java.</dd></dl>'
        # A shared item is needed once, however often one source repeats it.
        self.assertEqual(errors(src={"artifact/showcase.html": [(terms, terms + terms)]}), [])
        # Shared items wait while either glossary or measures is a stub.
        self.assertEqual(errors({"glossary": [("<head>", f"<head>{STUB}"), (terms, "")]}), [])

    def test_svg_title_is_no_mark(self):
        svg = 'aria-label="Scatter of PMD violations against weighted tokens, one mark per method">'
        self.assertEqual(errors({"results/survey": [(svg, svg + "<title>Scatter</title>")]}), [])

    def test_droppedMarkFails(self):
        mark = re.search(r'<path class="mk s2".*?</path>', read("page-results-survey")).group(0)
        found = " ".join(errors({"results/survey": [(mark, "")]}))
        self.assertRegex(found, "results/survey lacks figure 'Scatter of PMD violations.*missing marks.*noun-verb: 961,206")
        found = " ".join(errors({"results/survey": [(mark, mark + mark)]}))
        self.assertRegex(found, "results/survey lacks figure .*extra marks.*noun-verb")

    def test_wrongPageFails(self):
        tile = '<div class="tiles"><div class="tile"><span class="sub">Correctness</span>'
        moved = {"": [(tile, '<div class="tiles"><div class="tile"><span class="sub">Moved</span>')],
                 "results/survey": [("</main>", tile + "<b>11 of 11</b></div></div></main>")]}
        self.assertRegex(" ".join(errors(moved)), "^landing lacks tile 'Correctness 11 of 11")
        moved = {"questions": [('id="q1"', 'id="q2"')], "glossary": [("<h1>", '<h1 id="q1">')]}
        self.assertRegex(" ".join(errors(moved)), "questions lacks term '#q1'")
        emptied = {"questions": [('<p class="aq"><b>Q1</b> Does the greedy analogy hold?</p>', "")]}
        self.assertRegex(" ".join(errors(emptied)), "questions lacks term '#q1': question differs")
        # A shared term may sit on either glossary or measures, but not elsewhere.
        terms = '<dl class="terms"><dt>PMD</dt><dd>A static analysis tool for Java.</dd></dl>'
        self.assertEqual(errors({"glossary": [(terms, "")], "methodology/measures": [("</main>", terms + "</main>")]}), [])
        moved = {"glossary": [(terms, "")], "questions": [("</main>", terms + "</main>")]}
        self.assertRegex(" ".join(errors(moved)), "glossary or measures lacks term 'PMD A static analysis tool for Java.'")

    def test_droppedDdFails(self):
        # In a dl of two pairs each dt with its dd is one term, which no single element holds.
        dd = "<dd>One stone in a pit.</dd>"
        self.assertRegex(" ".join(errors({"glossary": [(dd, "")]})), "glossary or measures lacks term 'Seed One stone in a pit.'")
        # A term that one element already holds, a lone dt or a one-pair dl, counts once.
        found = study().parse(read("page-glossary") + "<dl><dt>Lone</dt></dl>").texts
        self.assertEqual([found[t] for t in ("PMDAstaticanalysistoolforJava.", "SeedOnestoneinapit.", "Lone")], [1, 1, 1])


class MetricDefs(unittest.TestCase):
    def test_undefinedMetricFails(self):
        header = '<th scope="col">PMD violations</th>'
        found = " ".join(errors({"results/survey": [(header, '<th scope="col">Zorp score</th>')]}))
        self.assertRegex(found, "results/survey table header 'Zorp score' has no dfn on methodology/measures")
        found = " ".join(errors({"methodology/measures": [(' data-alias="Cost"', "")]}))
        self.assertRegex(found, "results/survey tile label 'Cost' has no dfn")
        found = " ".join(errors({"results/survey": [(">Weighted tokens, millions<", ">Seeds sown<")]}))
        self.assertRegex(found, "results/survey axis label 'Seeds sown' has no dfn")
        found = " ".join(errors({"results/survey": [("Figure 1. PMD violations against weighted tokens", "Figure 1. Seeds sown")]}))
        self.assertRegex(found, "results/survey figure title 'Figure 1. Seeds sown' has no metric dfn")
        # The id names a dfn too, so "Weighted tokens" needs id weighted-tokens.
        found = " ".join(errors({"methodology/measures": [('id="weighted-tokens"', 'id="wt"')]}))
        self.assertRegex(found, "table header 'Weighted tokens' has no dfn")

    def test_label_must_match_whole_name(self):
        # Only a figure title may contain a dfn name. Other labels are one name, less a unit.
        header = '<th scope="col">PMD violations</th>'
        found = " ".join(errors({"results/survey": [(header, '<th scope="col">Strict PMD compliance</th>')]}))
        self.assertRegex(found, "results/survey table header 'Strict PMD compliance' has no dfn")
        unit = {"results/survey": [(header, '<th scope="col">PMD violations /15</th>'),
                                   ("<span class=\"sub\">Cost</span>", "<span class=\"sub\">cost, millions</span>")]}
        self.assertEqual(errors(unit), [])
        # A figure title needs a whole dfn name, so "Methods" does not contain "method".
        title = "Figure 1. PMD violations against weighted tokens"
        found = " ".join(errors({"results/survey": [(title, "Figure 1. Methods")]}))
        self.assertRegex(found, "figure title 'Figure 1. Methods' has no metric dfn")

    def test_figureTitleNeedsMetricDfn(self):
        # A field or record dfn names a row part, so it defines a header but never a figure title.
        rows = ('<div class="shaped fields"><p><dfn id="seed">Seed</dfn></p></div>'
                '<div class="shaped records"><p><dfn id="arm">Arm</dfn></p></div><h2 ')
        title = "Figure 1. PMD violations against weighted tokens"
        for name in ("Seed", "Arm"):
            with self.subTest(name):
                found = " ".join(errors({"methodology/measures": [("<h2 ", rows)],
                                         "results/survey": [(title, f"Figure 1. {name} per pit")]}))
                self.assertRegex(found, f"figure title 'Figure 1. {name} per pit' has no metric dfn")
                header = {"methodology/measures": [("<h2 ", rows)],
                          "results/survey": [('<th scope="col">PMD violations</th>', f'<th scope="col">{name}</th>')]}
                self.assertEqual(errors(header), [])
        # A stage flow names stages, not measures, so its title is not checked.
        flow = {"results/survey": [(title, "Figure 1. Stage flow"), ('<svg viewBox', '<svg class="flow" viewBox')]}
        self.assertEqual(errors(flow), [])
        self.assertEqual(study().metric_defs(pages(flow))[1], 6)

    def test_bare_dfn_id(self):
        # An id with no value names nothing and must not crash the check.
        self.assertEqual(errors({"methodology/measures": [("<h2 ", "<p><dfn id>Bare</dfn></p><h2 ")]}), [])

    def test_dfn_name_with_comma(self):
        # A label may be the whole comma name, or that name less one ", unit".
        header = '<th scope="col">PMD violations</th>'
        named = {"methodology/measures": [("<h2 ", "<p><dfn>Tokens, weighted</dfn></p><h2 ")],
                 "results/survey": [(header, '<th scope="col">Tokens, Weighted</th>'),
                                    ('<span class="sub">Cost</span>', '<span class="sub">Tokens, weighted, millions</span>')]}
        self.assertEqual(errors(named), [])

    def test_void_tag_closes_itself(self):
        # A br opens nothing, so the span after it is still the tile's first label span.
        tile = '<div class="tile"><span class="sub">Cost</span>'
        found = " ".join(errors({"results/survey": [(tile, '<div class="tile"><br><span class="sub">Zorp</span>')]}))
        self.assertRegex(found, "tile label 'Zorp' has no dfn")

    def test_stub_measures_defines_nothing(self):
        # Labels wait for a built measures page, as shared items do.
        site = pages({"methodology/measures": [("<head>", f"<head>{STUB}")]})
        self.assertEqual(study().metric_defs(site), ([], 0))


class Stubs(unittest.TestCase):
    def test_finalRejectsStub(self):
        s = study()
        items = s.inventory(sources())[0]
        site = pages({"questions": [("<head>", f"<head>{STUB}")]})
        self.assertEqual(s.coverage(items, site), ([], len(items) - 1), "the stub's q1 is skipped")
        self.assertEqual(s.coverage(items, site, final=True)[0], ["questions is a stub"])

    def test_stub_skips_labels(self):
        stubbed = {"results/survey": [("<head>", f"<head>{STUB}"), ('<th scope="col">Method</th>', "<th>Zorp</th>")]}
        self.assertEqual(errors(stubbed), [])
        self.assertEqual(study().metric_defs(pages(stubbed))[1], 0)

    def test_committed_study(self):
        s = study()
        from kalah_tdd import pagemap, pages as built
        # The check's stub detection must agree with the page registry.
        stubs = {slug for slug, html in s.load_pages(SCRIPTS.parent).items() if s.parse(html).stub}
        self.assertEqual(stubs, {p.slug for p in pagemap.PAGES if built.built(p) is None})
        self.assertEqual(s.check(SCRIPTS.parent)[0], [])
        final = s.check(SCRIPTS.parent, final=True)[0]
        self.assertEqual(len([e for e in final if e.endswith(" is a stub")]), len(stubs))


if __name__ == "__main__":
    unittest.main()
