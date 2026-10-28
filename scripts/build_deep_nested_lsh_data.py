"""Regenerate the Deep Nested LSH page data and its parity fixture from a study checkout.

Usage: build_deep_nested_lsh_data.py --study <dir> [--sha <sha>]
CI never runs this. It needs the study's Python environment and its corpus under <dir>/files.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

SITE = Path(__file__).resolve().parent.parent
PAGE = SITE / "simulations/deep-nested-lsh/index.html"
FIXTURE = SITE / "scripts/fixtures/deep-nested-lsh-parity.json"
TABLE_KINDS = ["cascade", "equal_rows", "error_area", "high_cap_family", "algorithm", "quorum", "seed_spread"]
S_GRID = [0.0, 1e-06, 0.01] + [round(0.05 * i, 2) for i in range(1, 20)] + [0.99, 0.999999, 1.0]
Y_GRID = [0.05, 0.5, 0.95]
TARGETS = [0.3, 0.5, 0.8]
# Hand-picked shapes beside the table tuples: textbook bandings, arity 1 levels and the flat collapse pair.
EXTRA_DIMS = [(1,), (4, 10), (7, 69), (3, 8, 2), (2, 5, 3, 4), (2, 4, 2, 3, 2), (5, 5, 4), (5, 20), (100, 1), (7, 23, 3)]
HASH_SAMPLES = 64
# Small trees for the brute-force pipeline: banding, depth 3 and 4, and a depth 5 tree whose kept bands sit scattered.
BRUTE_DIMS = [(4,), (3, 5), (2, 2, 3), (2, 4, 2), (2, 2, 2, 2), (2, 2, 1, 2, 2)]


# ---- StudyTables ----
def parse_cell(text: str):
    if text == "--":
        return None
    if re.fullmatch(r"\(\d+(, \d+)*,?\)", text):
        return [int(v) for v in re.findall(r"\d+", text)]
    if re.fullmatch(r"\d+(x\d+)+", text):
        return [int(v) for v in text.split("x")]
    if re.fullmatch(r"\d+(,\d+)+", text):
        return [int(v) for v in text.split(",")]
    if re.fullmatch(r"\d+D", text):
        return int(text[:-1])
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def read_table(path: Path) -> dict:
    """One render_table text file. The dash rule under the header gives the column spans."""
    header, rule, *lines = path.read_text(encoding="utf-8").splitlines()
    spans = [m.span() for m in re.finditer(r"-+", rule)]
    cut = lambda line: [line[a:b].strip() for a, b in spans]
    names = cut(header)
    rows, decimals = [], {}
    for line in lines:
        cells = cut(line)
        rows.append({k: parse_cell(v) for k, v in zip(names, cells)})
        for k, v in zip(names, cells):
            if re.fullmatch(r"-?\d+\.\d+", v):
                decimals[k] = len(v.split(".")[1])
    kind = next(k for k in TABLE_KINDS if path.stem.startswith(f"lsh_{k}"))
    tag = re.search(r"_t(\d+)(?:_n(\d+))?$", path.stem)
    return {"kind": kind, "target": int(tag.group(1)) / 100 if tag else None,
            "budget": int(tag.group(2)) if tag and tag.group(2) else None, "rows": rows, "decimals": decimals}


def read_tables(study: Path) -> dict:
    paths = sorted(p for k in TABLE_KINDS for p in (study / "output").glob(f"lsh_{k}*.txt"))
    return {p.stem: read_table(p) for p in paths}


def corpus_facts(lga, study: Path) -> dict:
    """Corpus pairs as (num, den, count) per distinct nonzero Jaccard, checked against the study's histogram."""
    data = lga.load_corpus(study / "files")
    member = np.zeros((len(data.sets), data.universe), dtype=np.int32)
    for i, doc in enumerate(data.sets):
        member[i, list(doc)] = 1
    inter = member @ member.T
    sizes = member.sum(axis=1)
    union = sizes[:, None] + sizes[None, :] - inter
    upper = np.triu_indices(len(data.sets), k=1)
    tally: dict[Fraction, int] = {}
    for a, b in zip(inter[upper].tolist(), union[upper].tolist()):
        if a:
            f = Fraction(a, b)
            tally[f] = tally.get(f, 0) + 1
    pairs = [[f.numerator, f.denominator, c] for f, c in sorted(tally.items())]
    sims, counts = lga.similarity_histogram(lga.exact_jaccard_matrix(data))
    keep = sims > 0
    assert [n / d for n, d, _ in pairs] == sims[keep].tolist() and [c for *_, c in pairs] == counts[keep].tolist()
    return {"docs": len(data.sets), "vocab": data.universe, "set_median": float(np.median(sizes)),
            "set_min": int(sizes.min()), "set_max": int(sizes.max()), "pairs": pairs}


def study_sha(study: Path, given: str | None) -> str:
    """Study HEAD of a clean tree, which --sha must name. Where git cannot read the study, such as the study container, --sha stands alone."""
    git = lambda *a: subprocess.run(["git", "-C", str(study), *a], capture_output=True, text=True, check=True).stdout.strip()
    try:
        head = git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        if given:
            return given
        raise SystemExit(f"git cannot read {study}; pass --sha with the study commit")
    if git("status", "--porcelain"):
        raise SystemExit(f"{study} has uncommitted changes; the data must come from one commit")
    if given and not (len(given) >= 7 and head.startswith(given.lower())):
        raise SystemExit(f"--sha {given} is not {study} HEAD {head[:7]}")
    return given or head[:7]


# ---- ParityExport ----
def table_dims(tables: dict) -> list[tuple[int, ...]]:
    out = []
    for t in tables.values():
        for r in t["rows"]:
            dims = r.get("tuple") if t["kind"] == "algorithm" else r.get("dims")
            if isinstance(dims, list):
                out.append(tuple(dims))
    return out


def paper_tuples(tables: dict) -> dict[tuple[int, ...], set[float]]:
    """Cascade and equal-rows tuples with the targets they are scored at."""
    out: dict[tuple[int, ...], set[float]] = {}
    for t in tables.values():
        if t["kind"] in ("cascade", "equal_rows"):
            for r in t["rows"]:
                out.setdefault(tuple(r["dims"]), set()).add(t["target"])
    return out


def parity_rows(lga, tables: dict, facts: dict) -> list[dict]:
    pairs = np.array(facts["pairs"], dtype=float)
    sims, counts = pairs[:, 0] / pairs[:, 1], pairs[:, 2]
    s = np.array(S_GRID)
    paper = paper_tuples(tables)
    rows = []
    for dims in dict.fromkeys(EXTRA_DIMS + table_dims(tables)):
        n = lga.dims_total_rows(dims)
        row = {
            "dims": list(dims),
            "curve": lga.cascade_curve(s, dims).tolist(),
            "inverse": [lga.cascade_inverse(y, dims) for y in Y_GRID],
            "threshold": lga.cascade_threshold(dims),
            "bands": [lga.bands_for_threshold(t, dims) for t in TARGETS],
            "width": lga.cascade_transition_width(dims),
            "area": [lga.cascade_error_area(dims, t) for t in TARGETS],
            "tails": list(lga.cascade_tail_exponents(dims)),
            "counts": [list(lga.expected_counts(lga.cascade_curve(sims, dims), sims, counts, t)) for t in TARGETS],
        }
        if dims in paper:
            row["quorum"] = {str(t): {"full": lga.quorum_curve(s, n, t).tolist(),
                                      "pipeline": lga.quorum_curve(s, n, t, lga.retrieval_dims(dims)).tolist()}
                             for t in sorted(paper[dims])}
        rows.append(row)
    return rows


def no_nan(v):
    """JSON has no NaN, so it travels as null."""
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, list):
        return [no_nan(x) for x in v]
    if isinstance(v, dict):
        return {k: no_nan(x) for k, x in v.items()}
    return v


def hash_samples(demo, vocab: int) -> list[list[str]]:
    """(a, c, x, h) with h = (a x + c) mod 2^61 - 1 as the study hashes rows. Decimal strings keep all 61 bits."""
    p = demo.MERSENNE_PRIME
    rng = np.random.default_rng(753)
    a = rng.integers(1, p, size=HASH_SAMPLES, dtype=np.int64).astype(np.uint64)
    c = rng.integers(0, p, size=HASH_SAMPLES, dtype=np.int64).astype(np.uint64)
    x = rng.integers(0, vocab, size=HASH_SAMPLES, dtype=np.int64).astype(np.uint64)
    # The extremes of every operand.
    a[:2], c[:2], x[:2] = [p - 1, 1], [p - 1, 0], [vocab - 1, 0]
    h = demo.reduce61(demo.mulmod61(a, x) + c)
    assert all(int(hv) == (int(av) * int(xv) + int(cv)) % p for av, cv, xv, hv in zip(a, c, x, h))
    return [[str(int(v)) for v in t] for t in zip(a, c, x, h)]


def brute_force_pipeline(lga) -> list[dict]:
    """P[accept] of retrieve then verify by summing every agreement pattern over n <= 16 rows.

    Doc 0 is the query and doc p + 1 agrees with it on the rows set in p, so the study's own retrieval matrix
    says which patterns a kept band retrieves."""
    s = np.array(S_GRID)
    out = []
    for dims in BRUTE_DIMS:
        n = lga.dims_total_rows(dims)
        patterns = np.arange(2**n)
        bits = (patterns[None, :] >> np.arange(n)[:, None]) & 1
        retrieved = np.concatenate([
            lga.retrieval_candidate_matrix(np.hstack([np.zeros((n, 1), dtype=np.int64), np.where(chunk, 0, 1 + np.arange(chunk.shape[1]))]),
                                           dims, chunk.shape[1] + 1)[0, 1:]
            for chunk in np.array_split(bits, max(1, 2**n // 256), axis=1)])
        agree = bits.sum(axis=0)
        curves = {}
        for t in TARGETS:
            accepted = np.bincount(agree[retrieved & (agree >= lga.quorum_need(n, t))], minlength=n + 1)
            curve = sum(c * s**k * (1 - s) ** (n - k) for k, c in enumerate(accepted.tolist()))
            assert np.allclose(curve, lga.quorum_curve(s, n, t, lga.retrieval_dims(dims)), rtol=1e-9, atol=1e-12), (dims, t)
            curves[str(t)] = curve.tolist()
        out.append({"dims": list(dims), "pipeline": curves})
    return out


def write(page: Path, fixture: Path, data: dict, parity: dict) -> None:
    html = page.read_text(encoding="utf-8")
    head = '<script type="application/json" id="sim-data">\n'
    start = html.index(head) + len(head)
    end = html.index("\n</script>", start)
    page.write_text(html[:start] + json.dumps(no_nan(data), separators=(",", ":"), allow_nan=False) + html[end:], encoding="utf-8")
    fixture.write_text(json.dumps(no_nan(parity), indent=1, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--study", type=Path, required=True)
    ap.add_argument("--sha", help="study commit, for a checkout without git")
    args = ap.parse_args()
    study = args.study.resolve()
    sha = study_sha(study, args.sha)
    sys.path.insert(0, str(study))
    import lsh_demo as demo
    import lsh_grid_analysis as lga

    tables = read_tables(study)
    corpus = corpus_facts(lga, study)
    data = {
        "provenance": {"sha": sha, "grid": {"max_depth": lga.CASCADE_MAX_DEPTH, "tolerance": lga.CASCADE_THRESHOLD_TOLERANCE,
                                            "max_free_arity": lga.CASCADE_MAX_FREE_ARITY,
                                            "equal_rows_tolerance": lga.EQUAL_ROWS_TOLERANCE}},
        "facts": {"top_budget": lga.MAX_SIGNATURE_ROWS, "corpus": corpus},
        "tables": tables,
    }
    parity = {"source": f"lsh_grid_analysis at {sha}", "s": S_GRID, "y": Y_GRID, "targets": TARGETS,
              "rows": parity_rows(lga, tables, corpus), "hashes": hash_samples(demo, corpus["vocab"]),
              "brute": brute_force_pipeline(lga)}
    write(PAGE, FIXTURE, data, parity)
    print(f"wrote {PAGE.relative_to(SITE)} and {FIXTURE.relative_to(SITE)} from {sha}")


if __name__ == "__main__":
    main()
