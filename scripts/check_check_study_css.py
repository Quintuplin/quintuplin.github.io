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

    def test_needs_compact_base(self):
        errors = touch(lambda t: re.sub(r"(\.toc a\{[^}]*min-height:)\d+px", r"\g<1>20px", t, count=1))
        self.assertRegex(" ".join(errors), r"\.toc a has no min-height of 24px or more, ")

    def test_later_override_fails(self):
        for probe in ("@media (max-width:899.98px){.toc a{min-height:20px}}", ".toc ol ol a{min-height:20px}",
                      ".pager a:hover{min-height:auto}"):
            with self.subTest(probe):
                self.assertRegex(" ".join(touch(lambda t: t + probe)), r"rule \.(toc|pager) .*a(:hover)? lowers")

    def test_stronger_earlier_override_fails(self):
        self.assertRegex(" ".join(touch(lambda t: ".toc ol a{min-height:20px}" + t)), r"rule \.toc ol a lowers \.toc a")

    def test_larger_override_passes(self):
        self.assertEqual(touch(lambda t: t + ".toc ol ol a{min-height:48px}"), [])


if __name__ == "__main__":
    unittest.main()
