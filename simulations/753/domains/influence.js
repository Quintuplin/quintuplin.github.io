(() => {
  "use strict";
  const presets = [
    { name: "Relay with shortcut", links: [["A","B",4], ["B","C",2], ["A","C",1], ["C","D",4]] },
    { name: "Two feeders", links: [["A","C",3], ["B","C",4], ["C","D",4], ["B","E",2]] },
    { name: "Loop and spur", links: [["A","B",2], ["B","C",4], ["C","A",2], ["C","D",3], ["D","E",2]] }
  ];
  const seeds = { key: "seeds", label: "Starting nodes", options: ["A", "B", "A and B"], value: "A" };
  const boost = { key: "boost", label: "Extra edge weight (sixteenths)", min: 0, max: 3, step: 1, value: 1 };
  const positions = { A: [-2, 1, -1], B: [0, 2, 1], C: [1, 0, -1], D: [3, 1, 1], E: [3, -1, -2] };
  const names = set => [...set].join(", ") || "∅";
  const runCount = active => "Activated nodes in this run = |{" + names(active) + "}| = " + active.size + ".";
  const freezeList = items => Object.freeze(items.map(Object.freeze));
  const register = spec => globalThis.Sims.register({ topic: "Influence", presets, ...spec });

  function network(preset, params, rng) {
    const links = preset.links.map(([from, to, base]) => ({ from, to, units: 4 * (base + params.boost) + Math.floor(rng() * 4) }));
    const vertices = [...new Set(links.flatMap(e => [e.from, e.to]))].sort();
    const start = new Set(params.seeds ? params.seeds.split(" and ") : []);
    const frames = [];
    function emit(line, work, active, marked = [], focus = [], labels = {}) {
      const nodes = vertices.map(id => {
        const [x, y, z] = positions[id];
        const group = focus.includes(id) ? 3 : start.has(id) ? 2 : active.has(id) ? 1 : 0;
        return { id, label: labels[id] || id, x, y, z, group, active: active.has(id) };
      });
      const edges = links.map(e => ({ from: e.from, to: e.to, directed: true, active: marked.includes(e) }));
      frames.push(Object.freeze({ line, work, nodes: freezeList(nodes), edges: freezeList(edges) }));
    }
    emit(0, "Directed edge weights in order: " + links.map(e => e.from + "→" + e.to + " = " + e.units + "/64").join(", ") +
      ". Initial seeds = {" + names(start) + "}.", start);
    return { links, vertices, start, emit, frames };
  }

  register({
    id: "independent-cascade", title: "Independent cascade", params: [seeds, boost],
    description: "Follow a relay from its starting nodes. Each newly active node gets one independent attempt on each inactive neighbour.",
    code: ["active ← frontier ← seeds", "while frontier ≠ ∅: next ← ∅",
      "    for (u,v) from frontier with v outside active ∪ next:",
      "        draw ← uniformInteger(0,63)", "        if draw < 64 × p[u,v]: next.add(v)",
      "    active ← active ∪ next; frontier ← next", "return size(active)"],
    trace(preset, params, rng) {
      const { links, start, emit, frames } = network(preset, params, rng);
      const active = new Set(start);
      let frontier = start;
      while (frontier.size) {
        const next = new Set();
        for (const e of links) {
          if (!frontier.has(e.from) || active.has(e.to) || next.has(e.to)) continue;
          const draw = Math.floor(64 * rng());
          emit(3, e.from + "→" + e.to + " draws " + draw + " from 0…63. Success buckets = 0…" + (e.units - 1) + ".", active, [e]);
          if (draw < e.units) next.add(e.to);
          emit(4, draw + (draw < e.units ? " < " : " ≥ ") + e.units + ". Next wave = {" + names(next) + "}.", active, [e], [...next]);
        }
        for (const v of next) active.add(v);
        frontier = next;
        emit(5, "Activate {" + names(next) + "}. Active so far = {" + names(active) + "}.", active);
      }
      emit(6, runCount(active), active);
      return frames;
    }
  });

  register({
    id: "linear-threshold", title: "Linear threshold", params: [seeds, boost],
    description: "Each node draws a threshold once. At each wave, add the weights from already active neighbours and compare the sum with that threshold.",
    code: ["active ← seeds", "for v outside seeds: θ[v] ← uniformInteger(1,64) / 64",
      "repeat: next ← ∅", "    for v outside active: w ← sum(b[u,v] for u in active)",
      "        if w ≥ θ[v]: next.add(v)", "    active ← active ∪ next", "until next = ∅; return size(active)"],
    trace(preset, params, rng) {
      const { links, vertices, start, emit, frames } = network(preset, params, rng);
      const active = new Set(start);
      const thresholds = {};
      const labels = {};
      for (const v of vertices.filter(v => !active.has(v))) {
        thresholds[v] = 1 + Math.floor(rng() * 64);
        labels[v] = v + " θ" + thresholds[v] + "/64";
        emit(1, "Threshold for " + v + " = " + thresholds[v] + "/64. All incoming weights are multiples of 1/64.", active, [], [v], labels);
      }
      let next;
      do {
        next = [];
        for (const v of vertices.filter(v => !active.has(v))) {
          const incoming = links.filter(e => e.to === v && active.has(e.from));
          const units = incoming.reduce((s, e) => s + e.units, 0);
          emit(3, v + " receives (" + (incoming.map(e => e.units).join(" + ") || "0") + ")/64 = " + units + "/64.", active, incoming, [v], labels);
          if (units >= thresholds[v]) next.push(v);
          emit(4, units + "/64 " + (units >= thresholds[v] ? "≥" : "<") + " " + thresholds[v] + "/64. Next wave = {" + names(next) + "}.", active, incoming, next, labels);
        }
        for (const v of next) active.add(v);
        emit(5, "Activate {" + names(next) + "}. Active = {" + names(active) + "}.", active, [], [], labels);
      } while (next.length);
      emit(6, runCount(active), active, [], [], labels);
      return frames;
    }
  });

  function reach(seeds, live) {
    const reached = new Set(seeds);
    for (const u of reached) {
      for (const edge of live) if (edge.from === u) reached.add(edge.to);
    }
    return reached;
  }

  register({
    id: "mutually-exclusive-cascade", title: "Mutually exclusive cascade", params: [seeds, boost],
    description: "Each node independently picks at most one incoming edge. Its parent can activate it only if the relay reaches that parent.",
    code: ["live ← ∅; active ← seeds", "for v in vertices: j ← uniformInteger(0,63)",
      "    parent ← intervalLookup(incoming[v], j, default=none)", "    if parent ≠ none: live.add((parent,v))",
      "for u in growingSet(active): active.addAll(outNeighbours(u,live))", "return size(active)"],
    trace(preset, params, rng) {
      const { links, vertices, start, emit, frames } = network(preset, params, rng);
      const live = [];
      for (const v of vertices) {
        let end = 0;
        const j = Math.floor(64 * rng());
        const ranges = [];
        let chosen;
        for (const e of links.filter(e => e.to === v)) {
          ranges.push(e.from + " [" + end + "," + (end + e.units) + ")");
          if (j >= end && j < end + e.units) chosen = e;
          end += e.units;
        }
        emit(2, v + " draws " + j + ". Parent intervals: " + [...ranges, "none [" + end + ",64)"].join(", ") + ".", start, live, [v]);
        if (chosen) live.push(chosen);
        emit(3, v + " picks " + (chosen ? chosen.from + "→" + v : "no parent") + ".", start, live, [v]);
      }
      const active = new Set(start);
      for (const u of active) {
        const outgoing = live.filter(e => e.from === u);
        for (const e of outgoing) active.add(e.to);
        emit(4, "From " + u + " follow {" + names(outgoing.map(e => e.to)) + "}. Reached = {" + names(active) + "}.", active, outgoing);
      }
      emit(5, runCount(active), active, live);
      return frames;
    }
  });

  // Each edge has 64 equiprobable outcomes. Keep integer numerators until display.
  function worlds(links) {
    return Array.from({ length: 2 ** links.length }, (_, mask) => {
      const live = links.filter((e, i) => (mask & (1 << i)) !== 0);
      const mass = links.reduce((p, e) => p * (live.includes(e) ? e.units : 64 - e.units), 1);
      return { live, mass };
    });
  }
  const expectation = (worlds, seeds) => worlds.reduce((s, w) => s + w.mass * reach(seeds, w.live).size, 0);
  register({
    id: "live-edge-spread", title: "Exact live-edge spread", params: [seeds, boost],
    description: "Enumerate every live or blocked configuration of a small independent-cascade graph. Weight each reachable set by the probability of its configuration.",
    code: ["total ← 0", "for live in subsets(edges):", "    p ← product(p[e] if e in live else 1−p[e] for e in edges)",
      "    reached ← reachable(seeds, live)", "    total ← total + p × size(reached)", "return total"],
    trace(preset, params, rng) {
      const { links, start, emit, frames } = network(preset, params, rng);
      const denom = 64 ** links.length;
      let sum = 0;
      for (const w of worlds(links)) {
        const reached = reach(start, w.live);
        const factors = links.map(e => w.live.includes(e) ? e.units : 64 - e.units);
        emit(2, "World [" + links.map(e => Number(w.live.includes(e))).join("") + "] in edge order. P = (" +
          factors.join(" × ") + ")/" + denom + " = " + w.mass + "/" + denom + ".", start, w.live);
        emit(3, "Reachable from {" + names(start) + "} = {" + names(reached) + "}.", reached, w.live);
        sum += w.mass * reached.size;
        emit(4, "Add " + w.mass + "/" + denom + " × " + reached.size + ". Running spread = " + sum + "/" + denom + ".", reached, w.live);
      }
      emit(5, "Expected spread = " + sum + "/" + denom + " = " + sum / denom + ".", start);
      return frames;
    }
  });

  register({
    id: "greedy-influence", title: "Greedy influence maximisation",
    params: [{ key: "budget", label: "Nodes to select", min: 1, max: 3, step: 1, value: 2 }, boost],
    description: "Add the node with the largest gain in expected spread. Recalculate every remaining gain after each choice. Alphabetical order breaks ties.",
    code: ["S ← ∅; spread ← 0", "while size(S) < budget:", "    for v outside S: gain[v] ← E[reach(S ∪ {v})] − spread",
      "    v ← firstArgMax(gain[v] for v outside S); S.add(v); spread ← spread + gain[v]", "return S, spread"],
    trace(preset, params, rng) {
      const { links, vertices, emit, frames } = network(preset, params, rng);
      const all = worlds(links);
      const denom = 64 ** links.length;
      const chosen = new Set();
      let sum = 0;
      while (chosen.size < params.budget) {
        let best, largest = -1;
        for (const v of vertices.filter(v => !chosen.has(v))) {
          const enlarged = expectation(all, [...chosen, v]);
          const gain = enlarged - sum;
          emit(2, "Gain(" + v + " | {" + names(chosen) + "}) = (" + enlarged + " − " + sum + ")/" + denom + " = " + gain / denom + ".", chosen, [], [v]);
          if (gain > largest) { best = v; largest = gain; }
        }
        chosen.add(best);
        sum += largest;
        emit(3, "Select " + best + " with gain " + largest / denom + ". Expected spread = " + sum / denom + ".", chosen);
      }
      emit(4, "Selected {" + names(chosen) + "}. Expected spread = " + sum + "/" + denom + " = " + sum / denom + ".", chosen);
      return frames;
    }
  });
})();
