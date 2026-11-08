'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const playerSeed = require('./player-seed.cjs');

const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require('../../simulations/753/domains/neighbors.js');
delete globalThis.Sims;

const seeds = [7, 31, 892];
function rng(seed) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}
function trace(spec, preset, seed, controls = {}) {
  const defaults = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  return spec.trace(preset, { ...defaults, ...controls }, rng(seed));
}
const xyz = n => [n.x, n.y, n.z];
const sq = (a, b) => a.reduce((s, x, j) => s + (x - b[j]) ** 2, 0);
const l1 = (a, b) => a.reduce((s, x, j) => s + Math.abs(x - b[j]), 0);
const active = f => f.nodes.filter(n => n.active).map(n => n.id);
const sorted = (items, score) => [...items].sort((a, b) => score(a) - score(b) || a.localeCompare(b));
const abc = 'ABCDEFGH'.split('');
const vectors = nodes => Object.fromEntries(nodes.map(n => [n.id, xyz(n)]));
const numericTuple = t => t.slice(1, -1).split(', ').map(Number);
const tuples = line => Array.from(line.matchAll(/\([^()]+\)/g), m => numericTuple(m[0]));
function answer(frame, order, score) {
  assert.deepEqual(active(frame).sort(), [...order].sort());
  const rows = Array.from(frame.work.matchAll(/\b([A-H]) ([\d.]+)/g));
  assert.deepEqual(rows.map(m => m[1]), order);
  for (const [, id, d] of rows) assert.ok(Math.abs(Number(d) - score(id)) < 0.00051);
}

test('seven standalone specs replay seeded data and keep independent snapshots', () => {
  assert.deepEqual([...specs.keys()].sort(), ['exact-neighbours','greedy-graph','hnsw','inverted-file','k-means-codebook','lsh-radius','product-quantization']);
  for (const spec of specs.values()) {
    assert.equal(new Set(spec.presets.map(p => p.name)).size, 3);
    const saved = structuredClone(spec.presets);
    for (const preset of spec.presets) {
      const input = [];
      for (const seed of seeds) {
        const frames = trace(spec, preset, seed);
        assert.ok(Object.isFrozen(frames));
        assert.deepEqual(frames, trace(spec, preset, seed));
        const objects = new Set();
        const depths = new Set();
        for (const f of frames) {
          assert.ok(Number.isInteger(f.line) && spec.code[f.line] && f.work.trim());
          const ids = new Set(f.nodes.map(n => n.id));
          assert.equal(ids.size, f.nodes.length);
          for (const n of f.nodes) {
            assert.ok(n.label && xyz(n).every(Number.isFinite));
            depths.add(n.z);
          }
          for (const e of f.edges) assert.ok(ids.has(e.from) && ids.has(e.to));
          for (const obj of [f, f.nodes, ...f.nodes, f.edges, ...f.edges]) {
            assert.ok(Object.isFrozen(obj));
            assert.ok(!objects.has(obj));
            objects.add(obj);
          }
        }
        assert.ok(depths.size > 1);
        input.push(frames[0].nodes.map(xyz));
      }
      assert.equal(new Set(input.map(v => JSON.stringify(v))).size, seeds.length);
    }
    assert.deepEqual(spec.presets, saved);
  }
});

test('exact scan ranks by the selected metric and keeps k at every insertion', () => {
  const spec = specs.get('exact-neighbours');
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const metric of ['Manhattan', 'Euclidean']) for (const k of [1, 3, 5]) {
      const frames = trace(spec, preset, seed, { metric, k });
      const v = vectors(frames[0].nodes);
      const score = id => metric === 'Manhattan' ? l1(v[id], v.Q) : Math.sqrt(sq(v[id], v.Q));
      frames.filter(f => f.line === 2).forEach((f, i) => {
        answer(f, sorted(abc.slice(0, i + 1), score).slice(0, k), score);
      });
      answer(frames.at(-1), sorted(abc, score).slice(0, k), score);
    }
  }
});

test('rNNS charges repeated bucket entries to the default two-per-table budget', () => {
  const spec = specs.get('lsh-radius');
  const defaults = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  const params = { ...defaults, bits: 2, tables: 2, radius: 2, factor: 2 };
  for (const budget of [params.budget, 4]) {
    const frames = spec.trace(spec.presets[0], { ...params, budget }, playerSeed(15));
    assert.deepEqual(frames.filter(f => f.line === 2).map(f => f.work.split(': ').at(-1)), ['E, G','F, G, H']);
    assert.deepEqual(frames.filter(f => f.line === 3).map(f => active(f)[0]), ['E','G','F','G']);
    assert.match(frames.at(-1).work, /miss.*4 retrieved entries/i);
  }
});

test('LSH uses all cuts per key and stops at the retrieved-entry budget', () => {
  const spec = specs.get('lsh-radius');
  const outcomes = new Set();
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const bits of [1, 5]) for (const tables of [1, 5]) for (const budget of [1, 8]) {
      for (const [radius, factor] of [[1,1],[4,2],[10,3]]) {
        const frames = trace(spec, preset, seed, { bits, tables, budget, radius, factor });
        const v = vectors(frames[0].nodes);
        const filters = frames.filter(f => f.line === 0).map(f =>
          Array.from(f.work.matchAll(/([xyz]) ≥ (\d+)/g), m => ['xyz'.indexOf(m[1]), Number(m[2])]));
        assert.equal(filters.length, tables);
        const retrieved = [];
        let hit;
        for (const cuts of filters) {
          assert.equal(cuts.length, bits);
          const sameKey = id => cuts.every(([axis, cut]) => (v[id][axis] >= cut) === (v.Q[axis] >= cut));
          for (const id of abc.filter(sameKey)) {
            retrieved.push(id);
            if (l1(v[id], v.Q) <= radius * factor) hit = id;
            if (hit || retrieved.length === budget) break;
          }
          if (hit || retrieved.length === budget) break;
        }
        const checked = frames.filter(f => f.line === 3).map(f => active(f).find(id => id !== 'Q'));
        assert.deepEqual(checked, retrieved);
        assert.deepEqual(active(frames.at(-1)), hit ? [hit] : []);
        outcomes.add(hit ? 'hit' : retrieved.length === budget ? 'budget' : 'exhausted');
      }
    }
  }
  assert.equal(outcomes.size, 3);
});

test('greedy search expands the nearest discovered frontier point and ranks only measured points', () => {
  const spec = specs.get('greedy-graph');
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const entry of ['A','D','H']) for (const expansions of [1,3,8]) {
      const frames = trace(spec, preset, seed, { entry, expansions, k: 5 });
      const v = vectors(frames[0].nodes);
      const score = id => Math.sqrt(sq(v[id], v.Q));
      const seen = new Set([entry]);
      const expanded = new Set();
      for (const f of frames.filter(f => f.line === 1)) {
        const [id] = sorted([...seen].filter(n => !expanded.has(n)), score);
        assert.deepEqual(active(f), [id]);
        expanded.add(id);
        for (const e of f.edges) {
          if (e.from === id) seen.add(e.to);
          if (e.to === id) seen.add(e.from);
        }
      }
      assert.equal(expanded.size, expansions);
      answer(frames.at(-1), sorted(seen, score).slice(0, 5), score);
    }
  }
});

function seededData(preset, seed, dimensions) {
  const random = rng(seed);
  const raw = [...preset.points, preset.query].map(v =>
    v.slice(0, dimensions).map(x => x - 1 + Math.floor(3 * random())));
  return Object.fromEntries([...abc, 'Q'].map((key, i) => [key, raw[i]]));
}
function winner(v, centers) {
  const ds = centers.map(c => sq(c, v));
  return ds.indexOf(Math.min(...ds));
}
function referenceCenters(v, count, rounds = 8) {
  let centers = [v.A];
  while (centers.length < count) {
    const gaps = abc.map(id => sq(v[id], centers[winner(v[id], centers)]));
    centers.push(v[abc[gaps.indexOf(Math.max(...gaps))]]);
  }
  for (let t = 0; t < rounds; t++) {
    const assigned = abc.map(id => winner(v[id], centers));
    centers = centers.map((c, j) => {
      const members = abc.filter((_, i) => assigned[i] === j);
      if (!members.length) return c;
      return c.map((_, axis) => members.reduce((sum, id) => sum + v[id][axis], 0) / members.length);
    });
  }
  return centers;
}
function probed(v, centers, probes) {
  const open = centers.map((_, j) => j).sort((a,b) => sq(v.Q, centers[a]) - sq(v.Q, centers[b])).slice(0, probes);
  return abc.filter(id => open.includes(winner(v[id], centers)));
}

test('coarse centres and final distortion match independent Lloyd iterations at the round limit', () => {
  const spec = specs.get('k-means-codebook');
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const count of [2,3,4]) for (const rounds of [1,2,8]) {
      const v = seededData(preset, seed, 3);
      const centers = referenceCenters(v, count, rounds);
      const frames = trace(spec, preset, seed, { count, rounds });
      const final = frames.at(-1);
      assert.deepEqual(final.nodes.filter(n => /^C\d+$/.test(n.id)).map(xyz), centers);
      const error = abc.reduce((sum, id) => sum + sq(v[id], centers[winner(v[id], centers)]), 0);
      assert.ok(Math.abs(Number(/error ≈ ([\d.]+)\./.exec(final.work)[1]) - error) < 0.00051);
      const moves = frames.filter(f => f.line === 2);
      assert.ok(moves.length >= count && moves.length <= count * rounds);
    }
  }
});

test('IVF measures exactly the members of the requested closest lists', () => {
  const spec = specs.get('inverted-file');
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const probes of [1,2,3]) for (const k of [1,5]) {
      const v = seededData(preset, seed, 3);
      const candidates = probed(v, referenceCenters(v, 3), probes);
      const frames = trace(spec, preset, seed, { probes, k });
      const measured = frames.filter(f => f.line === 3).map(f => /→ ([A-H])/.exec(f.work)[1]);
      assert.deepEqual(measured.sort(), candidates);
      const score = id => Math.sqrt(sq(v[id], v.Q));
      answer(frames.at(-1), sorted(candidates, score).slice(0,k), score);
      if (probes === 3) assert.equal(measured.length, abc.length);
    }
  }
});

test('product codes choose nearest pair centroids and lookup sums match reconstructed four-dimensional distances', () => {
  const spec = specs.get('product-quantization');
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const words of [2,3,4]) for (const probes of [1,3]) for (const k of [1,5]) {
      const v = seededData(preset, seed, 4);
      const books = [0, 2].map(start => {
        const sub = Object.fromEntries(abc.map(id => [id, v[id].slice(start, start + 2)]));
        return referenceCenters(sub, words);
      });
      const frames = trace(spec, preset, seed, { words, probes, k });
      const encoded = frames.filter(f => f.line === 1);
      assert.equal(encoded.length, abc.length);
      const distances = {};
      for (const [i, id] of abc.entries()) {
        const f = encoded[i];
        assert.deepEqual(tuples(f.work).flat(), v[id]);
        const codes = [winner(v[id].slice(0,2), books[0]), winner(v[id].slice(2), books[1])];
        assert.ok(f.work.endsWith('[' + codes.join(', ') + ']'));
        const reconstruction = [...books[0][codes[0]], ...books[1][codes[1]]];
        distances[id] = sq(v.Q, reconstruction);
      }
      const lookup = frames.filter(f => f.line === 2).at(-1).nodes;
      assert.equal(lookup.length, 2 * words);
      lookup.forEach((n, i) => {
        const s = Math.floor(i / words);
        assert.equal(n.shape, 'cell');
        assert.equal(n.value, sq(v.Q.slice(2*s,2*s+2), books[s][i % words]));
      });
      const candidates = probed(v, referenceCenters(v, 3), probes);
      const measured = frames.filter(f => f.line === 4);
      assert.deepEqual(measured.flatMap(active).sort(), candidates);
      for (const f of measured) {
        const score = Number(f.work.split(' ≈ ')[1]);
        assert.ok(Math.abs(score - distances[active(f)[0]]) < 0.00051);
      }
      const score = id => [0,1].reduce((sum, s) => {
        const sub = v[id].slice(s*2, s*2+2);
        return sum + sq(v.Q.slice(s*2, s*2+2), books[s][winner(sub, books[s])]);
      }, 0);
      answer(frames.at(-1), sorted(candidates, score).slice(0,k), score);
    }
  }
});

const adjacent = (frame, id) => frame.edges.flatMap(e =>
  e.from === id ? [e.to] : e.to === id && !e.directed ? [e.from] : []);

test('inserting D prunes both B–C adjacency entries in the tight clouds', () => {
  const spec = specs.get('hnsw');
  const frames = spec.trace(spec.presets[0], { degree: 2, width: 3 }, playerSeed(753));
  const insert = frames.findIndex(f => f.line === 1 && f.work.includes('Insert D'));
  const prune = frames.findIndex((f,i) => i > insert && f.line === 5 && active(f).includes('B'));
  assert.ok(prune > insert);
  assert.ok(adjacent(frames[prune-1], 'B').includes('C'));
  assert.ok(!adjacent(frames[prune], 'B').includes('C'));
  assert.ok(!adjacent(frames[prune], 'C').includes('B'));
  assert.match(frames[prune].work, /B ↔ C/);
});

test('HNSW inserts nested layers, prunes the farthest undirected link and searches by layer', () => {
  const spec = specs.get('hnsw');
  let prunes = 0;
  let promotions = 0;
  for (const preset of spec.presets) for (const seed of seeds) {
    for (const degree of [2,4]) for (const width of [1,3,8]) {
      const frames = trace(spec, preset, seed, { degree, width });
      let entry = 'A';
      const heights = { A: 1 };
      for (const [index, f] of frames.entries()) {
        assert.ok(f.edges.every(e => !e.directed && e.from < e.to));
        if (f.line === 1) {
          const [, id, level] = /Insert ([A-H]) = .*up to layer (\d+)/.exec(f.work);
          heights[id] = Number(level);
        }
        if (f.line === 4) {
          const id = f.work.match(/([A-H]) ↔/)[1];
          const links = adjacent(f, id);
          assert.ok(links.length && links.length <= degree);
        }
        if (f.line === 5) {
          prunes++;
          const [owner] = active(f);
          const prev = adjacent(frames[index - 1], owner);
          const v = vectors(f.nodes);
          assert.equal(prev.length, degree + 1);
          const expected = sorted(prev, id => sq(v[id], v[owner])).slice(0, degree);
          assert.deepEqual(adjacent(f, owner).sort(), expected.sort());
        }
        if (f.line === 6) {
          promotions++;
          [entry] = active(f);
        }
      }
      assert.deepEqual(Object.keys(heights), abc);
      let winner = entry;
      for (let level = Math.max(...Object.values(heights)); level >= 0; level--) {
        const start = frames.findIndex(f => [7,8].includes(f.line) && f.work.startsWith('Layer ' + level + '.'));
        const end = frames.findIndex((f, i) => i > start && f.line === 14);
        const steps = frames.slice(start, end);
        const f = steps[0];
        const v = vectors(f.nodes);
        assert.deepEqual(Object.keys(v).filter(id => id !== 'Q'), abc.filter(id => heights[id] >= level));
        for (const id of Object.keys(v)) assert.ok(adjacent(f, id).length <= degree);
        const score = id => sq(v[id], v.Q);
        const beam = level ? 1 : width;
        const visited = new Set([winner]);
        const pending = new Set([winner]);
        let retained = [winner];
        const expanded = [];
        while (pending.size) {
          const [next] = sorted(pending, score);
          pending.delete(next);
          if (!retained.includes(next)) break;
          expanded.push(next);
          const fresh = adjacent(f, next).filter(id => !visited.has(id));
          fresh.forEach(id => visited.add(id));
          retained = sorted([...retained, ...fresh], score).slice(0, beam);
          fresh.filter(id => retained.includes(id)).forEach(id => pending.add(id));
        }
        assert.deepEqual(steps.filter(s => s.line === 11 && s.work.includes('Expand')).flatMap(active), expanded);
        winner = retained[0];
      }
      assert.deepEqual(active(frames.at(-1)), [winner]);
    }
  }
  assert.ok(prunes > 0 && promotions > 0);
});
