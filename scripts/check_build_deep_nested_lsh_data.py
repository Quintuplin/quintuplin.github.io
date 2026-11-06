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
    # study_sha needs no numpy, so the check also runs where numpy is not installed.
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


class TidyRule(unittest.TestCase):
    """Stands in for the tidy rule study's result file and corpus constants."""

    corpus = types.SimpleNamespace(NOISE=0.05, NOISE_GROUP=50, FILLER_NOISE_DOCS=1000, MIN_DEPTH=2, SEARCH_MAX_DEPTH=10)

    @staticmethod
    def cell(dataset, n, mix, b, t, fit_e=12.5, f1_e=10.0):
        return {"dataset": dataset, "n": n, "mix": mix, "m": 8.0, "t": t, "b": b, "role": "fit", "group": "fit",
                "rules": {"KA": {"dims": [9], "e": 9.0, "work": 9},
                          "KAlambda": {"k": 2, "dims": [5, 20], "e": fit_e, "rho": 1.0, "work": 33},
                          "F1": {"k": 3, "dims": [2, 22, 5], "e": f1_e, "rho": 0.9, "work": 33}}}

    def result(self, name="F1", elegant="KAlambda", passed=True):
        switch = {r: {"clears": r == "F1", "p": p, "below": below, "keys": 27, "key_gm_rho": 0.98}
                  for r, p, below in (("KA", 0.4, 16), ("KAlambda", 0.36, 18), ("F1", 7.5e-09, 27))}
        cells = [self.cell("recorded_n1000", 1000, 19, 250, 0.3, 11.0, 10.0), self.cell("n3000_c10", 3000, 10, 250, 0.3, 40.0, 10.0),
                 self.cell("n3000_c10", 3000, 10, 10000, 0.3), self.cell("n1000000_c19", 1000000, 19, 250, 0.3, 99.0, 1.0)]
        # The recorded corpus has no histogram file, as the page carries its pairs.
        hists = {"n3000_c10": "histograms/n3000_c10.csv", "n1000000_c19": "../../scale_study/results/histograms/n1000000_c19.csv"}
        return {"pick": {"name": name, "elegant": elegant, "switch_test": switch}, "cache_check": {"passed": passed}, "cells": cells,
                "histograms": hists, "candidates": [{"name": "KA", "constants": {"gamma": 0.9}}, {"name": "KAlambda", "constants": {"gamma": 0.05}}]}

    # N 1000000 lies past the page's N list, so its cells add neither a dataset nor a cell to the excess.
    def test_tidy_data_reads_rule_constants(self):
        data = generator.tidy_data(self.result(), self.corpus)
        excess = data.pop("excess")
        self.assertEqual(data, {"rule": "KAlambda", "pick": "F1", "gamma": 0.05, "noise": 0.05, "noise_group": 50, "filler_cap": 1000,
                                "depths": [2, 10], "corpus_mix": 19, "datasets": [[1000, 19], [3000, 10]],
                                "switch": {"KAlambda": {"below": 18, "keys": 27, "p": 0.36, "clears": False},
                                           "F1": {"below": 27, "keys": 27, "p": 7.5e-09, "clears": True}}})
        self.assertEqual([b for b, _ in excess], [250, 10000])
        self.assertAlmostEqual(excess[0][1], (1.1 * 4.0) ** 0.5 - 1, places=12)
        self.assertAlmostEqual(excess[1][1], 0.25, places=12)

    # The page twins F1 and the KAlambda fit, so another pick or an unchecked cache must not ship under their names.
    def test_tidy_data_requires_f1_pick(self):
        for result in (self.result(name="KAlambda"), self.result(elegant="KA"), self.result(passed=False)):
            with self.assertRaises(SystemExit):
                generator.tidy_data(result, self.corpus)

    def test_tidy_rows_keep_top_budget(self):
        cells = [self.cell("n3000_c10", 3000, 10, 1000, 0.3), self.cell("n3000_c10", 3000, 10, 10000, 0.3),
                 self.cell("n3000_c10", 3000, 10, 100000, 0.5)]
        full = generator.tidy_rows(cells)
        self.assertEqual(len(full), 3)
        self.assertEqual(full[0]["dims"], [5, 20])
        self.assertEqual(generator.tidy_rows(cells, 10000), [{"n": 3000, "mix": 10, "m": 8.0, "t": 0.3, "dims": [5, 20], "e": 12.5}])

    def test_tidy_rows_carry_f1(self):
        cells = [self.cell("n3000_c10", 3000, 10, 1000, 0.3), self.cell("n1000000_c19", 1000000, 19, 1000, 0.3)]
        self.assertEqual(generator.tidy_rows(cells), [{"dataset": "n3000_c10", "n": 3000, "mix": 10, "m": 8.0, "t": 0.3, "b": 1000, "dims": [5, 20],
                                                       "e": 12.5, "work": 33, "f1": {"dims": [2, 22, 5], "e": 10.0, "work": 33}}])
        self.assertEqual(len(generator.tidy_rows(cells, 1000)), 1, "the page rows skip N past its list too")


def decode(cols):
    """The page's decodeHistogram: den deltas, nums that restart at each new den, counts."""
    out, num, den = [], 0, 0
    for d, n, c in zip(cols["d"], cols["n"], cols["c"]):
        den += d
        num = n if d else num + n
        out.append([num, den, c])
    return out


class Histograms(unittest.TestCase):
    # 1/2 and 2/4 are one similarity. s 0 and s 1 add no error under any curve, and an empty row adds nothing.
    def test_histogram_columns_round_trip(self):
        rows = [(0, 5, 7), (1, 2, 3), (2, 4, 4), (3, 3, 2), (1, 3, 5), (2, 3, 1), (5, 7, 0)]
        cols = generator.histogram_columns(rows)
        self.assertEqual(cols, {"d": [2, 1, 0], "n": [1, 1, 1], "c": [7, 5, 1]})
        self.assertEqual(decode(cols), [[1, 2, 7], [1, 3, 5], [2, 3, 1]])

    def test_histograms_skip_n_past_page_list(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        results = Path(tmp.name)
        (results / "h").mkdir()
        # Three documents give three pairs.
        (results / "h/n3.csv").write_text("num,den,count\n0,4,1\n1,4,1\n2,4,1\n")
        result = {"histograms": {"n3": "h/n3.csv", "n1000000_c19": "h/missing.csv"},
                  "cells": [{"dataset": "n3", "n": 3, "mix": 2}, {"dataset": "n1000000_c19", "n": 1000000, "mix": 19}]}
        out = generator.histograms(results, result, "abc1234")
        self.assertEqual(out, {"sha": "abc1234", "datasets": {"n3": {"docs": 3, "mix": 2, "d": [2, 2], "n": [1, 1], "c": [1, 1]}}})
        self.assertEqual(decode(out["datasets"]["n3"]), [[1, 2, 1], [1, 4, 1]])
        (results / "h/n3.csv").write_text("num,den,count\n1,4,1\n")
        with self.assertRaises(AssertionError, msg="a histogram short of N (N - 1) / 2 pairs"):
            generator.histograms(results, result, "abc1234")


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
