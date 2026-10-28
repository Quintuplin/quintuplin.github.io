#!/usr/bin/env python3
"""Check that the Deep Nested LSH generator pins its data to one clean study commit and reads the study's depth cap.

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


generator = load_generator()
study_sha = generator.study_sha


class StudyGrid(unittest.TestCase):
    """Stands in for lsh_grid_analysis at its depth cap rule, which has no CASCADE_MAX_DEPTH."""

    lga = types.SimpleNamespace(SEARCH_MAX_DEPTH=10, TRIM_DEPTH=5, CASCADE_THRESHOLD_TOLERANCE=0.01, CASCADE_MAX_FREE_ARITY=24,
                                EQUAL_ROWS_TOLERANCE=0.05,
                                reported_depth_cap=lambda best: 5 if max(best.values()) <= 5 else 10)

    def best_table(self, depths):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "lsh_best_depth_table.txt"
        lines = ["target  sweep   best depth", "------  ------  ----------"]
        lines += [f"{t:<6}  {s:<6}  {d:<10}" for t, s, d in depths]
        path.write_text("\n".join(lines) + "\n")
        return generator.read_table(path)

    # Guard: main()'s provenance read lga.CASCADE_MAX_DEPTH, which the study dropped, and crashed with an AttributeError.
    def test_grid_cap_reads_best_depth_table(self):
        deep = self.best_table([(0.3, "equal", 6), (0.5, "equal", 9), (0.8, "n1000", 5)])
        self.assertEqual(deep["kind"], "best_depth")
        self.assertEqual(deep["rows"][1], {"target": 0.5, "sweep": "equal", "best depth": 9})
        prov = generator.provenance("abc1234", self.lga, {"lsh_best_depth_table": deep})
        grid = prov["grid"]
        self.assertEqual(prov["sha"], "abc1234")
        self.assertEqual((grid["max_depth"], grid["search_max_depth"], grid["trim_depth"]), (10, 10, 5))
        shallow = self.best_table([(0.3, "equal", 5), (0.5, "n250", 3)])
        self.assertEqual(generator.provenance("abc1234", self.lga, {"lsh_best_depth_table": shallow})["grid"]["max_depth"], 5)


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
