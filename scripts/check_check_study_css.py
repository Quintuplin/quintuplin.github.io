#!/usr/bin/env python3
"""Check the study stylesheet touch target (#60), figure pull (#69) and card label (#70) checks on edited copies of study.css.

Usage: check_check_study_css.py
"""
import importlib.util
import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def css():
    spec = importlib.util.spec_from_file_location("check_study_css", SCRIPTS / "check_study_css.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def touch(edit=lambda text: text):
    """touch_targets on the committed study.css after edit."""
    c = css()
    text = re.sub(r"/\*.*?\*/", "", (SCRIPTS.parent / c.CSS).read_text(encoding="utf-8"), flags=re.S)
    return c.touch_targets(list(c.rules(edit(text))))


class TouchTargets(unittest.TestCase):
    def test_committed_passes(self):
        self.assertEqual(touch(), [])

    def test_needs_coarse_rows(self):
        errors = touch(lambda t: t.replace("(pointer:coarse)", "(pointer:fine)"))
        self.assertRegex(" ".join(errors), r"\.toc a has no min-height of 44px or more under @media")

    def test_base_rows_stay_between_24_and_28px(self):
        for value in ("20px", "44px"):
            with self.subTest(value):
                errors = touch(lambda t: re.sub(r"(\.toc a\{[^}]*min-height:)\d+px", rf"\g<1>{value}", t, count=1))
                self.assertRegex(" ".join(errors), r"\.toc a has no min-height between 24px and 28px, ")

    def test_later_base_raise_fails(self):
        self.assertRegex(" ".join(touch(lambda t: t + ".toc a{min-height:44px}")), r"rule \.toc a raises \.toc a")

    def test_desktop_query_raise_fails(self):
        # Only the coarse query may raise the compact row, so a desktop or fine pointer query fails.
        for probe in ("@media (min-width:900px){.toc a{min-height:44px}}", "@media (pointer:fine){.toc ol a{min-height:44px}}"):
            with self.subTest(probe):
                self.assertRegex(" ".join(touch(lambda t: t + probe)), r"rule \.toc (ol )?a raises \.toc a")

    def test_later_override_fails(self):
        for probe in ("@media (max-width:899.98px){.toc a{min-height:20px}}", ".toc ol ol a{min-height:20px}",
                      ".pager a:hover{min-height:auto}"):
            with self.subTest(probe):
                self.assertRegex(" ".join(touch(lambda t: t + probe)), r"rule \.(toc|pager) .*a(:hover)? lowers")

    def test_stronger_earlier_override_fails(self):
        self.assertRegex(" ".join(touch(lambda t: ".toc ol a{min-height:20px}" + t)), r"rule \.toc ol a lowers \.toc a")

    def test_rem_and_em_count_at_16px(self):
        for value, ok in (("3rem", True), ("2.75em", True), ("2rem", False), ("10vh", False), ("auto", False)):
            with self.subTest(value):
                errors = touch(lambda t: t.replace("{.toc a,.contents li > a{min-height:44px}}",
                                                    f"{{.toc a,.contents li > a{{min-height:{value}}}}}"))
                self.assertEqual(errors == [], ok, errors)

    def test_other_selectors_for_the_link_fail(self):
        for probe, before in (("#toc a{min-height:20px}", True), ("details.toc a{min-height:20px}", True),
                              (".toc a{min-height:20px !important}", True), ("#toc a{min-height:20px}", False)):
            with self.subTest(probe, before=before):
                errors = touch(lambda t: probe + t if before else t + probe)
                self.assertRegex(" ".join(errors), r"rule (#|details\.|\.)toc a lowers \.toc a")

    def test_larger_override_passes(self):
        # The compact base row has a cap, so only a touch query may raise it.
        for probe in (".pager a:hover{min-height:48px}", "@media (pointer:coarse){.toc ol ol a{min-height:48px}}"):
            with self.subTest(probe):
                self.assertEqual(touch(lambda t: t + probe), [])

    def test_figure_data_link_is_44px(self):
        # The rule must exist before any page uses a figure foot, so the check never passes on nothing.
        rule = re.compile(r"\.fig-foot a\{[^}]*\}")
        errors = touch(lambda t: rule.sub("", t))
        self.assertRegex(" ".join(errors), r"\.fig-foot a has no min-height of 44px or more")
        self.assertRegex(" ".join(touch(lambda t: t + ".fig-foot a:hover{min-height:20px}")), r"rule \.fig-foot a:hover lowers")

    def test_cell_link_is_44px_on_touch(self):
        # Design links in methodology table cells were 18px tall at 375px.
        for removed, remaining in ((".cols td a", ".matrix td a"), (".matrix td a", ".cols td a")):
            with self.subTest(removed):
                errors = touch(lambda t: t.replace(".cols td a,.matrix td a", remaining))
                self.assertRegex(" ".join(errors), re.escape(removed) + r" has no min-height of 44px or more under @media")
                errors = touch(lambda t: t + removed + "{min-height:20px}")
                self.assertRegex(" ".join(errors), "rule " + re.escape(removed) + " lowers")


def kept(edit=lambda text: text):
    """kept_rules on the committed study.css after edit."""
    c = css()
    text = re.sub(r"/\*.*?\*/", "", (SCRIPTS.parent / c.CSS).read_text(encoding="utf-8"), flags=re.S)
    return c.kept_rules(list(c.rules(edit(text))))


class KeptRules(unittest.TestCase):
    def test_committed_passes(self):
        self.assertEqual(kept(), [])

    def test_each_rule_needed(self):
        text = (SCRIPTS.parent / css().CSS).read_text(encoding="utf-8")
        for sel, media, prop, value in css().KEPT:
            with self.subTest(sel):
                bad = {"normal": "anywhere", "anywhere": "normal", "nowrap": "normal", "block": "none"}[value]
                edit = lambda t: re.sub(rf"({re.escape(sel)}\{{[^}}]*\b{re.escape(prop)}:){re.escape(value)}",
                                        rf"\g<1>{bad}", t)
                self.assertNotEqual(edit(text), text, "the mutation must change the retained rule")
                errors = kept(edit)
                self.assertRegex(" ".join(errors), rf"no rule sets {re.escape(sel)} \{{{prop}:{value}\}}")

    def test_caption_rule_must_be_in_the_stacked_query(self):
        errors = kept(lambda t: t.replace(".cols caption{display:block}", "") + ".cols caption{display:block}")
        self.assertRegex(" ".join(errors), r"\.cols caption \{display:block\} under @media \(max-width:640px\)")


FIX = ".diagram .qlegend{display:grid;grid-template-columns:max-content max-content;gap:8px 6px}.diagram .qlegend .cnt{margin-left:0}"


def pull(edit=lambda text: text):
    """diagram_pull on the committed study.css after edit."""
    c = css()
    text = re.sub(r"/\*.*?\*/", "", (SCRIPTS.parent / c.CSS).read_text(encoding="utf-8"), flags=re.S)
    return c.diagram_pull(list(c.rules(edit(text))))


class DiagramPull(unittest.TestCase):
    def test_committed_passes(self):
        self.assertEqual(pull(), [])

    def test_count_without_diagram_reset_fails(self):
        # The legend count pulls 8px left, which a figure's scroll region clips at a line start.
        errors = pull(lambda t: t.replace(FIX, ""))
        self.assertRegex(" ".join(errors), r"\.cnt sets margin-left:-8px and no \.diagram rule resets it")

    def test_negative_reset_or_weaker_earlier_reset_fails(self):
        for probe in (lambda t: t.replace(FIX, "") + ".diagram .cnt{margin-inline-start:-1px}",
                      lambda t: ".diagram .cnt{margin-left:0}" + t.replace(FIX, "") + ".a .cnt{margin-left:-2px}"):
            with self.subTest():
                self.assertRegex(" ".join(pull(probe)), r"\.cnt sets margin")

    def test_pull_on_figure_child_fails(self):
        # A rule written under .diagram is itself inside the scroll region.
        self.assertRegex(" ".join(pull(lambda t: t + ".diagram .zz{margin-left:-6px}")), r"\.diagram \.zz sets margin-left:-6px")

    def test_not_toc_is_not_sidebar(self):
        # :not(.toc) names everything but the sidebar, so a figure can hold it.
        self.assertRegex(" ".join(pull(lambda t: t + "details:not(.toc) .cnt2{margin-left:-3px}")), r"\.cnt2 sets margin-left:-3px")

    def test_shorthand_pull_fails(self):
        # The left value is the fourth of four, the second of two or three, the only one, or margin-inline's first.
        for rule in (".yy{margin:0 0 0 -5px}", ".yy{margin:0 -5px 1px}", ".yy{margin:1px -5px}", ".yy{margin:-5px}",
                     ".yy{margin-inline:-5px 0}", ".yy{margin:var(--a) calc(var(--b) * 2) 0 -5px !important}"):
            with self.subTest(rule):
                self.assertRegex(" ".join(pull(lambda t: t + rule)), r"\.yy sets margin")

    def test_fold_summary_exemption_is_narrow(self):
        # The fold summary's -14px only cancels its details' 14px padding. Any other pull there still fails.
        self.assertRegex(" ".join(pull(lambda t: t + "details:not(.toc) > summary{margin:0 -15px}")), r"summary sets margin:0 -15px")

    def test_reset_and_sidebar_pass(self):
        # The sidebar never sits inside a figure, so its current-page pull needs no reset.
        for probe in (".x{margin-inline-start:-4px}.diagram .x{margin-inline-start:0}", ".toc li a{margin-left:-2px}",
                      ".yy{margin:0 -5px 0 0}", ".yy{margin-inline:0 -5px}", ".x{margin:0 0 0 -4px}.diagram .x{margin:0}"):
            with self.subTest(probe):
                self.assertEqual(pull(lambda t: t + probe), [])


LABEL = ".cols td.nowrap::before{white-space:normal}"


def wrap(edit=lambda text: text):
    """label_wrap on the committed study.css after edit."""
    c = css()
    text = re.sub(r"/\*.*?\*/", "", (SCRIPTS.parent / c.CSS).read_text(encoding="utf-8"), flags=re.S)
    return c.label_wrap(list(c.rules(edit(text))))


class LabelWrap(unittest.TestCase):
    def test_committed_passes(self):
        self.assertEqual(wrap(), [])

    def test_missing_or_misplaced_rule_fails(self):
        # Outside the narrow block the rule never reaches stacked cards.
        for probe in (lambda t: t.replace(LABEL, ""), lambda t: t.replace(LABEL, "") + LABEL):
            with self.subTest():
                self.assertRegex(" ".join(wrap(probe)), r"no rule under @media \(max-width:640px\) sets \.cols td\.nowrap")

    def test_later_or_stronger_nowrap_undoes_it(self):
        for probe in ("@media (max-width:640px){.cols td + td.nowrap::before{white-space:nowrap}}",
                      "@media (max-width:640px){table.cols td.nowrap::before{white-space:nowrap}}",
                      "#main .cols td.nowrap::before{white-space:nowrap}", ".nowrap::before{white-space:nowrap !important}",
                      "#main .nowrap::before{white-space:nowrap}"):
            with self.subTest(probe):
                self.assertRegex(" ".join(wrap(lambda t: t + probe)), r"sets white-space:nowrap.* on the stacked card label")

    def test_weaker_earlier_or_other_label_passes(self):
        for probe in (lambda t: ".cols td.nowrap::before{white-space:nowrap}" + t,
                      lambda t: t + ".qtable td.nowrap::before{white-space:nowrap}",
                      lambda t: t + ".cols td.nowrap::before{white-space:nowrap}@media (max-width:640px){" + LABEL + "}",
                      lambda t: t + ".cols td.nowrap::before{white-space:pre-wrap}"):
            with self.subTest():
                self.assertEqual(wrap(probe), [])


if __name__ == "__main__":
    unittest.main()
