const test = require("node:test");
const assert = require("node:assert/strict");
const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require("../../simulations/753/domains/streams.js");
delete globalThis.Sims;

function seeded(seed) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}

function run(spec, preset, seed, changes = {}) {
  const params = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  return spec.trace(preset, { ...params, ...changes }, seeded(seed));
}
const input = frames => JSON.parse(frames[0].work.match(/\[.*\]/)[0]);
const memory = frame => frame.nodes.filter(n => n.id !== "key");
const focus = frame => frame.nodes.find(n => n.id === "key").value;
const active = frame => memory(frame).find(n => n.active);
const values = frame => memory(frame).map(n => n.value);
const sum = a => a.reduce((s, n) => s + n, 0);
const atLine = (frames, line) => frames.filter(f => f.line === line);
const frequency = (stream, key) => stream.filter(x => x === key).length;
const ids = ["fixed-proportion-sampling", "reservoir-sampling", "standard-bloom-filter",
  "partitioned-bloom-filter", "repeated-bloom-filter", "misra-gries", "count-min-sketch", "count-sketch"];

test("catalog, bounded inputs, replay, independent snapshots and working controls", () => {
  assert.deepEqual([...specs.keys()].sort(), [...ids].sort());
  for (const spec of specs.values()) {
    assert.ok(new Set(spec.presets.map(p => p.name)).size >= 3);
    for (const preset of spec.presets) {
      const frames = run(spec, preset, 91);
      assert.deepEqual(frames, run(spec, preset, 91));
      assert.notDeepEqual(input(frames), input(run(spec, preset, 101)));
      const instances = new Set();
      for (const frame of frames) {
        assert.ok(spec.code[frame.line] && frame.work.trim());
        assert.ok(Object.isFrozen(frame) && Object.isFrozen(frame.nodes));
        assert.equal(new Set(frame.nodes.map(n => n.id)).size, frame.nodes.length);
        for (const node of frame.nodes) {
          assert.ok(node.label && [node.x, node.y, node.z].every(Number.isFinite));
          assert.ok(!instances.has(node));
          assert.ok(Object.isFrozen(node));
          instances.add(node);
        }
      }
      assert.ok(frames.some(f => new Set(f.nodes.map(n => n.z)).size > 1));
      for (const p of spec.params) {
        const alternatives = p.options || [p.min, p.max];
        for (const alt of alternatives.filter(x => x !== p.value)) {
          const changed = run(spec, preset, 91, { [p.key]: alt });
          assert.deepEqual(input(changed), input(frames));
          assert.notDeepEqual(changed, frames);
        }
      }
    }
  }
});

function eachExample(id, check) {
  const spec = specs.get(id);
  for (const preset of spec.presets) {
    for (const seed of [17, 113, 304]) {
      check((params = {}) => run(spec, preset, seed, params));
    }
  }
}

test("fixed-proportion sampling routes every repeat to its original bucket", () => {
  eachExample(ids[0], trace => {
    for (const keep of [1, 3, 5]) {
      const frames = trace({ keep });
      const stream = input(frames);
      const counts = Array(6).fill(0);
      const byKey = new Map();
      atLine(frames, 2).forEach((f, i) => {
        const b = Number(active(f).id.split("-")[1]);
        if (byKey.has(stream[i])) assert.equal(b, byKey.get(stream[i]));
        byKey.set(stream[i], b);
        counts[b]++;
        assert.deepEqual(values(f), counts);
        assert.equal(focus(f), stream[i]);
      });
      assert.match(frames.at(-1).work, new RegExp(sum(counts.slice(0, keep)) + "/" + stream.length + "\\.$"));
    }
  });
});

test("reservoir snapshots match every independent integer draw and preserve occurrence identities", () => {
  eachExample(ids[1], trace => {
    for (const slots of [1, 3, 4]) {
      for (const mode of ["One reservoir", "Three independent reservoirs"]) {
        const frames = trace({ slots, mode });
        const stream = input(frames);
        const copies = mode === "One reservoir" ? 1 : 3;
        const expected = Array(slots * copies).fill(0);
        let frame = 1;
        stream.forEach((key, i) => {
          for (let r = 0; r < copies; r++) {
            let j = i + 1;
            if (j > slots) {
              const draw = frames[frame++];
              assert.equal(draw.line, 2);
              assert.deepEqual(values(draw), expected);
              j = Number(draw.work.match(/= (\d+)\./)[1]);
              assert.ok(j >= 1 && j <= i + 1);
            }
            const decision = frames[frame++];
            if (j <= slots) expected[r * slots + j - 1] = i + 1;
            assert.equal(decision.line, i < slots ? 1 : j <= slots ? 3 : 4);
            assert.deepEqual(values(decision), expected);
            assert.equal(focus(decision), key);
          }
        });
        assert.equal(frame, frames.length - 1);
      }
    }
  });
});

test("RS1 and RSs give every subset equal probability and parallel RS1 copies use independent draws", () => {
  const spec = specs.get(ids[1]);
  function outcomes(slots, parallel, pattern, draws) {
    const occurrences = new Map();
    function enumerate(prefix) {
      if (prefix.length < draws.length) {
        const denominator = draws[prefix.length];
        for (let i = 0; i < denominator; i++) enumerate([...prefix, (i + 0.5) / denominator]);
        return;
      }
      const tape = [...Array(Math.max(...pattern) + 2).fill(0), ...prefix];
      const frames = spec.trace({ pattern }, { slots, mode: parallel ? "Three independent reservoirs" : "One reservoir" },
        () => { assert.ok(tape.length); return tape.shift(); });
      assert.equal(tape.length, 0);
      const result = values(frames.at(-1));
      if (!parallel) result.sort();
      const key = result.join(",");
      occurrences.set(key, (occurrences.get(key) || 0) + 1);
    }
    enumerate([]);
    return occurrences;
  }
  for (const [counts, size] of [
    [outcomes(1, false, [0, 0, 0, 0], [2, 3, 4]), 4],
    [outcomes(2, false, [0, 0, 0, 0], [3, 4]), 6],
    [outcomes(1, true, [0, 0], [2, 2, 2]), 8]
  ]) {
    assert.equal(counts.size, size);
    assert.equal(new Set(counts.values()).size, 1);
  }
});

for (const id of ids.slice(2, 5)) {
  test(id + " updates the correct array and checks every required bit", () => {
    eachExample(id, trace => {
      for (const selection of ["First arrival", "Last arrival", "Unseen key"]) {
        const bits = 6, hashes = 3, copies = id.startsWith("repeated") ? 3 : 1;
        const frames = trace({ bits, hashes, copies, query: selection });
        const stream = input(frames);
        const expected = Array(bits * copies).fill(0);
        const assignments = new Map();
        function address(f, i, key) {
          assert.equal(focus(f), key);
          const [r, b] = active(f).id.split("-").map(Number);
          const h = i % hashes;
          assert.equal(r, Math.floor(i / hashes) % copies);
          assert.ok(b >= 0 && b < bits);
          if (id.startsWith("partitioned")) assert.equal(Math.floor(b / (bits / hashes)), h);
          const lookup = [key, r, h].join(",");
          if (assignments.has(lookup)) assert.equal(b, assignments.get(lookup));
          assignments.set(lookup, b);
          return r * bits + b;
        }
        const writes = atLine(frames, 1);
        assert.equal(writes.length, stream.length * copies * hashes);
        writes.forEach((f, i) => {
          expected[address(f, i, stream[Math.floor(i / (copies * hashes))])] = 1;
          assert.deepEqual(values(f), expected);
        });
        const reads = atLine(frames, 2);
        assert.equal(reads.length, copies * hashes);
        const key = focus(frames.at(-1));
        const hits = reads.map((f, i) => expected[address(f, i, key)]);
        const present = selection !== "Unseen key";
        assert.equal(stream.includes(key), present);
        if (present) {
          assert.ok(hits.every(Boolean));
          assert.equal(key, selection === "First arrival" ? stream[0] : stream.at(-1));
        }
        const work = atLine(frames, 3)[0].work;
        assert.ok(work.includes(hits.every(Boolean) ? "possibly present" : "definitely absent"));
        assert.ok(work.includes("Exact membership = " + (present ? "present" : "absent")));
        assert.equal(work.includes("false positive"), !present && hits.every(Boolean));
        let probability = 1;
        for (let r = 0; r < copies; r++) {
          const row = expected.slice(r * bits, (r + 1) * bits);
          if (id.startsWith("partitioned")) {
            for (let h = 0; h < hashes; h++) {
              const width = bits / hashes;
              probability *= sum(row.slice(h * width, (h + 1) * width)) / width;
            }
          } else {
            probability *= (sum(row) / bits) ** hashes;
          }
        }
        assert.ok(frames.at(-1).work.includes((probability * 100).toFixed(2) + "%"));
      }
    });
  });
}

test("Misra–Gries cancels full groups and bounds every prefix frequency", () => {
  eachExample("misra-gries", trace => {
    for (const capacity of [1, 2, 4]) {
      const frames = trace({ capacity });
      const stream = input(frames);
      const expected = new Map();
      let rounds = 0;
      stream.forEach((key, i) => {
        if (expected.has(key) || expected.size < capacity) {
          expected.set(key, (expected.get(key) || 0) + 1);
        } else {
          rounds++;
          for (const [k, n] of expected) {
            if (n === 1) expected.delete(k);
            else expected.set(k, n - 1);
          }
        }
        const tracked = new Map(memory(frames[i + 1]).filter(n => n.value)
          .map(n => [Number(n.label.split(" ")[0]), n.value]));
        assert.deepEqual(tracked, expected);
        assert.equal(i + 1 - sum([...tracked.values()]), rounds * (capacity + 1));
        for (const k of stream) {
          const exact = frequency(stream.slice(0, i + 1), k);
          const count = tracked.get(k) || 0;
          assert.ok(count <= exact && exact <= count + rounds);
        }
      });
      const estimate = expected.get(stream[0]) || 0;
      assert.ok(frames.at(-1).work.includes("Bounds = [" + estimate + ", " + (estimate + rounds) + "]"));
    }
  });
});

for (const signed of [false, true]) {
  const id = signed ? "count-sketch" : "count-min-sketch";
  test(id + " updates one hashed cell per row and reads the correct estimator", () => {
    let belowZero = false;
    let sawError = false;
    eachExample(id, trace => {
      for (const query of ["First arrival", "Last arrival", "Unseen key"]) {
        const rows = 3, width = 2;
        const frames = trace({ rows, width, query });
        const stream = input(frames);
        const counts = Array(rows * width).fill(0);
        const lookups = new Map();
        atLine(frames, 1).forEach((f, i) => {
          const key = stream[Math.floor(i / rows)];
          assert.equal(focus(f), key);
          const n = active(f);
          const [r, b] = n.id.split("-").map(Number);
          assert.equal(r, i % rows);
          const j = r * width + b;
          const delta = n.value - counts[j];
          assert.ok(delta === 1 || (signed && delta === -1));
          const lookup = key + "," + r;
          if (lookups.has(lookup)) assert.deepEqual([b, delta], lookups.get(lookup));
          lookups.set(lookup, [b, delta]);
          counts[j] += delta;
          assert.deepEqual(values(f), counts);
          assert.equal(n.y, n.value);
          belowZero ||= n.y < 0;
        });
        const final = frames.at(-1);
        const key = focus(final);
        const exact = frequency(stream, key);
        const readings = atLine(frames, 2).map((f, r) => {
          const n = active(f);
          const b = Number(n.id.split("-")[1]);
          const delta = signed ? Number(f.work.match(/Read (-?1) ×/)[1]) : 1;
          if (exact) assert.deepEqual([b, delta], lookups.get(key + "," + r));
          return delta * counts[r * width + b];
        }).sort((a, b) => a - b);
        assert.equal(readings.length, rows);
        const estimate = readings[signed ? 1 : 0];
        sawError ||= estimate !== exact;
        assert.ok(signed || estimate >= exact);
        assert.ok(final.work.includes("] = " + estimate + ". Exact count = " + exact + ". Error = " + (estimate - exact)));
      }
    });
    assert.equal(belowZero, signed);
    assert.ok(sawError);
  });
}
