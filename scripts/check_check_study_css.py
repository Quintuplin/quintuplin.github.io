#!/usr/bin/env python3
"""Check the study stylesheet touch target check (#60) on edited copies of study.css.

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
                errors = touch(lambda t: t.replace("{.toc a{min-height:44px}}", f"{{.toc a{{min-height:{value}}}}}"))
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


if __name__ == "__main__":
    unittest.main()
