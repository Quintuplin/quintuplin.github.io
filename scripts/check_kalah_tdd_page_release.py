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
    def test_projectsListsStudy(self):
        projects = (ROOT / "projects/index.html").read_text(encoding="utf-8")
        studies = re.search(r"<h2>Studies</h2>\s*<ul\b[^>]*>(.*?)</ul>", projects, re.S).group(1)
        linked = re.findall(r'<li><a href="(/studies/[\w-]+/)">[^<]+</a>\. \S', studies)
        built = sorted(f"/studies/{p.parent.name}/" for p in (ROOT / "studies").glob("*/index.html"))
        self.assertIn("/studies/kalah-tdd-study/", built)
        self.assertEqual(sorted(linked), built)
        self.assertNotIn("single self-contained page", projects)

    def test_siteCheckRunsFinal(self):
        site = (ROOT / "scripts/check_site.sh").read_text(encoding="utf-8")
        runs = re.findall(r"^python3 -I scripts/check_kalah_tdd_study\.py\b(.*?)\|\|", site, re.M)
        self.assertEqual([r.split() for r in runs], [["--final"]])

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
