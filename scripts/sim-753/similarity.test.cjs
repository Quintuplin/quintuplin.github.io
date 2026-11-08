const { test } = require('node:test');
const assert = require('node:assert/strict');
const playerSeed = require('./player-seed.cjs');

const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require('../../simulations/753/domains/similarity.js');
delete globalThis.Sims;

function run(spec, preset = spec.presets[0], overrides = {}, seed = 54819) {
  const params = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  const rng = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  return spec.trace(preset, { ...params, ...overrides }, rng);
}

const numbers = text => text.match(/-?\d+/g).map(Number);

test('every highlighted code line contains an algorithm operation', () => {
  for (const spec of specs.values()) {
    const visited = new Set(run(spec).map(f => f.line));
    spec.code.forEach((line, index) => {
      assert.ok(visited.has(index), spec.id + ' unreachable line ' + index);
      assert.match(line, /←|\breturn\b|\bif\b|\bfor\b/, spec.id + ' line ' + index);
    });
  }
});

test('all eight simulations register and replay independent snapshots for every preset', () => {
  assert.equal(specs.size, 8);
  for (const spec of specs.values()) {
    assert.ok(new Set(spec.presets.map(p => p.name)).size >= 3);
    for (const preset of spec.presets) {
      const frames = run(spec, preset);
      assert.deepEqual(frames, run(spec, preset));
      assert.notEqual(frames[0].work, run(spec, preset, {}, 710123)[0].work, spec.id);
      assert.ok(new Set(frames.flatMap(f => f.nodes.map(n => n.z))).size > 1);
      const references = new Set();
      for (const { line, work, nodes, edges = [] } of frames) {
        assert.ok(spec.code[line] && work.length && nodes.length);
        const ids = new Set(nodes.map(n => n.id));
        assert.equal(ids.size, nodes.length);
        for (const n of nodes) {
          assert.ok(!references.has(n));
          references.add(n);
          assert.ok([n.x, n.y, n.z].every(Number.isFinite));
          assert.ok(typeof n.label === 'string' && n.label.length);
        }
        for (const { from, to } of edges) assert.ok(ids.has(from) && ids.has(to));
      }
      for (const param of spec.params) {
        const values = param.options || [param.min, param.max];
        for (const value of values.filter(v => v !== param.value)) {
          assert.notDeepEqual(run(spec, preset, { [param.key]: value }), frames, param.key);
        }
      }
    }
  }
});

test('matrix entries and bucket heads render as cells', () => {
  for (const id of ['minhash-permutation', 'minhash-one-pass', 'lsh-banding', 'chained-dictionary']) {
    for (const n of run(specs.get(id))[0].nodes) assert.equal(n.shape, 'cell', id);
  }
});

test('scalar and packed composite keys use a nonzero multiplier in a field covering the input universe', () => {
  const spec = specs.get('universal-hashing');
  for (const kind of spec.params[0].options) {
    const [init, ...steps] = run(spec, spec.presets[2], { slots: 5, kind });
    const keys = [...init.work.matchAll(/\(([\d,]+)\)/g)].map(m => numbers(m[1]));
    const coeff = numbers(init.work.split('Coefficients ')[1]);
    keys.forEach((key, i) => {
      const [a, b, prime] = coeff;
      const x = kind === 'Single number' ? key[0] : key[0] * 17 + key[1];
      assert.ok(prime >= (kind === 'Single number' ? 17 : 289));
      assert.ok(a > 0 && a < prime && b >= 0 && b < prime);
      const sum = a * x + b;
      const expected = [sum, sum % prime, sum % prime % 5];
      assert.deepEqual(steps.slice(3 * i, 3 * i + 3).map(f => +f.nodes.at(-1).label), expected);
    });
  }
});

test('every affine coefficient pair on (1,2) and (1,4) respects the table collision bound', () => {
  const spec = specs.get('universal-hashing');
  const preset = { pairs: [[1,2],[1,4]] };
  const p = 293;
  const collisions = Array(8).fill(0);
  for (let a = 1; a < p; a++) for (let b = 0; b < p; b++) {
    const tape = [0, 0, (a - 0.5) / (p - 1), (b + 0.5) / p];
    let i = 0;
    const frames = spec.trace(preset, {kind: 'Two fields', slots: 4}, () => tape[i++]);
    const residues = frames.filter(f => f.line === 2).map(f => Number(f.nodes.at(-1).label));
    assert.deepEqual(residues, [(19*a + b) % p, (21*a + b) % p]);
    for (let m = 2; m <= 7; m++) collisions[m] += Number(residues[0] % m === residues[1] % m);
  }
  for (let m = 2; m <= 7; m++) assert.ok(collisions[m] * m <= p * (p - 1));
});

test('dictionary probes the collision chain and unlinks only a present key', () => {
  const spec = specs.get('chained-dictionary');
  for (const query of spec.params[1].options) {
    const frames = run(spec, spec.presets[0], { query });
    const key = numbers(frames[0].work)[1];
    const found = query === 'Stored key';
    assert.deepEqual(frames.filter(f => f.line === 3).map(f => numbers(f.work)[0]), [key + 8, key + 4, key]);
    assert.equal(frames.at(-1).nodes.some(n => n.id === 'k' + key), !found);
    assert.equal(frames.at(-1).edges.length, found ? 3 : 4);
  }
});

test('repeated character windows count once in intersection and union', () => {
  const spec = specs.get('shingling-jaccard');
  for (const preset of spec.presets) for (const width of [1, 2, 3, 4]) {
    const frames = run(spec, preset, { width });
    const docs = [...frames[0].work.matchAll(/= ([A-Z]+)/g)].map(m => m[1]);
    const sets = docs.map(doc => new Set([...doc].map((_, i) => doc.slice(i, i + width)).filter(s => s.length === width)));
    const intersection = [...sets[0]].filter(s => sets[1].has(s)).length;
    const union = new Set([...sets[0], ...sets[1]]).size;
    assert.deepEqual(numbers(frames.at(-1).work).slice(0, 2), [intersection, union]);
  }
});

for (const id of ['minhash-permutation', 'minhash-one-pass']) {
  test(id + ' stores the minimum rank in each document column', () => {
    const spec = specs.get(id);
    for (const preset of spec.presets) {
      const frames = run(spec, preset, { count: 6 });
      const sets = [...frames[0].work.matchAll(/\{([\d,]+)\}/g)].map(m => numbers(m[1]));
      const rankers = id === 'minhash-permutation'
        ? frames.filter(f => f.line === 1).map(f => {
          const order = numbers(f.work.match(/\[(.*?)\]/)[1]);
          assert.equal(new Set(order).size, 7);
          return x => order.indexOf(x);
        })
        : [...frames[0].work.matchAll(/\((\d+),(\d+)\)/g)].map(([, a, b]) => x => (a * x + Number(b)) % 7);
      const pairs = rankers.map(rank => sets.map(set => Math.min(...set.map(rank))));
      assert.deepEqual(frames.at(-1).nodes.map(n => n.value), pairs.flat());
      assert.deepEqual(numbers(frames.at(-1).work).slice(0, 2), [pairs.filter(([a, b]) => a === b).length, 6]);
    }
  });
}

test('a candidate requires every signature row in at least one band', () => {
  const spec = specs.get('lsh-banding');
  for (const preset of spec.presets) for (const rows of spec.params[0].options) {
    const frames = run(spec, preset, { rows });
    const [a, b] = [...frames[0].work.matchAll(/\[([\d,]+)\]/g)].map(m => m[1].split(','));
    let hits = 0;
    for (let i = 0; i < 8; i += Number(rows)) {
      if (a.slice(i, i + Number(rows)).every((v, j) => v === b[i + j])) hits++;
    }
    assert.equal(numbers(frames.at(-1).work)[0], hits);
    assert.equal(frames.at(-1).work.includes('(A,B)'), hits > 0);
  }
});

test('independent AND and OR stages transform near and far bounds', () => {
  const spec = specs.get('lsh-amplification');
  for (const k of [1, 3, 6]) for (const tables of [1, 5, 8]) {
    const frames = run(spec, spec.presets[1], { k, tables });
    const [near, far] = frames[0].nodes.map(n => n.y);
    assert.ok(near > far);
    for (const [i, p] of [near, far].entries()) {
      assert.equal(frames[1].nodes[i + 2].y, p ** k);
      assert.equal(frames.at(-1).nodes[i + 4].y, 1 - (1 - p ** k) ** tables);
    }
  }
});

test('opposing vectors at player seed 11 have four complementary SimHash bits', () => {
  const spec = specs.get('simhash');
  const frames = spec.trace(spec.presets[1], {bits: 4}, playerSeed(11));
  assert.match(frames.at(-1).work, /= 4\. Agreement = 0\/4/);
});

test('Box–Muller redraws a tied plane and keeps the accepted Gaussian coordinates finite', () => {
  const spec = specs.get('simhash');
  const tape = [0,0,0, 0,0,0.75,0.5, 0.5,0.125,0.75,0.5];
  const frames = spec.trace({vectors: [[1,0,0],[-1,0,0]]}, {bits: 1}, () => { assert.ok(tape.length); return tape.shift(); });
  const n = frames.find(f => f.line === 1).nodes.at(-1);
  const diagonal = Math.sqrt(Math.log(2));
  for (const [v, expected] of [[n.x, diagonal], [n.y, diagonal], [n.z, -Math.sqrt(2 * Math.log(4))]]) {
    assert.ok(Math.abs(v - expected) < 1e-12);
  }
  assert.equal(tape.length, 0);
});

test('SimHash projects actual vectors without ties and counts bit differences', () => {
  const spec = specs.get('simhash');
  for (let seed = 10; seed < 40; seed++) {
    const frames = run(spec, spec.presets[2], { bits: 8 }, seed);
    const signatures = ['', ''];
    for (const f of frames.filter(f => f.line === 2)) {
      const v = f.nodes.find(n => n.active), n = f.nodes.at(-1);
      const dot = v.x * n.x + v.y * n.y + v.z * n.z;
      assert.notEqual(dot, 0);
      const bit = Number(dot >= 0);
      signatures[v.id === 'A' ? 0 : 1] += bit;
      assert.ok(f.work.includes('≈ ' + Number(dot.toPrecision(4)) + '. Bit = ' + bit));
    }
    const distance = [...signatures[0]].filter((v, i) => signatures[1][i] !== v).length;
    assert.ok(frames.at(-1).work.includes('(' + signatures.join(', ') + ') = ' + distance));
  }
});
