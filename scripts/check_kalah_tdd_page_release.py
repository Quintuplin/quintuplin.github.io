#!/usr/bin/env python3
"""Check the Kalah TDD study release wiring (#113, #118): the projects page lists every study, the site check runs
the completeness check in its final mode, where a stub page fails, and the site check compares every study page,
study stylesheet and simulation data file with the built copy.

Usage: check_kalah_tdd_page_release.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Release(unittest.TestCase):
    def test_verbatimCoversDataAndStudy(self):
        site = (ROOT / "scripts/check_site.sh").read_text(encoding="utf-8")
        loops = re.findall(r"^for page in (.*?); do\n(.*?)^done$", site, re.M | re.S)
        verbatim = [re.findall(r"\$\([^)]*\)|\S+", items) for items, body in loops if "cmp -s" in body]
        self.assertEqual(verbatim, [[
            "simulations/*/index.html", "$studyPages", "$(find studies -name '*.css')", "simulations/*/*.json",
        ]])
        self.assertRegex(site, r"(?m)^studyPages=\$\(find studies -name '\*\.html' \| sort\)$")


if __name__ == "__main__":
    unittest.main()
