#!/usr/bin/env python3
"""Check that the Deep Nested LSH generator pins its data to one clean study commit.

Self-contained: builds throwaway git repos, so CI needs only python3 and git.
Usage: check_build_deep_nested_lsh_data.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

GENERATOR = Path(__file__).resolve().parent / "build_deep_nested_lsh_data.py"


def load_generator():
    # study_sha needs no numpy, and CI does not install it.
    try:
        import numpy  # noqa: F401
    except ImportError:
        sys.modules["numpy"] = types.ModuleType("numpy")
    spec = importlib.util.spec_from_file_location("build_deep_nested_lsh_data", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


study_sha = load_generator().study_sha


class StudySha(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        # Keeps git from finding a repository above the temp folder.
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.root)
        self.repo = self.root / "study"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("a\n")
        self.git("add", "a.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", "commit", "-qm", "a")
        self.head = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True).stdout.strip()

    def test_clean_tree_at_sha_passes(self):
        self.assertEqual(study_sha(self.repo, self.head[:7]), self.head[:7])
        self.assertEqual(study_sha(self.repo, None), self.head[:7])

    # Guard: --sha once skipped the clean-tree check, so edited study files could ship under a commit's name.
    def test_dirty_tree_refuses(self):
        (self.repo / "a.txt").write_text("edited\n")
        for given in (self.head[:7], None):
            with self.assertRaises(SystemExit, msg=f"--sha {given}"):
                study_sha(self.repo, given)

    def test_other_sha_refuses(self):
        with self.assertRaises(SystemExit):
            study_sha(self.repo, "0000000")

    def test_without_git_trusts_sha_only(self):
        plain = self.root / "copy"
        plain.mkdir()
        self.assertEqual(study_sha(plain, "abc1234"), "abc1234")
        with self.assertRaises(SystemExit):
            study_sha(plain, None)


if __name__ == "__main__":
    unittest.main()
