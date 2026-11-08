"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require("../../simulations/753/domains/graphs.js");
delete globalThis.Sims;

function random(seed) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
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
function run(spec, preset, seed = 11, controls = {}) {
  const defaults = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  return spec.trace(preset, { ...defaults, ...controls }, random(seed));
}
const all = (n, fn) => Array.from({ length: n }, (_, i) => fn(i));
const sum = xs => xs.reduce((a, b) => a + b, 0);
const values = frame => frame.nodes.map(n => n.value);
const groups = frame => frame.nodes.map(n => n.group);
const close = (a, b, eps = 1e-8) => assert.ok(Math.abs(a - b) <= eps, `${a} differs from ${b}`);
const index = id => id.charCodeAt(0) - 65;
function matrix(frame) {
  const rows = frame.nodes.map(() => frame.nodes.map(() => 0));
  for (const { from, to, directed } of frame.edges) {
    rows[index(from)][index(to)]++;
    if (!directed) rows[index(to)][index(from)]++;
  }
  return rows;
}
function each(id, check) {
  const spec = specs.get(id);
  for (const p of spec.presets) {
    for (const seed of [11, 223]) check(controls => run(spec, p, seed, controls), p);
  }
}

test("classic registration, real input variation, replay, independent snapshots and controls", () => {
  assert.equal(specs.size, 11);
  for (const spec of specs.values()) {
    assert.equal(new Set(spec.presets.map(p => p.name)).size, 3);
    const motifs = new Set();
    for (const p of spec.presets) {
      const saved = structuredClone(p);
      const frames = run(spec, p);
      motifs.add(JSON.stringify(frames[0].edges));
      assert.deepEqual(frames, run(spec, p));
      assert.notDeepEqual(frames[0].edges, run(spec, p, 223)[0].edges, spec.id);
      assert.ok(frames.length > 2);
      const nodeRefs = new Set(), edgeRefs = new Set();
      const executed = new Set();
      for (const f of frames) {
        assert.ok(Number.isInteger(f.line) && spec.code[f.line], spec.id);
        executed.add(f.line);
        assert.ok(typeof f.work === "string" && f.work.length);
        const ids = new Set(f.nodes.map(n => n.id));
        for (const n of f.nodes) {
          assert.ok(n.label && n.label.length <= 6);
          assert.ok([n.x, n.y, n.z].every(Number.isFinite));
          if ("value" in n) assert.ok(Number.isFinite(n.value));
          assert.ok(!nodeRefs.has(n));
          nodeRefs.add(n);
        }
        for (const e of f.edges) {
          assert.ok(ids.has(e.from) && ids.has(e.to));
          assert.ok(!edgeRefs.has(e));
          edgeRefs.add(e);
        }
      }
      assert.equal(executed.size, spec.code.length, spec.id + " pseudocode coverage");
      assert.ok(frames.some(f => new Set(f.nodes.map(n => n.z)).size > 1));
      for (const param of spec.params) {
        const options = param.options ?? [param.min, param.max];
        for (const value of options.filter(v => v !== param.value)) {
          assert.notDeepEqual(run(spec, p, 11, { [param.key]: value }), frames, spec.id + " " + param.key);
        }
      }
      assert.deepEqual(p, saved);
    }
    assert.equal(motifs.size, 3);
  }
});

// Independent dense stochastic matrix, including replacement columns for dead ends.
function walk(W, start, dest, beta, steps) {
  const P = W.map(row => row.map((w, j) => {
    const out = sum(row);
    return beta * (out ? w / out : dest[j]) + (1 - beta) * dest[j];
  }));
  let r = start;
  for (let t = 0; t < steps; t++) r = r.map((_, j) => sum(P.map((row, i) => row[j] * r[i])));
  return r;
}
test("PageRank at β=1 explains the restart from dangling pages", () => {
  const spec = specs.get("pagerank"), p = spec.presets.find(p => p.name.includes("dead end"));
  const fs = run(spec, p, 753, { follow: 1, rounds: 1 });
  assert.match(spec.description, /dead ends? still restart/i);
  const W = matrix(fs[0]);
  const dangling = W.filter(row => !sum(row)).length / W.length;
  assert.ok(dangling > 0);
  const receipts = values(fs.find(f => f.line === 3));
  values(fs.at(-1)).forEach((v, i) => close(v - receipts[i], dangling / W.length));
});

test("sparse iterations match dense walks including dangling redistribution, closed traps and restart sets", () => {
  for (const id of ["pagerank", "personalised-pagerank"]) each(id, (trace, preset) => {
    for (const follow of [0, 0.85, 1]) {
      const fs = trace({ rounds: 4, follow, restart: "A and B" });
      const W = matrix(fs[0]), n = W.length, uniform = all(n, () => 1 / n);
      const p = id === "pagerank" ? uniform : all(n, i => i <= 1 ? 0.5 : 0);
      let r = uniform;
      const iterations = fs.filter(f => f.line === 4);
      assert.equal(iterations.length, 4);
      for (const f of iterations) {
        r = walk(W, r, p, follow, 1);
        values(f).forEach((v, i) => close(v, r[i]));
        close(sum(r), 1);
      }
      if (preset.name.includes("dead end")) assert.ok(W.some(row => !sum(row)));
      if (preset.name.includes("trap")) {
        assert.equal(W[2][3], 1);
        assert.equal(W[3][2], 1);
        assert.equal(sum(W[2]) + sum(W[3]), 2);
      }
    }
  });
});

test("link-farm target balance and spam mass agree with independent stationary ranks", () => {
  for (const id of ["trustrank", "link-farm"]) each(id, (trace, preset) => {
    for (const supporters of [1, 5]) {
      const beta = 0.9, fs = trace({ supporters, follow: beta, restart: "B" });
      const W = matrix(fs[0]), n = W.length, target = preset.n;
      assert.equal(n, target + supporters + 1);
      const uniform = all(n, () => 1 / n);
      const r = walk(W, uniform, uniform, beta, 400);
      const t = walk(W, uniform, all(n, i => Number(i === 1)), beta, 400);
      const external = sum(W.slice(0, target).map((row, i) => beta * r[i] * row[target] / sum(row)));
      close(r[target], (external + (1 - beta) * (1 + beta * supporters) / n) / (1 - beta ** 2));
      values(fs.at(-1)).forEach((v, i) => close(v, id === "trustrank" ? (r[i] - t[i]) / r[i] : r[i]));
    }
  });
});

// Enumerate simple paths and split each pair's unit among only its shortest paths.
function pathScores(frame, roots) {
  const W = matrix(frame);
  const scores = Object.fromEntries(frame.edges.map(e => [[e.from,e.to].sort().join("–"), 0]));
  for (const a of roots) {
    for (let b = 0; b < W.length; b++) {
      if (a === b || (roots.length === W.length && a > b)) continue;
      const paths = [];
      function visit(path) {
        const end = path.at(-1);
        if (end === b) paths.push(path);
        else W[end].forEach((w, i) => { if (w && !path.includes(i)) visit([...path, i]); });
      }
      visit([a]);
      const min = Math.min(...paths.map(p => p.length));
      const shortest = paths.filter(p => p.length === min);
      for (const p of shortest) {
        for (let i = 1; i < p.length; i++) {
          const k = [frame.nodes[p[i - 1]].id, frame.nodes[p[i]].id].sort().join("–");
          scores[k] += 1 / shortest.length;
        }
      }
    }
  }
  return scores;
}
const readScores = s => [...s.matchAll(/([A-Z])–([A-Z]) ([\d.]*\d)/g)].map(([, a, b, v]) => [[a, b].sort().join("–"), Number(v)]);
test("Brandes highlights the outgoing edges that receive shortest-path counts", () => {
  const spec = specs.get("brandes"), p = spec.presets.find(p => p.name === "Workshop rings");
  const visits = spec.trace(p, { roots: "A only" }, playerRandom(753)).filter(f => f.line === 2);
  const lit = f => f.edges.filter(e => e.active).map(e => [e.from, e.to].sort().join(""));
  assert.deepEqual(lit(visits[0]), ["AB", "AD"]);
  assert.deepEqual(lit(visits[1]), ["BC"]);
  for (const f of visits) {
    const v = f.nodes.find(n => n.active);
    const depth = new Map(f.nodes.map(n => [n.id, n.z]));
    for (const e of f.edges) {
      const w = e.from === v.id ? e.to : e.to === v.id ? e.from : undefined;
      assert.equal(e.active, depth.get(w) === v.z + 1);
    }
  }
});

test("Brandes fractional reverse credits and all-root halving match shortest-path enumeration", () => {
  each("brandes", trace => {
    for (const roots of ["A only", "All vertices"]) {
      const fs = trace({ roots });
      const expected = pathScores(fs[0], roots === "A only" ? [0] : all(fs[0].nodes.length, i => i));
      const actual = readScores(fs.at(-1).work);
      assert.equal(actual.length, fs[0].edges.length);
      for (const [edge, value] of actual) close(value, expected[edge], 5.1e-6);
    }
  });
});
test("Girvan–Newman recomputes every surviving score and removes one current maximum", () => {
  each("girvan-newman", trace => {
    const fs = trace({ count: 5 });
    for (let i = 1; i < fs.length; i += 2) {
      const f = fs[i], after = fs[i+1];
      const scores = pathScores(f, all(f.nodes.length, j => j));
      const actual = readScores(f.work);
      assert.equal(actual.length, f.edges.length);
      actual.forEach(([edge, v]) => close(v, scores[edge], 5.1e-6));
      const [best] = f.edges.filter(e => e.active);
      close(scores[[best.from, best.to].sort().join("–")], Math.max(...Object.values(scores)));
      assert.equal(after.edges.length, f.edges.length - 1);
      assert.ok(!after.edges.some(e => e.from === best.from && e.to === best.to));
    }
    assert.equal(new Set(groups(fs.at(-1))).size, 5);
  });
});

function modularity(W, P) {
  const deg = W.map(sum), ends = sum(deg);
  return sum(W.map((row, i) => sum(row.map((w, j) => P[i] === P[j] ? w - deg[i] * deg[j] / ends : 0)))) / ends;
}
test("greedy Newman chooses the largest modularity gain at each level and returns the peak", () => {
  each("greedy-newman", trace => {
    const fs = trace({ stop: "Show full hierarchy" });
    const W = matrix(fs[0]);
    let P = groups(fs[1]), peak = modularity(W, P);
    for (const f of fs.filter(f => f.line === 3)) {
      const candidates = fs[0].edges.map(e => [P[index(e.from)], P[index(e.to)]]).filter(([a, b]) => a !== b);
      const expected = Math.max(...candidates.map(([a, b]) => modularity(W, P.map(v => v === a ? b : v))));
      P = groups(f);
      close(modularity(W, P), expected);
      peak = Math.max(peak, expected);
    }
    assert.equal(new Set(P).size, 1);
    close(modularity(W, groups(fs.at(-1))), peak);
    close(modularity(W, groups(trace({}).at(-1))), peak);
  });
});

test("minimum, ratio and normalized cuts attain their exhaustive objective minimum", () => {
  each("graph-cuts", trace => {
    for (const objective of ["Minimum cut", "Ratio cut", "Normalized cut"]) {
      const fs = trace({ objective }), W = matrix(fs[0]);
      function cost(P) {
        const cut = sum(W.map((row, i) => sum(row.filter((_, j) => P[i] && !P[j]))));
        if (objective === "Minimum cut") return cut;
        const sizes = [0, 0];
        P.forEach((c, i) => { sizes[c] += objective === "Ratio cut" ? 1 : sum(W[i]); });
        return cut * (1 / sizes[0] + 1 / sizes[1]);
      }
      const scores = all(2 ** W.length - 2, i => cost(all(W.length, j => ((i + 1) >> j) & 1)));
      close(cost(groups(fs.at(-1))), Math.min(...scores));
    }
  });
});

test("local clustering counts actual neighbour pairs and handles the leaf", () => {
  each("clustering-coefficient", trace => {
    for (const focus of "ABCDEFGH") {
      const fs = trace({ focus }), W = matrix(fs[0]), v = index(focus);
      const degree = sum(W[v]);
      const trianglesTwice = sum(W.map((row, i) => sum(row.map((e, j) => W[v][i] * e * W[v][j]))));
      close(values(fs.at(-1))[v], degree < 2 ? 0 : trianglesTwice / (degree * (degree - 1)));
    }
  });
});

function lapTimes(W, v) {
  return W.map((row, i) => sum(row.map((w, j) => w * (v[i] - v[j]))));
}
const dot = (a, b) => sum(a.map((x, i) => x * b[i]));
test("Fiedler sign split explains where a tiny positive coordinate goes", () => {
  const spec = specs.get("fiedler-partition");
  const p = spec.presets.find(p => p.name === "Neighbourhood footpaths");
  const final = spec.trace(p, { split: "Sign of the Fiedler vector" }, playerRandom(1)).at(-1);
  const nearZero = final.nodes.filter(n => n.value > 0 && n.value <= 1e-10);
  assert.ok(nearZero.length);
  nearZero.forEach(n => assert.equal(n.group, 0));
  assert.match(spec.code[final.line], /v\[i\] > 1e-10/);
  assert.match(final.work, /1e-10/);
});

test("Fiedler eigenvector has unit norm, zero sum, second eigenvalue and the requested split", () => {
  each("fiedler-partition", trace => {
    const fs = trace({}), W = matrix(fs[0]), final = fs.at(-1);
    const v = values(final), Lv = lapTimes(W, v), lambda = dot(v, Lv);
    close(dot(v, v), 1);
    close(sum(v), 0);
    const spectrum = fs.find(f => f.work.startsWith("Eigenvalues")).work.match(/\[([^\]]+)\]/)[1].split(",").map(Number);
    assert.deepEqual(spectrum, [...spectrum].sort((a, b) => a - b));
    close(sum(spectrum), sum(W.map(sum)), 1e-4);
    close(lambda, spectrum[1], 5.1e-6);
    Lv.forEach((x, i) => close(x, lambda * v[i]));
    assert.deepEqual(groups(final), v.map(x => Number(x > 1e-10)));
    const halves = groups(trace({ split: "Equal halves by sorted value" }).at(-1));
    assert.equal(sum(halves), v.length / 2);
    assert.ok(Math.min(...v.filter((_, i) => halves[i])) >= Math.max(...v.filter((_, i) => !halves[i])));
  });
});
test("k-means clusters the first k Laplacian coordinates and reaches a nearest-centroid assignment", () => {
  each("spectral-k-means", trace => {
    for (const k of [2, 3, 4]) {
      const fs = trace({ k }), W = matrix(fs[0]);
      const rows = fs.filter(f => f.work.startsWith("Embedding row")).map(f => f.work.match(/\[([^\]]+)\]/)[1].split(",").map(Number));
      assert.equal(rows.length, W.length);
      assert.ok(rows.every(r => r.length === k));
      const lambdas = fs.find(f => f.work.startsWith("Eigenvalues")).work.match(/\[([^\]]+)\]/)[1].split(",").map(Number);
      for (let j = 0; j < k; j++) {
        const v = rows.map(r => r[j]);
        close(dot(v,v), 1, 4e-5);
        lapTimes(W, v).forEach((x, i) => close(x, lambdas[j] * v[i], 1e-4));
        for (let i = 0; i < j; i++) close(dot(v, rows.map(r => r[i])), 0, 4e-5);
      }
      const P = groups(fs.at(-1));
      assert.equal(new Set(P).size, k);
      const centres = all(k, c => {
        const cluster = rows.filter((_, i) => P[i] === c);
        return all(k, j => sum(cluster.map(r => r[j])) / cluster.length);
      });
      rows.forEach((r, i) => {
        const ds = centres.map(c => sum(c.map((x, j) => (x-r[j])**2)));
        close(ds[P[i]], Math.min(...ds), 3e-5);
      });
    }
  });
});

test("k-means reaches stable groups for every supported community graph and k", () => {
  const spec = specs.get("spectral-k-means");
  for (const preset of spec.presets) {
    const optional = preset.extra.split(" ").length;
    for (let mask = 0; mask < 2 ** optional; mask++) {
      for (let leaf = 0; leaf < preset.n; leaf++) {
        for (let k = 2; k <= 4; k++) {
          const draws = all(optional, j => (mask >> j) & 1 ? 0.25 : 0.75);
          draws.push((leaf + 0.5) / preset.n);
          const frames = spec.trace(preset, { k }, () => draws.shift());
          const rounds = frames.filter(f => f.line === 4);
          assert.ok(rounds.length >= 2);
          assert.deepEqual(groups(rounds.at(-1)), groups(rounds.at(-2)));
          assert.equal(new Set(groups(rounds.at(-1))).size, k);
        }
      }
    }
  }
});
