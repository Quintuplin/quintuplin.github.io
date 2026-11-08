const test = require("node:test");
const assert = require("node:assert/strict");
const specs = new Map();
globalThis.Sims = { register(spec) {
  assert.ok(!specs.has(spec.id));
  specs.set(spec.id, spec);
} };
require("../../simulations/753/domains/influence.js");
require("../../simulations/753/domains/randomisation.js");
delete globalThis.Sims;

function random(seed) {
  return () => {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}
function run(id, preset, seed, changes = {}, rng = random(seed)) {
  const spec = specs.get(id);
  const params = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  return spec.trace(preset, { ...params, ...changes }, rng);
}
// Reproduce the shared player's seed-753 lesson fixtures alongside the independent LCG cases.
function lesson(id, preset = 0, changes = {}) {
  let state = 753;
  return run(id, specs.get(id).presets[preset], state, changes, () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let bits = Math.imul(state ^ (state >>> 15), state | 1);
    bits ^= bits + Math.imul(bits ^ (bits >>> 7), bits | 61);
    return ((bits ^ (bits >>> 14)) >>> 0) / 2 ** 32;
  });
}
function examples(id, check) {
  for (const preset of specs.get(id).presets) {
    for (const seed of [17, 753, 19993]) check((p = {}) => run(id, preset, seed, p), preset, seed);
  }
}
const bracket = text => text.match(/\[(.*?)\]/)[1].split(", ");
const onLine = (frames, n) => frames.filter(f => f.line === n);
const lit = frame => frame.nodes.filter(n => n.active).map(n => n.id).sort();
const live = frame => frame.edges.filter(e => e.active);
const edgeId = e => e.from + e.to;
function graph(frame) {
  return [...frame.work.matchAll(/([A-E])→([A-E]) = (\d+)\/(\d+)/g)]
    .map(([, from, to, w, denominator]) => ({ from, to, p: Number(w) / Number(denominator) }));
}
function closure(start, edges) {
  const reached = new Set(start);
  let size;
  do {
    size = reached.size;
    for (const e of edges) if (reached.has(e.from)) reached.add(e.to);
  } while (size !== reached.size);
  return [...reached].sort();
}
function expected(start, edges, kept = [], i = 0) {
  if (i === edges.length) return closure(start, kept).length;
  const e = edges[i];
  return (1 - e.p) * expected(start, edges, kept, i + 1) + e.p * expected(start, edges, [...kept, e], i + 1);
}

test("independent registration, replay, raw input changes, snapshots, edge endpoints and controls", () => {
  assert.equal(specs.size, 11);
  for (const spec of specs.values()) {
    assert.ok(new Set(spec.presets.map(p => p.name)).size >= 3);
    for (const preset of spec.presets) {
      const frames = run(spec.id, preset, 753);
      assert.deepEqual(frames, run(spec.id, preset, 753));
      assert.notEqual(frames[0].work, run(spec.id, preset, 19993)[0].work, spec.id);
      const used = new Set();
      for (const f of frames) {
        assert.ok(Number.isInteger(f.line) && spec.code[f.line] && f.work.trim());
        assert.ok(Object.isFrozen(f) && Object.isFrozen(f.nodes));
        const ids = new Set(f.nodes.map(n => n.id));
        assert.equal(ids.size, f.nodes.length);
        for (const n of f.nodes) {
          assert.ok(Object.isFrozen(n) && !used.has(n) && n.label && [n.x,n.y,n.z].every(Number.isFinite));
          used.add(n);
        }
        for (const e of f.edges || []) assert.ok(Object.isFrozen(e) && e.directed && ids.has(e.from) && ids.has(e.to));
      }
      assert.ok(frames.some(f => new Set(f.nodes.map(n => n.z)).size > 1));
      for (const p of spec.params) {
        for (const x of (p.options || [p.min, p.max]).filter(x => x !== p.value)) {
          assert.notDeepEqual(frames, run(spec.id, preset, 753, { [p.key]: x }), spec.id + " " + p.key);
        }
      }
    }
  }
});

test("sampled cascades report activated nodes in this run and live-edge reports their expectation", () => {
  for (const id of ["independent-cascade", "linear-threshold", "mutually-exclusive-cascade"]) {
    const final = lesson(id).at(-1);
    const active = lit(final);
    if (id === "independent-cascade") assert.equal(active.length, 2);
    assert.match(final.work, /^Activated nodes in this run = /);
    assert.ok(final.work.endsWith(" = " + active.length + "."));
  }
  const weighted = lesson("live-edge-spread");
  assert.equal(expected(["A"], graph(weighted[0])), 1.6547253131866455);
  assert.match(weighted.at(-1).work, /^Expected spread = .* = 1\.6547253131866455\.$/);
});

test("independent cascade uses one trial per eligible edge per frontier", () => {
  examples("independent-cascade", (run, preset, seed) => {
    for (const seeds of ["A", "B", "A and B"]) {
      const frames = run({ seeds }), edges = graph(frames[0]);
      const rng = random(seed);
      preset.links.forEach(() => rng());
      const active = new Set(seeds.split(" and "));
      let frontier = new Set(active), frame = 1;
      while (frontier.size) {
        const next = new Set();
        for (const e of edges) {
          if (!frontier.has(e.from) || active.has(e.to) || next.has(e.to)) continue;
          const draw = frames[frame++];
          assert.equal(draw.line, 3);
          assert.deepEqual(live(draw).map(edgeId), [edgeId(e)]);
          if (rng() < e.p) next.add(e.to);
          const decision = frames[frame++];
          assert.deepEqual(lit(decision), [...active].sort());
          assert.deepEqual(decision.nodes.filter(n => n.group === 3).map(n => n.id), [...next].sort());
        }
        for (const v of next) active.add(v);
        assert.deepEqual(lit(frames[frame++]), [...active].sort());
        frontier = next;
      }
      assert.equal(frames.length, frame + 1);
      assert.deepEqual(lit(frames.at(-1)), [...active].sort());
    }
  });
});

test("handwritten seed and frontier sets have zero members when empty", () => {
  const initial = lesson("greedy-influence")[0];
  assert.deepEqual(lit(initial), []);
  assert.ok(initial.work.endsWith("Initial seeds = {}."));
  const frames = lesson("independent-cascade");
  const waves = onLine(frames, 5);
  const [previous, last] = waves.slice(-2);
  assert.deepEqual(lit(last), lit(previous));
  assert.ok(last.work.startsWith("Activate {}."));
  assert.ok(frames.every(f => !f.work.includes("{∅}")));
});

test("linear thresholds persist and only the previous wave contributes to each comparison", () => {
  examples("linear-threshold", run => {
    for (const seeds of ["A", "A and B"]) {
      const frames = run({ seeds, boost: 3 }), edges = graph(frames[0]);
      const vertices = frames[0].nodes.map(n => n.id);
      const theta = Object.fromEntries(onLine(frames, 1).map(f => {
        const [, v, n, denominator] = f.work.match(/for (\w) = (\d+)\/(\d+)/);
        return [v, Number(n) / Number(denominator)];
      }));
      let active = seeds.split(" and ");
      for (const wave of onLine(frames, 5)) {
        const next = vertices.filter(v => !active.includes(v) &&
          edges.filter(e => e.to === v && active.includes(e.from)).reduce((s, e) => s + e.p, 0) >= theta[v]);
        active = [...active, ...next].sort();
        assert.deepEqual(lit(wave), active);
      }
      assert.deepEqual(lit(frames.at(-1)), active);
    }
  });
});

test("inspecting a threshold or scoring a candidate preserves active membership", () => {
  const threshold = lesson("linear-threshold").find(f => f.line === 1);
  assert.match(threshold.work, /B = 13\/64/);
  assert.deepEqual(lit(threshold), ["A"]);
  const b = threshold.nodes.find(n => n.id === "B");
  assert.notEqual(b.group, threshold.nodes.find(n => n.id === "C").group);
  let selected = [];
  for (const frame of lesson("greedy-influence")) {
    if (frame.line === 2) assert.deepEqual(lit(frame), selected);
    if (frame.line === 3) selected = lit(frame);
  }
});

test("exclusive cascade assigns at most one incoming parent using its disjoint interval", () => {
  examples("mutually-exclusive-cascade", (run, preset, seed) => {
    const frames = run({ boost: 3 }), edges = graph(frames[0]);
    const rng = random(seed);
    preset.links.forEach(() => rng());
    const selected = [];
    for (const node of frames[0].nodes) {
      let j = rng();
      const incoming = edges.filter(e => e.to === node.id);
      assert.ok(incoming.reduce((s, e) => s + e.p, 0) <= 1);
      for (const edge of incoming) {
        if (j < edge.p) { selected.push(edge); break; }
        j -= edge.p;
      }
    }
    assert.deepEqual(live(frames.at(-1)).map(edgeId).sort(), selected.map(edgeId).sort());
    assert.deepEqual(lit(frames.at(-1)), closure(["A"], selected));
  });
});

test("live-edge enumeration covers every mask, normalises and weights directed reachability", () => {
  examples("live-edge-spread", run => {
    const frames = run({ seeds: "A and B" }), edges = graph(frames[0]);
    const masks = new Set();
    let mass = 0, spread = 0;
    const weights = onLine(frames, 2), reached = onLine(frames, 3);
    assert.equal(weights.length, 2 ** edges.length);
    weights.forEach((f, i) => {
      const ids = live(f).map(edgeId);
      assert.ok(!masks.has(ids.join()));
      masks.add(ids.join());
      const p = edges.reduce((s, e) => s * (ids.includes(edgeId(e)) ? e.p : 1 - e.p), 1);
      const [, numerator, denominator] = f.work.match(/= (\d+)\/(\d+)\.$/);
      assert.equal(Number(numerator) / Number(denominator), p);
      const nodes = closure(["A", "B"], live(f));
      assert.deepEqual(lit(reached[i]), nodes);
      mass += p;
      spread += p * nodes.length;
    });
    assert.equal(mass, 1);
    assert.equal(spread, expected(["A","B"], edges));
    assert.ok(frames.at(-1).work.endsWith(" = " + spread + "."));
  });
});

test("displayed greedy argmax selects two distinct seeds on Relay with shortcut", () => {
  const frames = lesson("greedy-influence");
  const spec = specs.get("greedy-influence");
  const selected = [];
  const gains = new Map();
  for (const frame of frames) {
    if (frame.line === 2) {
      const [, v, gain] = frame.work.match(/^Gain\((\w).* = ([\d.]+)\.$/);
      gains.set(v, Number(gain));
    }
    if (frame.line === 3) {
      // A stale score remains in the table. Apply the displayed candidate domain.
      const eligible = [...gains].filter(([v]) => !spec.code[3].includes("v outside S") || !selected.includes(v));
      const [v] = eligible.sort((a, b) => b[1] - a[1])[0];
      selected.push(v);
      assert.ok(frame.work.startsWith("Select " + v + " "));
    }
  }
  assert.deepEqual(selected, ["A", "C"]);
  assert.ok(frames.at(-1).work.endsWith(" = 2.671875."));
});

test("greedy scores every remaining node against the updated seed set", () => {
  examples("greedy-influence", run => {
    const frames = run({ budget: 3 }), edges = graph(frames[0]), chosen = [];
    let i = 1;
    while (chosen.length < 3) {
      const old = expected(chosen, edges);
      const candidates = frames[0].nodes.map(n => n.id).filter(v => !chosen.includes(v));
      const gains = candidates.map(v => {
        const gain = expected([...chosen, v], edges) - old;
        const frame = frames[i++];
        assert.equal(frame.line, 2);
        assert.ok(frame.work.startsWith("Gain(" + v + " |") && frame.work.endsWith(" = " + gain + "."));
        return gain;
      });
      chosen.push(candidates[gains.indexOf(Math.max(...gains))]);
      assert.deepEqual(lit(frames[i++]), [...chosen].sort());
    }
    assert.deepEqual(lit(frames.at(-1)), [...chosen].sort());
    assert.ok(frames.at(-1).work.endsWith(" = " + expected(chosen, edges) + "."));
  });
});

for (const id of ["quickselect", "random-pivot-quicksort"]) {
  test(id + " preserves duplicates, partitions around the pivot and returns the exact answer", () => {
    examples(id, run => {
      const select = id === "quickselect";
      for (const p of select ? [1,2,3,4,5,6].map(rank => ({ rank })) : ["Largest first","Smallest first"].map(order => ({ order }))) {
        const frames = run(p);
        const original = bracket(frames[0].work).map(Number);
        const sorted = [...original].sort((a,b) => p.order === "Largest first" ? b - a : a - b);
        let pivot;
        for (const f of frames) {
          if (f.line === 3) pivot = Number(f.nodes.find(n => n.active).label);
          if (f.line === 5) {
            for (const n of f.nodes.filter(n => n.group >= 2)) {
              const cmp = Math.sign(Number(n.label) - pivot) * (p.order === "Largest first" ? -1 : 1);
              assert.equal(n.group, cmp + 3);
            }
          }
        }
        if (select) assert.equal(frames.at(-1).work, "Rank " + p.rank + " = " + sorted[p.rank - 1] + ".");
        else assert.deepEqual(frames.at(-1).nodes.map(n => Number(n.label)), sorted);
      }
    });
  });
}

test("find-a returns a matching zero-based index or an inconclusive result at exactly the limit", () => {
  let boundedMiss = false;
  for (const id of ["las-vegas-find-a", "monte-carlo-find-a"]) {
    examples(id, run => {
      for (const limit of [1, 4, 12]) {
        const frames = run({ limit }), letters = bracket(frames[0].work);
        const probes = onLine(frames, 2);
        const indices = probes.map(f => Number(f.nodes.find(n => n.active).id.slice(1)));
        assert.ok(indices.slice(0,-1).every(i => letters[i] !== "a"));
        const final = frames.at(-1);
        if (final.line === 3) {
          assert.equal(letters[indices.at(-1)], "a");
          assert.ok(final.work.includes("Return index " + indices.at(-1) + " "));
        } else {
          assert.equal(id, "monte-carlo-find-a");
          assert.equal(probes.length, limit);
          assert.notEqual(letters[indices.at(-1)], "a");
          boundedMiss = true;
        }
      }
    });
  }
  assert.ok(boundedMiss);
});

test("coupon collection stops on the final distinct type and matches the harmonic expectation", () => {
  examples("coupon-collector", run => {
    const frames = run({ size: 6 });
    const counts = new Map();
    const draws = onLine(frames, 3);
    for (const f of draws) {
      assert.ok(counts.size < 6);
      const type = f.nodes.find(n => n.active).id;
      counts.set(type, (counts.get(type) || 0) + 1);
      for (const n of f.nodes) assert.equal(n.y, counts.get(n.id) || 0);
    }
    assert.equal(counts.size, 6);
    assert.ok(frames.at(-1).work.includes("in " + draws.length + " draws"));
    assert.ok(frames.at(-1).work.includes("14.7000"));
  });
});

test("card guesses use the chosen memory rule, reveal each card once and score only matches", () => {
  examples("card-guessing", run => {
    for (const memory of ["Unseen cards", "All cards"]) {
      const frames = run({ size: 5, memory });
      const deck = bracket(frames[0].work), seen = new Set();
      let score = 0;
      deck.forEach((card, i) => {
        const guessFrame = frames[1 + 2*i], reveal = frames[2 + 2*i];
        const guess = guessFrame.nodes.find(n => n.active).id;
        const pool = bracket(guessFrame.work);
        assert.deepEqual(new Set(pool), new Set(deck.filter(t => memory === "All cards" || !seen.has(t))));
        assert.ok(pool.includes(guess));
        assert.equal(reveal.nodes.find(n => n.active).id, card);
        if (guess === card) score++;
        assert.ok(reveal.work.endsWith("Score = " + score + "."));
        seen.add(card);
      });
      assert.equal(seen.size, 5);
      assert.ok(frames.at(-1).work.includes("= " + score + "/5"));
      assert.ok(frames.at(-1).work.endsWith(memory === "Unseen cards" ? "2.2833." : " = 1."));
    }
  });
});
