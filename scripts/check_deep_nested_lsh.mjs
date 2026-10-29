// Maths parity checks for the Deep Nested LSH page (#31). Usage: node check_deep_nested_lsh.mjs <page>
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  PageScripts, C, study, MAX_DEPTH, PAIRS, SEARCH_WORK, same, counts, tablesOf, drainSearch, PAIR, realised,
  quorumTable, retrievalOf, quorumCounts, verifyRows,
} from "./deep_nested_lsh_support.mjs";

const parity = JSON.parse(readFileSync(new URL("fixtures/deep-nested-lsh-parity.json", import.meta.url), "utf8"));
const SEARCH_STEP = Number(PageScripts.read("cascade-src").match(/\bSEARCH_STEP = (\d+)/)[1]);

// ---- TableCheck: every printed table value the maths can reproduce ----
const EXPECTED = ["E[FP]", "E[FN]", "E[errors]", "E[retrieved]"];
const CHECKS = {
  cascade: ["rows", "threshold", "width", "fp_exp x fn_exp", ...EXPECTED],
  equal_rows: ["rows", "threshold", "width", "fp_exp x fn_exp", ...EXPECTED],
  high_cap_family: ["rows", "threshold", "width", "fp_exp x fn_exp"],
  error_area: ["rows", "threshold", "width", "error_area"],
  algorithm: ["rows", "fp_exp", "fn_exp"],
};

function computed(field, d, target) {
  switch (field) {
    case "rows": return C.rows(d);
    case "threshold": return C.threshold(d);
    case "width": return C.width(d);
    case "error_area": return C.errorArea(d, target);
    case "fp_exp": return C.tails(d)[0];
    case "fn_exp": return C.tails(d)[1];
    case "fp_exp x fn_exp": return C.tails(d);
    case "E[FP]": return counts(d, target).fp;
    case "E[FN]": return counts(d, target).fn;
    case "E[errors]": return counts(d, target).errors;
    // A query probes the banding (d0, f-), so its candidates are the retrieved volume.
    case "E[retrieved]": return counts([d[0], C.tails(d)[1]], target).candidates;
  }
}

// Compared at the precision the table prints. E[retrieved] prints as a rounded whole number.
const agrees = (printed, value, dec) => (Array.isArray(printed) || dec === undefined
  ? JSON.stringify(printed) === JSON.stringify(value)
  : Math.abs(value - printed) <= 0.5 * Math.pow(10, -dec) + 1e-9);

function tableChecks(tables) {
  const out = [];
  const seeds = Object.values(tables).filter((t) => t.kind === "seed_spread").flatMap((t) => t.rows);
  const push = (stem, t, d, field, printed, value, dec = t.decimals[field]) =>
    out.push({ table: stem, kind: t.kind, dims: d, field, printed, computed: value, ok: agrees(printed, value, dec) });
  for (const [stem, t] of Object.entries(tables)) {
    if (t.kind === "seed_spread") {
      for (const row of t.rows) {
        const draws = row["errors by draw"], { mean, sd } = C.spread(draws);
        push(stem, t, row.config, "draws", row.draws, draws.length);
        push(stem, t, row.config, "measured", row.measured, draws[0]);
        push(stem, t, row.config, "mean", row.mean, mean);
        push(stem, t, row.config, "sd", row.sd, sd);
      }
    }
    const fields = CHECKS[t.kind];
    if (!fields) continue;
    const dimsCol = t.kind === "algorithm" ? "tuple" : "dims";
    for (const row of t.rows) {
      const d = row[dimsCol];
      for (const field of fields) push(stem, t, d, field, row[field], computed(field, d, t.target), field === "E[retrieved]" ? 0 : undefined);
      // The table's measured errors are draw 0 of the seed spread.
      const seed = seeds.find((s) => s.target === t.target && s.config === row.config);
      if (seed && "errors" in row) push(stem, t, d, "errors as seed draw 0", row.errors, seed.measured);
    }
  }
  return out;
}

// ---- ParityChecks: the page maths against the study's reference values ----
function close(actual, expected, what) {
  if (expected === null) return assert.ok(Number.isNaN(actual), `${what}: expected NaN, got ${actual}`);
  const tol = Math.max(1e-12, 1e-9 * Math.abs(expected));
  assert.ok(Math.abs(actual - expected) <= tol, `${what}: ${actual} vs reference ${expected}`);
}

test("matchesReferenceParity", () => {
  assert.ok(parity.rows.length >= 100);
  for (const r of parity.rows) {
    const d = r.dims;
    parity.s.forEach((s, i) => close(C.curve(s, d), r.curve[i], `curve ${d} at ${s}`));
    parity.y.forEach((y, i) => close(C.inverse(y, d), r.inverse[i], `inverse ${d} at ${y}`));
    close(C.threshold(d), r.threshold, `threshold ${d}`);
    parity.targets.forEach((t, i) => close(C.bandsForThreshold(t, d), r.bands[i], `bands ${d} at ${t}`));
    close(C.width(d), r.width, `width ${d}`);
    parity.targets.forEach((t, i) => close(C.errorArea(d, t), r.area[i], `area ${d} at ${t}`));
    assert.deepEqual(C.tails(d), r.tails, `tails ${d}`);
    parity.targets.forEach((t, i) => {
      const c = counts(d, t), [fp, fn, candidates] = r.counts[i];
      close(c.fp, fp, `E[FP] ${d} at ${t}`);
      close(c.fn, fn, `E[FN] ${d} at ${t}`);
      close(c.candidates, candidates, `candidates ${d} at ${t}`);
    });
  }
});

test("parityPinnedAtProvenanceSha", () => {
  // The fixture and the page tables must come from the same study commit.
  assert.equal(parity.source, `lsh_grid_analysis at ${study.provenance.sha}`);
  const have = new Set(parity.rows.map((r) => r.dims.join(",")));
  const stems = ["lsh_cascade_table_", "lsh_error_area_table_", "lsh_high_cap_family_table_", "lsh_equal_rows_table_"];
  for (const [stem, t] of Object.entries(study.tables)) {
    if (!stems.some((s) => stem.startsWith(s))) continue;
    for (const r of t.rows) assert.ok(have.has(r.dims.join(",")), `${stem} tuple ${r.dims} has no parity row`);
  }
  assert.ok(parity.rows.every((r) => r.counts?.length === parity.targets.length), "every parity row carries expected counts per target");
});

// The depth cap follows the study's rule over its best measured depths: the trim depth unless a ladder does best deeper.
test("gridCapFollowsBestDepthTable", () => {
  const best = study.tables.lsh_best_depth_table?.rows || [];
  assert.ok(best.length, "the page embeds the study's best-depth table");
  const { trim_depth: trim, search_max_depth: deepest } = study.provenance.grid;
  assert.ok(trim >= 2 && deepest >= trim, `trim depth ${trim} and search depth ${deepest}`);
  assert.equal(MAX_DEPTH, Math.max(...best.map((r) => r["best depth"])) <= trim ? trim : deepest);
  // The study trims its tables to the cap, so the deepest table tree sits at it.
  assert.equal(Math.max(...tablesOf("cascade", "equal_rows").flatMap((t) => t.rows.map((r) => r.depth))), MAX_DEPTH);
});

test("reproducesPrintedTableValues", () => {
  const checks = tableChecks(study.tables);
  assert.ok(checks.length >= 1000, `only ${checks.length} checks`);
  const bad = checks.filter((c) => !c.ok);
  assert.deepEqual(bad, []);
  for (const kind of ["cascade", "equal_rows", "error_area", "high_cap_family", "algorithm", "seed_spread"]) {
    assert.ok(checks.some((c) => c.kind === kind), `no checks on ${kind}`);
  }
  for (const field of [...EXPECTED, "mean", "sd", "errors as seed draw 0"]) {
    assert.ok(checks.some((c) => c.field === field), `no checks on ${field}`);
  }
});

// ---- CurveChecks: search, tree, log tail and trial maths ----
// Cascade rows are the sharpest tree within n{budget} rows. Equal-rows rows hold their rows within the window around n{ref}.
test("bestTreeMatchesTables", () => {
  const { tolerance, max_free_arity: freeCap, equal_rows_tolerance: band } = study.provenance.grid;
  assert.equal(C.TOLERANCE, tolerance);
  assert.equal(C.MAX_FREE_ARITY, freeCap);
  let searched = 0;
  for (const t of tablesOf("cascade", "equal_rows")) {
    for (const row of t.rows) {
      const d = row.dims, [, ref, depth] = row.config.match(/^n(\d+)_d(\d+)$/).map(Number);
      const solved = C.bandsForThreshold(t.target, d);
      const options = [Math.max(2, Math.floor(solved)), Math.max(2, Math.ceil(solved))];
      assert.ok(options.includes(d[1]), `${row.config} t ${t.target}: d1 ${d[1]} not in ${options}`);
      const [low, high] = t.kind === "cascade" ? [1, ref] : [Math.floor(ref * (1 - band)), Math.floor(ref * (1 + band))];
      // The explorer's capped search finishes on every table tree.
      const r = drainSearch(C.treeSearch(high, depth, t.target, low, SEARCH_WORK), Infinity);
      assert.ok(r.complete, `${t.kind} ${row.config} t ${t.target} stops at the work cap`);
      assert.deepEqual(r.dims, d, `${t.kind} ${row.config} t ${t.target}`);
      searched += 1;
    }
  }
  assert.ok(searched >= 60, `only ${searched} tuples searched`);
});

// The depth 1 scan stops early once t̂ passes t, which no table row reaches.
test("bestTreeDepthOneMatchesFullScan", () => {
  const scan = (n, t) => {
    let best = null;
    for (let r = 1; r <= n; r++) {
      const d = [r];
      if (Math.abs(C.threshold(d) - t) <= C.TOLERANCE && (!best || C.width(d) < C.width(best))) best = d;
    }
    return best;
  };
  for (const n of [1, 2, 7, 64, 500, 5000]) {
    for (const t of [0.01, 0.05, 0.3, 0.5, 0.8, 0.95, 0.99]) assert.deepEqual(C.bestTree(n, 1, t), scan(n, t), `n ${n} t ${t}`);
  }
});

// Plain port of enumerate_cascade_configs and best_cascade_config with free arities up to maxArity.
function scanTrees(budget, depth, t, low = 1, maxArity = C.MAX_FREE_ARITY) {
  let best = null, bestW = Infinity;
  const consider = (d) => {
    const n = C.rows(d);
    if (n < low || n > budget || Math.abs(C.threshold(d) - t) > C.TOLERANCE) return;
    const w = C.width(d);
    if (w < bestW) [best, bestW] = [d, w];
  };
  function* free(d0, chosen, product) {
    if (chosen.length === depth - 2) { yield chosen; return; }
    for (let a = 2; a <= maxArity && d0 * product * a * 2 <= budget; a++) yield* free(d0, [...chosen, a], product * a);
  }
  for (let d0 = 2; d0 <= budget; d0++) {
    const probe = C.bandsForThreshold(t, [d0, 1, ...Array(depth - 2).fill(2)]);
    if (Number.isNaN(probe)) continue;
    if (d0 * Math.max(probe, 2) * 2 ** (depth - 2) > budget) break;
    for (const f of free(d0, [], 1)) {
      const solved = C.bandsForThreshold(t, [d0, 1, ...f]);
      if (Number.isNaN(solved) || solved < 1.5) continue;
      for (const b of new Set([Math.max(2, Math.floor(solved)), Math.max(2, Math.ceil(solved))])) consider([d0, b, ...f]);
    }
  }
  return best;
}

test("treeSearchMatchesExhaustiveScan", () => {
  const cases = [];
  // Depth 6 and 7 over 1e5 rows take seconds each, so depth 7 at t 0.5 covers them.
  for (const t of [0.05, 0.2, 0.3, 0.5, 0.8, 0.95, 0.99]) {
    for (let k = 2; k <= 7; k++) for (const n of [50, 1e3, 3e4, 1e5]) if (k < 6 || n < 1e5 || (k === 7 && t === 0.5)) cases.push([n, k, t]);
    for (let k = 8; k <= 10; k++) for (const n of [1e3, 1e4]) cases.push([n, k, t]);
  }
  cases.push([3e4, 10, 0.5]);
  for (const [n, k, t] of cases) {
    const r = drainSearch(C.treeSearch(n, k, t), Infinity);
    assert.equal(r.complete, true);
    assert.deepEqual(r.dims, scanTrees(n, k, t), `depth ${k} within ${n} rows at t ${t}`);
  }
});

// Guard: the depth search once enumerated billions of trees at depth 10 over 10 million rows.
// cappedSearchCoversItsArityShells covers capped results at other targets, so the full cap runs only at t 0.3, its costliest target.
test("deepSearchFinishesWithinWorkCap", () => {
  assert.ok(SEARCH_WORK > 0, "the explorer sets a search work cap");
  const t = 0.3, t0 = performance.now(), r = drainSearch(C.treeSearch(1e7, 10, t, 1, SEARCH_WORK), SEARCH_WORK / SEARCH_STEP + 1e4);
  const s = (performance.now() - t0) / 1000;
  assert.ok(s < 20, `the capped search took ${s.toFixed(1)} s`);
  assert.equal(r.complete, false, "depth 10 over 10 million rows needs the cap");
  assert.ok(r.arity >= 2, `shells up to ${r.arity} finished`);
  assert.equal(r.dims.length, 10);
  assert.ok(Math.abs(C.threshold(r.dims) - t) <= C.TOLERANCE && C.rows(r.dims) <= 1e7, String(r.dims));
});

// A capped search is at least as sharp as the full scan over the arity shells it finished.
test("cappedSearchCoversItsArityShells", () => {
  for (const [n, k, t, limit] of [[1e5, 6, 0.5, 2e4], [1e5, 7, 0.8, 5e4], [3e4, 5, 0.3, 3e3]]) {
    const r = drainSearch(C.treeSearch(n, k, t, 1, limit), Infinity), ref = scanTrees(n, k, t, 1, r.arity);
    assert.equal(r.complete, false, `depth ${k} within ${n} rows stops at ${limit} nodes`);
    assert.ok(r.arity >= 2 && r.arity < C.MAX_FREE_ARITY, `shells up to ${r.arity}`);
    assert.ok(ref && C.width(r.dims) <= C.width(ref), `depth ${k}: ${r.dims} against ${ref} with arities up to ${r.arity}`);
  }
});

test("solveD1PicksSharpestMatch", () => {
  const near = (d, t) => Math.abs(C.threshold(d) - t) <= C.TOLERANCE;
  let both = 0;
  for (const t of Object.values(study.tables)) {
    if (!["cascade", "equal_rows", "high_cap_family"].includes(t.kind)) continue;
    for (const row of t.rows) {
      if (row.dims.length < 2) continue;
      const solved = C.bandsForThreshold(t.target, row.dims);
      const [lo, hi] = [Math.floor(solved), Math.ceil(solved)].map((b) => { const d = row.dims.slice(); d[1] = Math.max(2, b); return d; });
      if (lo[1] === hi[1] || !near(lo, t.target) || !near(hi, t.target)) continue;
      const want = C.width(hi) < C.width(lo) ? hi : lo;
      assert.deepEqual(C.solveD1(row.dims, t.target), { dims: want, matched: true }, `${row.config} t ${t.target}`);
      both += 1;
    }
  }
  assert.ok(both > 0, "some rows match at both floor and ceil");
  // Depth 1 solves d0. 0.5^(1/3) lies within the tolerance of 0.8.
  assert.deepEqual(C.solveD1([5], 0.8), { dims: [3], matched: true });
  // No single band reaches below 0.5, so the closest is d0 1 and unmatched.
  assert.deepEqual(C.solveD1([5], 0.3), { dims: [1], matched: false });
  // d1 5 and 6 both match t 0.9 and 5 is narrower, so the last matched option is not the pick.
  assert.deepEqual(C.solveD1([20, 1], 0.9), { dims: [20, 5], matched: true });
});

test("evalTreeMatchesCurve", () => {
  for (const dims of [[2], [2, 3], [2, 3, 2], [1, 2, 2, 2]]) {
    const n = C.rows(dims);
    for (const s of [0.2, 0.5, 0.7]) {
      let mass = 0;
      for (let m = 0; m < 1 << n; m++) {
        const bits = Uint8Array.from({ length: n }, (_, i) => (m >> i) & 1);
        const ones = bits.reduce((a, b) => a + b, 0);
        const levels = C.evalTree(bits, dims);
        assert.equal(levels.length, dims.length);
        assert.equal(levels[dims.length - 1].length, 1);
        if (levels[dims.length - 1][0]) mass += s ** ones * (1 - s) ** (n - ones);
      }
      assert.ok(Math.abs(mass - C.curve(s, dims)) < 1e-12, `${dims} at ${s}: ${mass}`);
    }
  }
  const [lo, hi] = [0, 5, 10].map((k) => C.wilson(k, 10)).reduce((a, w) => [[...a[0], w[0]], [...a[1], w[1]]], [[], []]);
  [0.0, 0.2366, 0.7225].forEach((v, i) => assert.ok(Math.abs(lo[i] - v) < 1e-4, `wilson lo ${i}`));
  [0.2775, 0.7634, 1.0].forEach((v, i) => assert.ok(Math.abs(hi[i] - v) < 1e-4, `wilson hi ${i}`));
  for (const r of parity.rows) {
    const { fplus, fminus } = C.localSlopes(r.dims);
    assert.ok(Math.abs(fplus / r.tails[0] - 1) < 1e-3, `f+ slope ${r.dims}: ${fplus}`);
    assert.ok(Math.abs(fminus / r.tails[1] - 1) < 1e-3, `f- slope ${r.dims}: ${fminus}`);
  }
});

// ---- HashChecks: trial rows hash as the study's do, h(x) = (a x + c) mod 2^61 − 1 ----
const P61 = (1n << 61n) - 1n;
// A value below 2^62 as its 30 and 31 bit halves.
const halves = (v) => [Number(BigInt(v) >> 31n), Number(BigInt(v) & 0x7fffffffn)];
const join = (hi, lo) => (BigInt(hi) << 31n) + BigInt(lo);
const hashOf = (a, c, x) => join(...C.hash61([...halves(a), ...halves(c)], 0, x, new Float64Array(2)));

test("hash61MatchesBigInt", () => {
  const rng = C.mulberry32(61), word = () => join(Math.floor(rng() * 2 ** 30), Math.floor(rng() * 2 ** 31));
  const edges = [0n, 1n, P61 - 1n, P61], cases = [];
  // a = p − 1, c = 1 and x = 1 lands on p itself, which must read 0.
  for (const a of edges.slice(1)) for (const c of edges) for (const x of [0, 1, 2 ** 14 - 1, 2 ** 22 - 1]) cases.push([a, c, x]);
  for (let i = 0; i < 5000; i++) cases.push([word(), word(), Math.floor(rng() * 2 ** 22)]);
  for (const [a, c, x] of cases) assert.equal(hashOf(a, c, x), (a * BigInt(x) + c) % P61, `a ${a} c ${c} x ${x}`);
});

// Guard: trials once drew rows as coin flips at s instead of the study's linear hashes (critique S9).
test("hashMatchesStudySamples", () => {
  assert.ok(parity.hashes?.length >= 64, "the fixture carries the study's hash samples");
  for (const [a, c, x, h] of parity.hashes) assert.equal(hashOf(a, c, Number(x)), BigInt(h), `a ${a} c ${c} x ${x}`);
});

test("lazyTrialMatchesFullTree", () => {
  const hashes = C.drawRows(C.mulberry32(5)), outcomes = new Set();
  for (const d of [[3], [2, 3], [3, 4, 2], [2, 3, 2, 2], [2, 2, 3, 2, 2]]) {
    for (const s of [0.3, 0.5, 0.8]) {
      const { U, I } = realised(s);
      for (let seed = 1; seed <= 25; seed++) {
        const pair = C.drawPair(s, C.mulberry32(seed), PAIR.size, PAIR.vocab);
        assert.equal(new Set(pair.ids).size, U, `${U} distinct ids at ${s}`);
        assert.ok(pair.ids.every((x) => Number.isInteger(x) && x >= 0 && x < PAIR.vocab));
        assert.equal(pair.s, I / U);
        const full = C.sampleTree(pair, d, hashes), flat = hashes(C.rows(d));
        // A row agrees when the least hash over the union falls on one of the I shared ids.
        if (seed <= 2) {
          full.bits.forEach((bit, i) => {
            const h = pair.ids.map((x) => hashOf(join(flat[4 * i], flat[4 * i + 1]), join(flat[4 * i + 2], flat[4 * i + 3]), x));
            assert.equal(bit, h.indexOf(h.reduce((a, b) => (b < a ? b : a))) < I ? 1 : 0, `row ${i} of ${d} at ${s}`);
          });
        }
        assert.deepEqual(full.levels, C.evalTree(full.bits, d));
        const root = full.levels[d.length - 1][0];
        assert.equal(C.runTrials(s, d, 1, C.mulberry32(seed), hashes, PAIR), root, `${d} at ${s} seed ${seed}`);
        outcomes.add(root);
      }
    }
  }
  assert.deepEqual([...outcomes].sort(), [0, 1], "both outcomes occur");
});

// Guard: the Bernoulli trials matched the curve by construction. Linear-hash trials must match it at the realised s.
test("linearTrialsMatchCurve", () => {
  const hashes = C.drawRows(C.mulberry32(9)), trials = 2000;
  for (const d of [[5, 20], [7, 23, 3], [2, 17, 7, 8, 3]]) {
    const at = [0.2, 0.5, 0.8].map((p) => C.inverse(p, d));
    for (const s of at) {
      const hits = C.runTrials(s, d, trials, C.mulberry32(11), hashes, PAIR), { U, I } = realised(s), p = C.curve(I / U, d);
      assert.ok(Math.abs(hits / trials - p) < 4 * Math.sqrt(p * (1 - p) / trials), `${d} rate ${hits / trials} vs ${p} at ${I}/${U}`);
    }
  }
});

// ---- QuorumChecks: accept at quorum, alone or behind retrieval on the kept bands ----
// Counting a verify row behind retrieval takes up to 2.5 s and longest at low targets (2 s for the deepest row at t 0.3).
// So counts run per target on one depth 2 row and, from t 0.5 up, on one deepest row.
// Guard: a target without a depth 2 row once counted nothing below t 0.5. Each target fails without its counted rows.
const countedRows = (verify) => {
  const picks = new Set();
  for (const t of new Set(verify.map((v) => v.r.target))) {
    const peers = verify.filter((w) => w.r.target === t), deepest = Math.max(...peers.map((w) => w.d?.length ?? 0));
    for (const k of t >= 0.5 ? [2, deepest] : [2]) {
      const row = peers.find((w) => w.d?.length === k);
      assert.ok(row, `the quorum table has a depth ${k} verify row to count at ${t}`);
      picks.add(row);
    }
  }
  return verify.filter((v) => picks.has(v));
};

// One printed quorum row at its print precision. Without `counted` only its threshold, width and retrieved volume.
function checkQuorumRow(r, index, counted = true) {
  const { target: t, rows: n } = r, inv = (y) => C.quorumInverse(y, n, t, index);
  const fields = { threshold: inv(0.5), width: inv(0.95) - inv(0.05) };
  if (counted) {
    const c = quorumCounts(n, t, index);
    Object.assign(fields, { "E[FP]": c.fp, "E[FN]": c.fn, "E[errors]": c.errors });
  }
  if (index) fields.retrieved = counts(index, t).candidates;
  for (const [f, v] of Object.entries(fields)) {
    assert.ok(agrees(r[f], v, f === "retrieved" ? 0 : quorumTable.decimals[f]), `quorum ${n} ${r.retrieval} at ${t} ${f}: ${v} vs ${r[f]}`);
  }
}

const quorumRows = () => parity.rows.filter((r) => r.quorum);

test("quorumMatchesStudy", () => {
  assert.ok(quorumRows().length >= 50);
  for (const r of quorumRows()) {
    for (const [t, q] of Object.entries(r.quorum)) parity.s.forEach((s, i) => close(C.quorumCurve(s, C.rows(r.dims), +t), q.full[i], `quorum ${r.dims} at ${t} s ${s}`));
  }
  const all = quorumTable.rows.filter((r) => r.retrieval === "all");
  assert.equal(all.length, 9);
  all.forEach((r) => checkQuorumRow(r));
});

test("pipelineMatchesStudy", () => {
  for (const r of quorumRows()) {
    for (const [t, q] of Object.entries(r.quorum)) parity.s.forEach((s, i) => close(C.pipelineCurve(s, r.dims, +t), q.pipeline[i], `pipeline ${r.dims} at ${t} s ${s}`));
  }
  const verify = verifyRows();
  // Every quorum row that names a retrieval banding is a verify row.
  assert.ok(verify.length >= 1, "the quorum table has verify rows");
  assert.equal(verify.length, quorumTable.rows.filter((r) => r.retrieval !== "all").length);
  const counted = new Set(countedRows(verify));
  for (const v of verify) {
    assert.ok(v.d, `an equal-rows tree retrieves through ${v.r.retrieval} at ${v.r.target}`);
    checkQuorumRow(v.r, retrievalOf(v.d), counted.has(v));
  }
});

// Guard: the closed form drops pairs no kept band retrieves. Depth 4 and 5 trees keep bands scattered among the rows.
test("pipelineMatchesBruteForce", () => {
  assert.ok(parity.brute.some((b) => b.dims.length >= 4));
  for (const b of parity.brute) {
    for (const [t, ys] of Object.entries(b.pipeline)) parity.s.forEach((s, i) => close(C.pipelineCurve(s, b.dims, +t), ys[i], `brute ${b.dims} at ${t} s ${s}`));
  }
});

test("pipelineBeatsItsCascade", () => {
  for (const { r, d } of countedRows(verifyRows())) {
    const pipe = quorumCounts(r.rows, r.target, retrievalOf(d)).errors, cascade = counts(d, r.target).errors;
    assert.ok(pipe < cascade, `${d} at ${r.target}: pipeline ${pipe} vs cascade ${cascade}`);
  }
});

// Band i is kept when it is child 0 at every AND level above the bands.
function keptRef(d) {
  const out = [];
  for (let i = 0; i < C.rows(d) / d[0]; i++) {
    let rest = i, kept = true;
    for (let j = 1; j < d.length; j++) {
      if (!C.isOr(j) && rest % d[j]) kept = false;
      rest = Math.floor(rest / d[j]);
    }
    if (kept) out.push(i);
  }
  return out;
}

test("pipelineTrialsMatchCurve", () => {
  const shapes = [[3], [2, 3], [3, 4, 2], [2, 3, 2, 2], [2, 2, 3, 2, 2]];
  for (const d of shapes) assert.deepEqual(C.keptBands(d), keptRef(d), `kept bands of ${d}`);
  // One trial decides as the full tree's bits say: a kept band agrees in full and the quorum holds.
  const hashes = C.drawRows(C.mulberry32(13)), outcomes = new Set();
  for (const d of shapes.slice(3)) {
    for (const t of [0.3, 0.5]) {
      for (const s of [0.3, 0.5, 0.8]) {
        for (let seed = 1; seed <= 25; seed++) {
          const { bits } = C.sampleTree(C.drawPair(s, C.mulberry32(seed), PAIR.size, PAIR.vocab), d, hashes);
          const full = (i) => bits.subarray(i * d[0], (i + 1) * d[0]).every(Boolean);
          const want = keptRef(d).some(full) && bits.reduce((a, b) => a + b, 0) >= Math.ceil(+(t * bits.length).toFixed(9)) ? 1 : 0;
          assert.equal(C.runTrials(s, d, 1, C.mulberry32(seed), hashes, PAIR, t), want, `${d} at t ${t} s ${s} seed ${seed}`);
          outcomes.add(want);
        }
      }
    }
  }
  assert.deepEqual([...outcomes].sort(), [0, 1], "both outcomes occur");
  const trials = 2000;
  for (const [d, t] of [[[5, 20], 0.5], [[2, 3, 2, 2], 0.3], [[3, 4, 2, 2, 2], 0.5]]) {
    for (const y of [0.2, 0.5, 0.8]) {
      const s = C.quorumInverse(y, C.rows(d), t, retrievalOf(d)), { U, I } = realised(s), p = C.pipelineCurve(I / U, d, t);
      const hits = C.runTrials(s, d, trials, C.mulberry32(17), hashes, PAIR, t);
      assert.ok(Math.abs(hits / trials - p) < 4 * Math.sqrt(p * (1 - p) / trials), `${d} at t ${t}: rate ${hits / trials} vs ${p} at ${I}/${U}`);
    }
  }
});

// curve() loses digits once a level nears 0 or 1, so the reference carries the hit rate and its complement in linear space.
function hitMiss(s, d) {
  const ln = (x, xc) => (x < 0.5 ? Math.log(x) : Math.log1p(-xc));
  let p = s ** d[0], q = -Math.expm1(d[0] * Math.log(s));
  for (let j = 1; j < d.length; j++) {
    const [lp, lq] = [ln(p, q), ln(q, p)];
    [p, q] = j % 2 === 1 ? [-Math.expm1(d[j] * lq), Math.exp(d[j] * lq)] : [Math.exp(d[j] * lp), -Math.expm1(d[j] * lp)];
  }
  return [p, q];
}

// The slope check only sees differences of logs, so an offset in logPair would pass it. This pins absolute values.
test("logPairMatchesLogCurve", () => {
  const shapes = [[5, 20], [10, 710], [7, 23, 3], [3, 13, 8, 8, 4], [2, 16, 7, 11, 4], [8, 7, 5, 7, 5]];
  let compared = 0;
  for (const d of shapes) {
    for (const s of [0.2, 0.4, 0.5, 0.6, 0.8]) {
      const [p, q] = hitMiss(s, d);
      for (const [what, pair] of [["s", C.logPair(s, d)], ["1 - s", C.logPair(0, d, 1 - s)]]) {
        // Logs of underflowed rates are not comparable, so those sides are skipped.
        if (p > 1e-300) assert.ok(Math.abs(pair.lnp - Math.log(p)) < 1e-8, `ln p ${d} at ${what} ${s}: ${pair.lnp} vs ${Math.log(p)}`);
        if (q > 1e-300) assert.ok(Math.abs(pair.lnq - Math.log(q)) < 1e-8, `ln q ${d} at ${what} ${s}: ${pair.lnq} vs ${Math.log(q)}`);
        compared += (p > 1e-300) + (q > 1e-300);
      }
    }
  }
  assert.ok(compared >= 100, `only ${compared} comparisons`);
});

// profile(d)[j] describes the prefix tree d[0..j], the curve the explorer draws for level j.
test("profileMatchesPrefixCurves", () => {
  const deep = study.tables.lsh_algorithm_table_t50.rows[1].tuple;
  for (const d of [deep, [7, 23, 3], [7, 69], [100, 1], [3, 13, 1, 8, 4]]) {
    const prof = C.profile(d);
    assert.equal(prof.length, d.length, `levels of ${d}`);
    prof.forEach((p, j) => {
      const prefix = d.slice(0, j + 1);
      assert.equal(p.or, C.isOr(j), `op ${d} level ${j}`);
      assert.equal(p.arity, d[j], `arity ${d} level ${j}`);
      close(p.mid, C.inverse(0.5, prefix), `mid ${d} level ${j}`);
      // The forward curve pins the midpoint independently of inverse().
      close(C.curve(p.mid, prefix), 0.5, `curve at mid ${d} level ${j}`);
      close(p.width, C.width(prefix), `width ${d} level ${j}`);
      // An arity of 1 passes its one child through, so the level repeats the one below.
      if (d[j] === 1) {
        close(p.mid, prof[j - 1].mid, `arity 1 mid ${d} level ${j}`);
        close(p.width, prof[j - 1].width, `arity 1 width ${d} level ${j}`);
      }
    });
    assert.equal(prof.at(-1).mid, C.threshold(d), `root mid ${d}`);
    assert.equal(prof.at(-1).width, C.width(d), `root width ${d}`);
  }
});

test("profileStaysNumericAtLargestTuple", () => {
  // The largest tree the explorer accepts: every level at the arity cap and the depth at the grid max.
  const prof = C.profile(Array(MAX_DEPTH).fill(1e5));
  assert.equal(prof.length, MAX_DEPTH);
  for (const [j, p] of prof.entries()) {
    for (const key of ["mid", "width"]) {
      assert.ok(Number.isFinite(p[key]) || Number.isNaN(p[key]), `level ${j} ${key} is ${p[key]}`);
    }
  }
});

// ---- TidyChecks: the tidy rule twin against the study's tidy table. CI runs them apart with --test-name-pattern '^tidy' ----
const tidy = parity.tidy, TOP = study.facts.top_budget;
// Fixture rows within the top budget by (t, B), so each sweep is enumerated once and serves every row of its key.
function tidyKeys() {
  const by = new Map();
  for (const r of tidy.rows.filter((x) => x.b <= TOP)) {
    const k = `${r.t}|${r.b}`;
    by.set(k, [...(by.get(k) || []), r]);
  }
  return by;
}
// Every matched tree at the rule's depths within b rows at t, in the order the depth search finds them.
function matchedTrees(t, b) {
  const out = [], [lo, hi] = tidy.depths;
  for (let k = lo; k <= hi; k++) drainSearch(C.treeSearch(b, k, t, 1, Infinity, (d) => out.push(d)), Infinity);
  return out;
}

test("tidyMixMatchesStudy", () => {
  assert.equal(tidy?.rows.length, 450, "the fixture carries every cell of the tidy table");
  for (const r of tidy.rows) assert.equal(C.nearMass(r.n, r.mix, tidy), r.m, `${r.dataset} m`);
});

test("tidyDataMatchesFixture", () => {
  const { rows, ...consts } = tidy, { rows: pageRows, ...pageConsts } = study.tidy || {};
  assert.equal(consts.rule, "KAlambda");
  assert.deepEqual(pageConsts, consts, "the page embeds the fixture's rule constants");
  assert.deepEqual(C.TIDY_DEPTHS, consts.depths, "the page rule searches the study's depths");
  const top = rows.filter((r) => r.b === TOP).map(({ n, mix, m, t, dims, e }) => ({ n, mix, m, t, dims, e }));
  assert.ok(top.length >= 70, `only ${top.length} rows at ${TOP} rows`);
  assert.deepEqual(pageRows, top, `the page embeds the rows at ${TOP} rows`);
});

test("tidySweepCountsMatchStudyWork", () => {
  const keys = tidyKeys();
  assert.equal(keys.size, 24, "6 targets by 4 budgets");
  for (const rs of keys.values()) {
    const { t, b } = rs[0];
    assert.ok(rs.every((r) => r.work === rs[0].work), `t ${t} B ${b} rows share one sweep`);
    assert.equal(matchedTrees(t, b).length, rs[0].work, `matched trees at t ${t} within ${b} rows`);
  }
});

test("tidyTuneMatchesStudyRows", () => {
  const bad = [];
  let n = 0;
  for (const rs of tidyKeys().values()) {
    for (const r of rs) {
      const got = C.tidyTune(r.n, r.m, r.t, r.b, tidy.gamma);
      if (!same(got.dims, r.dims) || got.tuples !== r.work) bad.push({ dataset: r.dataset, t: r.t, b: r.b, got, want: r.dims });
      n++;
    }
  }
  assert.equal(n, 300);
  assert.deepEqual(bad, []);
});

// The pruned search against scoring every matched tree, on the study rows and on mixes and targets past them.
test("tidyPruneMatchesFullScan", () => {
  const cases = [...tidyKeys().values()].flat().filter((r) => r.b <= 1000);
  for (const t of [0.05, 0.3, 0.95]) {
    for (const [n, mix] of [[1000, 2], [1000, 50], [100000, 2], [100000, 50]]) cases.push({ n, mix, m: C.nearMass(n, mix, tidy), t, b: 1000 });
  }
  const sweeps = new Map();
  for (const r of cases) {
    const k = `${r.t}|${r.b}`;
    if (!sweeps.has(k)) {
      const M = matchedTrees(r.t, r.b);
      sweeps.set(k, { M, parts: M.map((d) => C.errorAreaParts(d, r.t)) });
    }
    const { M, parts } = sweeps.get(k), lam = C.tidyLambda(r.n, r.m, r.t, tidy.gamma);
    assert.ok(M.length, `matched trees at t ${r.t} within ${r.b} rows`);
    // Least λ A_lo + A_hi, ties to the lower A_lo and then the first found.
    let best = 0;
    parts.forEach(([lo, hi], i) => {
      const s = lam * lo + hi, b = lam * parts[best][0] + parts[best][1];
      if (s < b || (s === b && lo < parts[best][0])) best = i;
    });
    assert.deepEqual(C.tidyTune(r.n, r.m, r.t, r.b, tidy.gamma).dims, M[best], `N ${r.n} c ${r.mix} t ${r.t} B ${r.b}`);
    if (r.dims) assert.deepEqual(M[best], r.dims, `${r.dataset} t ${r.t} B ${r.b} full scan`);
  }
  for (const [d, t] of [[[2, 14, 4, 2], 0.3], [[5, 20], 0.5], [[2, 4, 2, 3, 2, 2, 2, 2, 2, 2], 0.8]]) {
    const [lo, hi] = C.errorAreaParts(d, t);
    close(lo + hi, C.errorArea(d, t), `parts of ${d} at ${t} add to the error area`);
  }
});
