#!/usr/bin/env python3
"""Check the study navigation check (#60) on fixture pages, then run it over the committed studies.

Usage: check_check_study_nav.py
"""
import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FIXTURE = SCRIPTS / "fixtures/study-nav"
INDEX, PART = "/studies/demo/", "/studies/demo/part/"


def nav():
    spec = importlib.util.spec_from_file_location("check_study_nav", SCRIPTS / "check_study_nav.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(**edits):
    """The fixture pages, each edited by (old, new) string pairs keyed by page."""
    pages = nav().load(FIXTURE, ".fixture")
    for key, pairs in edits.items():
        url = INDEX if key == "index" else PART
        for old, new in pairs:
            assert old in pages[url], f"{old!r} not in {url}"
            pages[url] = pages[url].replace(old, new)
    return pages


class StudyNav(unittest.TestCase):
    def test_fixture_passes(self):
        pages = fixture()
        self.assertEqual(sorted(pages), [INDEX, PART])
        for check in (nav().toc_links, nav().cross_links, nav().unique_ids):
            self.assertEqual(check(pages), [], check.__name__)

    def test_toc_links(self):
        n = nav()
        pages = fixture(part=[('<a href="#columns">', '<a href="#gone">')])
        self.assertRegex(" ".join(n.toc_links(pages)), f"{PART}.*#gone")
        pages = fixture(index=[('<a href="/studies/demo/part/">', '<a href="/studies/demo/missing/">')])
        self.assertRegex(" ".join(n.toc_links(pages)), "/studies/demo/missing/")
        pages = fixture(part=[('aria-current="page"', "")])
        self.assertRegex(" ".join(n.toc_links(pages)), f"{PART}.*aria-current")
        pages = fixture(index=[('<li><a href="/studies/demo/part/">', '<li><a href="/studies/demo/part/" aria-current="page">')])
        self.assertRegex(" ".join(n.toc_links(pages)), f"{INDEX}.*aria-current")
        self.assertEqual(n.cross_links(fixture(part=[('<a href="#columns">', '<a href="#gone">')])), [],
                         "a sidebar link is reported by toc_links only")

    def test_cross_links(self):
        n = nav()
        pages = fixture(part=[('href="../#intro"', 'href="../#outro"')])
        self.assertRegex(" ".join(n.cross_links(pages)), f"{PART}.*{INDEX}#outro")
        pages = fixture(index=[('href="/studies/demo/part"', 'href="/studies/demo/other"')])
        self.assertRegex(" ".join(n.cross_links(pages)), "/studies/demo/other")
        pages = fixture(index=[('href="#main"', 'href="#mian"')])
        self.assertRegex(" ".join(n.cross_links(pages)), f"{INDEX}.*#mian")

    def test_link_into_renamed_id(self):
        # unique_ids in the generator renames a colliding id on its own page only, so links from other pages break.
        pages = fixture(part=[('<h2 id="columns">', '<h2 id="columns-2">')])
        self.assertRegex(" ".join(nav().cross_links(pages)), f"{INDEX} links {PART}#columns .*columns-2")
        self.assertRegex(" ".join(nav().toc_links(pages)), f"{INDEX} links {PART}#columns")

    def test_unique_ids(self):
        pages = fixture(part=[('<title id="t">', '<title id="columns">')])
        self.assertEqual(nav().unique_ids(pages), [f"{PART} has id columns 2 times"])

    def test_committed_studies(self):
        self.assertEqual(nav().check(SCRIPTS.parent), [])


if __name__ == "__main__":
    unittest.main()
