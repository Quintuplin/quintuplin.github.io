"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require("../../simulations/753/domains/ratings.js");
delete globalThis.Sims;

const ids = ["content-profile", "user-collaborative-filtering", "item-collaborative-filtering",
  "bias-residual", "learned-interpolation", "truncated-svd", "latent-factor-sgd", "ranking-evaluation", "rating-rmse"];
const defaults = spec => Object.fromEntries(spec.params.map(p => [p.key, p.value]));
function random(seed) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}
// Match the generator used by the player's Seed control.
function playerRandom(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let bits = Math.imul(seed ^ (seed >>> 15), seed | 1);
    bits ^= bits + Math.imul(bits ^ (bits >>> 7), bits | 61);
    return ((bits ^ (bits >>> 14)) >>> 0) / 4294967296;
  };
}
function run(spec, p, params = {}, rng = () => 0.5) {
  return spec.trace(p, { ...defaults(spec), ...params }, rng);
}
function near(actual, expected, tolerance = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} ≠ ${expected}`);
}
const sum = xs => xs.reduce((a, b) => a + b, 0);
const avg = xs => sum(xs) / xs.length;
const known = xs => xs.filter(v => v !== null);
const inner = (xs, ys) => sum(xs.map((x, i) => x * ys[i]));
const cols = rows => rows[0].map((_, i) => rows.map(row => row[i]));
const cell = (frame, r, c) => frame.nodes.find(n => n.id === `r${r}c${c}`).value;

test("classic script registers all nine spec IDs", () => assert.deepEqual([...specs.keys()], ids));

test("each highlighted line contains an assignment, loop, conditional or return", () => {
  for (const spec of specs.values()) for (const line of spec.code) {
    assert.match(line, /←|^for |^if |^return |\+=/, spec.id + " " + line);
  }
});

for (const spec of specs.values()) {
  test(spec.id + " replays raw data, isolates frames and responds to every control on every preset", () => {
    assert.ok(new Set(spec.presets.map(p => p.name)).size >= 3);
    const saved = structuredClone(spec.presets);
    for (const p of spec.presets) {
      const trace = run(spec, p, {}, random(753));
      assert.deepEqual(run(spec, p, {}, random(753)), trace);
      const reseeded = run(spec, p, {}, random(122));
      assert.notDeepEqual(trace[0].nodes.map(n => n.value), reseeded[0].nodes.map(n => n.value));
      assert.notEqual(trace[0].work, reseeded[0].work);
      const visited = new Set(), identities = new Set();
      for (const f of trace) {
        assert.ok(Number.isInteger(f.line) && spec.code[f.line]);
        assert.ok(f.work && !/NaN|Infinity|undefined/.test(f.work));
        assert.ok(f.nodes.length);
        const ids = new Set(f.nodes.map(n => n.id));
        assert.equal(ids.size, f.nodes.length);
        for (const n of f.nodes) {
          assert.ok(n.label && [n.x, n.y, n.z, n.value].every(Number.isFinite));
          assert.ok(!identities.has(n), "a frame retained another frame’s node object");
          identities.add(n);
        }
        for (const e of f.edges ?? []) assert.ok(ids.has(e.from) && ids.has(e.to));
        visited.add(f.line);
      }
      assert.equal(visited.size, spec.code.length);
      assert.ok(trace.some(f => new Set(f.nodes.map(n => n.z)).size > 1));
      for (const param of spec.params) {
        for (const v of param.options ?? [param.min, param.max]) {
          if (v === param.value) continue;
          const altered = run(spec, p, { [param.key]: v }, random(753));
          assert.notDeepEqual(altered.slice(1), trace.slice(1), param.label);
          assert.deepEqual(altered[0].nodes, trace[0].nodes, "control changed the seeded dataset");
          assert.ok(altered.every(f => !/NaN|Infinity|undefined/.test(f.work)));
        }
      }
    }
    assert.deepEqual(spec.presets, saved);
  });
}

test("TF-IDF uses document frequency, averages only liked vectors and sorts unread cosines", () => {
  const spec = specs.get("content-profile");
  for (const p of spec.presets) for (const liked of [1, 2]) {
    const frames = run(spec, p, { liked }, random(19));
    const counts = p.counts.map((row, i) => row.map((_, j) => cell(frames[0], i, j)));
    const idf = cols(counts).map(c => -Math.log(c.filter(Boolean).length / c.length));
    const weighted = counts.map(row => row.map((v, j) => v * idf[j]));
    const profile = cols(weighted.slice(0, liked)).map(avg);
    const expected = weighted.slice(liked).map((v, j) => ({
      id: p.titles[liked + j], score: inner(v, profile) / (Math.hypot(...v) * Math.hypot(...profile))
    })).sort((a, b) => b.score - a.score);
    const result = frames.at(-1).nodes;
    assert.deepEqual(result.map(n => n.id), expected.map(s => s.id));
    result.forEach((n, i) => near(n.value, expected[i].score));
  }
});

test("user CF keeps the highest signed Pearson neighbour at k=1", () => {
  const spec = specs.get("user-collaborative-filtering");
  const p = spec.presets.find(p => p.name === "Two taste camps");
  const fs = run(spec, p, { metric: "Pearson", k: 1 }, playerRandom(753));
  assert.match(fs.find(f => f.line === 5).work, /Keep Bo \(0\.9608\)/);
  near(cell(fs.at(-1), 0, 3), 4.63);
});

function referenceBaseline(rows) {
  const global = avg(known(rows.flat()));
  return (r, c) => avg(known(rows[r])) + avg(known(cols(rows)[c])) - global;
}

test("cosine keeps full norms; Pearson uses all-rating means and common dimensions on each axis", () => {
  for (const id of ids.slice(1, 4)) {
    const spec = specs.get(id), byItem = id.startsWith("item"), residual = id === "bias-residual";
    for (const p of spec.presets) for (const metric of ["Cosine", "Pearson"]) for (const k of [1, 2, 3]) {
      const frames = run(spec, p, { metric, k });
      const rows = p.rows, v = byItem ? cols(rows) : rows;
      const target = byItem ? 3 : 0, column = byItem ? 0 : 3;
      const baseline = referenceBaseline(rows);
      const neighbours = [];
      for (const [j, other] of v.entries()) {
        if (j === target || other[column] === null) continue;
        const a = v[target], ma = avg(known(a)), mb = avg(known(other));
        let xy = 0, xx = 0, yy = 0;
        for (let c = 0; c < a.length; c++) {
          const pearson = metric === "Pearson";
          if (pearson && (a[c] === null || other[c] === null)) continue;
          const x = (a[c] ?? 0) - (pearson ? ma : 0), y = (other[c] ?? 0) - (pearson ? mb : 0);
          xy += x * y;
          xx += x * x;
          yy += y * y;
        }
        const w = xx && yy ? xy / (Math.sqrt(xx) * Math.sqrt(yy)) : 0;
        neighbours.push({ w, value: other[column] - (residual ? baseline(j, column) : 0) });
      }
      const priority = n => id === "user-collaborative-filtering" ? n.w : Math.abs(n.w);
      const selected = neighbours.sort((a, b) => priority(b) - priority(a)).slice(0, k);
      const correction = sum(selected.map(n => n.w * n.value)) / sum(selected.map(n => Math.abs(n.w)));
      near(cell(frames.at(-1), 0, 3), (residual ? baseline(0, 3) : 0) + correction);
    }
  }
});

test("flat Pearson vectors have zero weight and fall back to the target bias baseline", () => {
  const rows = [[2, 2, 2, null], [1, 1, 1, 4], [2, 2, 2, 3], [4, 4, 4, 2]];
  for (const id of ["user-collaborative-filtering", "bias-residual"]) {
    const frames = run(specs.get(id), { rows }, { metric: "Pearson", k: 3 });
    assert.match(frames.at(-1).work, /No weight mass/);
    near(cell(frames.at(-1), 0, 3), referenceBaseline(rows)(0, 3));
  }
});

test("batch holds weights fixed for a pass and SGD applies each residual gradient immediately", () => {
  const spec = specs.get("learned-interpolation");
  for (const p of spec.presets) for (const method of spec.params[0].options) {
    const rows = p.rows.slice(0, 3), base = referenceBaseline(rows);
    const x = cols(rows).map((col, j) => [col[1] - base(1, j), col[2] - base(2, j)]);
    const params = { rate: 0.1, epochs: 3, method };
    const frames = run(spec, p, params);
    const updates = frames.filter(f => f.line === 4);
    let w = [0, 0], step = 0;
    const batch = method.startsWith("Batch");
    for (let epoch = 0; epoch < 3; epoch++) {
      const groups = batch ? [[0, 1, 2]] : [[0], [1], [2]];
      for (const group of groups) {
        const delta = group.map(j => rows[0][j] - base(0, j) - inner(w, x[j]));
        w = w.map((old, i) => old + 0.1 * avg(group.map((j, n) => delta[n] * x[j][i])));
        w.forEach((v, i) => near(updates[step].nodes[i].value, v));
        step++;
      }
    }
    assert.equal(step, updates.length);
    near(cell(frames.at(-1), 0, 3), base(0, 3) + inner(w, x[3]));
  }
});

test("rank two skips a zero singular component and reconstructs the rank-one table", () => {
  const spec = specs.get("truncated-svd"), p = spec.presets.find(p => p.name === "Parallel tastes");
  const fs = run(spec, p, { rank: 2 }, playerRandom(7462739));
  const components = fs.filter(f => f.line === 3);
  assert.match(components[1].work, /contributes zero/i);
  assert.equal(fs.filter(f => f.line === 4).length, 1);
  fs.at(-1).nodes.forEach((n, i) => near(n.value, fs[0].nodes[i].value));
});

test("truncated SVD has rank one and exactly the discarded energy; rank two restores every cell", () => {
  const spec = specs.get("truncated-svd");
  for (const p of spec.presets) for (const seed of [21, 93]) for (const rank of [1, 2]) {
    const frames = run(spec, p, { rank }, random(seed));
    const matrix = f => p.rows.map((row, i) => row.map((_, j) => cell(f, i, j)));
    const [a,b] = matrix(frames[0]), [u,v] = matrix(frames.at(-1));
    if (rank === 2) {
      u.forEach((x, j) => near(x, a[j]));
      v.forEach((x, j) => near(x, b[j]));
    } else {
      for (let j = 1; j < 3; j++) near(u[0] * v[j], v[0] * u[j]);
      const tr = inner(a, a) + inner(b, b);
      const det = inner(a, a) * inner(b, b) - inner(a, b) ** 2;
      const discarded = (tr - Math.sqrt(tr ** 2 - 4 * det)) / 2;
      near(sum(a.map((x, j) => (x - u[j]) ** 2 + (b[j] - v[j]) ** 2)), discarded);
    }
  }
});

test("latent SGD uses previous factors for both gradients, learns offsets and skips missing ratings", () => {
  const spec = specs.get("latent-factor-sgd");
  for (const p of spec.presets) for (const bias of ["Include biases", "Omit biases"]) {
    const frames = run(spec, p, { bias, epochs: 2, factors: 2, rate: 0.05, penalty: 0.2 });
    const updates = frames.filter(f => f.line === 3);
    const observations = known(p.rows.flat());
    assert.equal(updates.length, 2 * observations.length);
    const enabled = bias === "Include biases", global = enabled ? avg(observations) : 0;
    // With a constant RNG all factors start at 0.3 and the two dimensions stay equal.
    const user = Array(4).fill(0.3), item = Array(4).fill(0.3);
    const ub = Array(4).fill(0), ib = Array(4).fill(0);
    let step = 0;
    for (let pass = 0; pass < 2; pass++) {
      p.rows.forEach((row, u) => row.forEach((r, i) => {
        if (r === null) return;
        const q = user[u], v = item[i];
        const err = r - (global + ub[u] + ib[i] + 2 * q * v);
        user[u] = 0.98 * q + 0.1 * err * v;
        item[i] = 0.98 * v + 0.1 * err * q;
        if (enabled) {
          ub[u] = 0.98 * ub[u] + 0.1 * err;
          ib[i] = 0.98 * ib[i] + 0.1 * err;
        }
        near(cell(updates[step], 0, 0), user[u]);
        near(cell(updates[step], 1, 0), item[i]);
        step++;
      }));
    }
    near(cell(frames.at(-1), 0, 3), global + ub[0] + ib[3] + 2 * user[0] * item[3]);
  }
});

test("each latent dimension follows its own seeded gradient in the first simultaneous update", () => {
  const spec = specs.get("latent-factor-sgd");
  for (const p of spec.presets) {
    const frames = run(spec, p, { factors: 3, bias: "Omit biases", epochs: 1 }, random(99));
    const start = frames.find(f => f.line === 1), after = frames.find(f => f.line === 3);
    const q = start.nodes.slice(0, 3).map(n => n.value), v = start.nodes.slice(3).map(n => n.value);
    assert.equal(new Set([...q, ...v]).size, 6);
    const error = cell(frames[0], 0, 0) - inner(q, v);
    for (let f = 0; f < 3; f++) {
      near(cell(after, 0, f), q[f] + 0.08 * (error * v[f] - 0.1 * q[f]));
      near(cell(after, 1, f), v[f] + 0.08 * (error * q[f] - 0.1 * v[f]));
    }
  }
});

test("ranking cutoff uses input order on ties; grouped ROC area equals pairwise wins plus half ties", () => {
  const spec = specs.get("ranking-evaluation");
  for (const p of spec.presets) for (const seed of [12, 24]) for (const k of [1, 3, 6]) {
    const frames = run(spec, p, { k }, random(seed));
    const entries = frames[0].nodes.map((n, i) => ({ score: n.value, liked: p.liked[i] }));
    const positives = entries.filter(e => e.liked), negatives = entries.filter(e => !e.liked);
    const wins = sum(positives.flatMap(p => negatives.map(n => p.score > n.score ? 1 : Number(p.score === n.score) / 2)));
    const hits = sum(entries.sort((a, b) => b.score - a.score).slice(0, k).map(e => e.liked));
    const metrics = frames.find(f => f.line === 2).work;
    assert.ok(metrics.includes(`Precision@${k} = ${hits}/${k}`));
    assert.ok(metrics.includes(`Recall@${k} = ${hits}/${positives.length}`));
    const roc = frames.at(-1);
    near(Number(roc.work.match(/area = ([\d.]+)/)[1]), wins / positives.length / negatives.length, 0.000051);
    assert.equal(roc.nodes.length, 1 + new Set(entries.map(e => e.score)).size);
    assert.equal(roc.nodes.at(-1).x, 1);
    assert.equal(roc.nodes.at(-1).y, 1);
  }
});

test("RMSE uses all held-out cells and applies the calibration offset before squaring", () => {
  const spec = specs.get("rating-rmse");
  for (const p of spec.presets) for (const offset of [-1, 0, 1]) {
    const frames = run(spec, p, { offset }, random(52));
    const errors = p.actual.map((_, j) => cell(frames[0], 1, j) + offset - cell(frames[0], 0, j));
    const result = Number(frames.at(-1).work.match(/= ([\d.]+) rating points/)[1]);
    near(result, Math.hypot(...errors) / Math.sqrt(errors.length), 0.000051);
  }
});
