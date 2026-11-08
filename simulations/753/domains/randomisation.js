(() => {
  "use strict";
  const register = spec => globalThis.Sims.register({ topic: "Randomised algorithms", ...spec });
  const range = (key, label, min, max, value) => ({ key, label, min, max, step: 1, value });
  const index = (rng, n) => Math.floor(rng() * n);
  const show = a => "[" + a.join(", ") + "]";
  function shuffled(items, rng) {
    const a = [...items];
    for (let i = a.length - 1; i > 0; i--) {
      const j = index(rng, i + 1);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  function cell(id, label, x, y, z, group, active, shape = "cell") {
    return { id, label, x, y, z, group, active, shape };
  }
  function record(frames, line, work, nodes) {
    frames.push(Object.freeze({ line, work, nodes: Object.freeze(nodes.map(Object.freeze)) }));
  }
  const runs = [
    { name: "Paired measurements", values: [3, 1, 3, 2, 4, 2, 1] },
    { name: "Descending ridge", values: [7, 6, 5, 4, 3, 2] },
    { name: "Alternating peaks", values: [1, 6, 2, 5, 3, 4, 2, 5] }
  ];
  for (const select of [false, true]) {
    register({
      id: select ? "quickselect" : "random-pivot-quicksort", title: select ? "Random-pivot quickselect" : "Random-pivot quicksort",
      presets: runs, params: select ? [range("rank", "Rank from smallest (capped at input length)", 1, Math.max(...runs.map(p => p.values.length)), 3)] :
        [{ key: "order", label: "Sort order", options: ["Smallest first", "Largest first"], value: "Smallest first" }],
      description: select ? "Partition around a random pivot. Continue only in the part containing the requested rank. Equal values occupy consecutive ranks." :
        "Choose a random pivot in each subarray. Group smaller, equal and larger values, then sort the two outer groups.",
      code: [select ? "A ← input; rank ← min(requested, length(A))" : "A ← input", "visit(lo, hi):", select ? "    if hi − lo = 1: return A[lo]" : "    if hi − lo ≤ 1: return",
        "    pivot ← uniformChoice(A[lo:hi]); groups ← [[], [], []]",
        "    for x in A[lo:hi]: groups[1 + compare(x,pivot,order)].append(x)",
        "    before, equal, after ← groups; A[lo:hi] ← before ++ equal ++ after",
        ...(select ? ["    if rank ≤ lo + size(before): return visit(left)",
          "    if rank ≤ lo + size(before) + size(equal): return pivot", "    return visit(right)", "return visit(0, size(A))"] :
          ["    visit(left); visit(right)", "visit(0, size(A)); return A"])],
      trace(preset, params, rng) {
        const offset = index(rng, 30);
        const keys = new Map([...new Set(preset.values)].map(v => [v, offset + 3 * v + index(rng, 3)]));
        const a = preset.values.map((v, i) => ({ id: "i" + i, v: keys.get(v) }));
        const frames = [];
        const vals = list => list.map(item => item.v);
        const order = params.order === "Largest first" ? -1 : 1;
        const rank = select ? Math.min(params.rank, a.length) : undefined;
        function emit(line, work, lo, hi, groups = new Map(), focus) {
          record(frames, line, work, a.map((item, i) => {
            const lane = groups.get(item) ?? (i >= lo && i < hi ? 0 : -1);
            return cell(item.id, String(item.v), i * 2, item.v / 8, lane * 2, lane + 1, item === focus, "bar");
          }));
        }
        const setting = select ? "Valid ranks = 1…" + a.length + ". " +
          (rank < params.rank ? "Requested " + params.rank + " exceeds " + a.length + ". " : "") + "Rank = " + rank :
          "Order = " + params.order;
        emit(0, "Input A = " + show(vals(a)) + ". " + setting + ".", 0, a.length);
        function visit(lo, hi) {
          if (hi - lo <= 1) {
            emit(2, "A[" + lo + ":" + hi + "] = " + show(vals(a.slice(lo, hi))) + ". Base case.", lo, hi);
            return a[lo]?.v;
          }
          const pivot = a[lo + index(rng, hi - lo)];
          emit(3, "Choose uniformly from " + show(vals(a.slice(lo, hi))) + ". Pivot = " + pivot.v + ".", lo, hi, undefined, pivot);
          const parts = [[], [], []];
          const groups = new Map();
          for (const item of a.slice(lo, hi)) {
            const comparison = order * (item.v - pivot.v);
            const g = comparison < 0 ? 0 : comparison === 0 ? 1 : 2;
            parts[g].push(item);
            groups.set(item, g + 1);
            emit(4, item.v + (item.v < pivot.v ? " < " : item.v > pivot.v ? " > " : " = ") + pivot.v +
              ". " + ["Before","Equal","After"][g] + " = " + show(vals(parts[g])) + ".", lo, hi, groups, item);
          }
          a.splice(lo, hi - lo, ...parts.flat());
          const first = lo + parts[0].length, last = first + parts[1].length;
          emit(5, "A[" + lo + ":" + hi + "] ← " + parts.map(p => show(vals(p))).join(" ++ ") + ".", lo, hi, groups);
          if (select) {
            const side = rank <= first ? "left" : rank <= last ? "equal" : "right";
            emit(side === "left" ? 6 : side === "equal" ? 7 : 8, "Pivot ranks = " + (first + 1) + "…" + last +
              ". Rank " + rank + " lies in " + side + ".", lo, hi, groups, pivot);
            if (side === "equal") return pivot.v;
            return side === "left" ? visit(lo, first) : visit(last, hi);
          }
          emit(6, "Visit A[" + lo + ":" + first + "] then A[" + last + ":" + hi + "].", lo, hi, groups);
          visit(lo, first);
          visit(last, hi);
        }
        const answer = visit(0, a.length);
        emit(select ? 9 : 7, select ? "Rank " + rank + " = " + answer + "." : "Sorted A = " + show(vals(a)) + ".", 0, a.length);
        return frames;
      }
    });
  }

  const texts = [
    { name: "One signal", letters: "bcdafg" }, { name: "Alternating signals", letters: "abacadaf" },
    { name: "Cluster of signals", letters: "bcaaade" }
  ];
  for (const bounded of [false, true]) {
    register({
      id: bounded ? "monte-carlo-find-a" : "las-vegas-find-a", title: bounded ? "Bounded Monte Carlo find-a" : "Las Vegas find-a",
      presets: texts, params: [range("extra", "Additional letters changed to a", 0, 2, 0),
        ...(bounded ? [range("limit", "Maximum probes", 1, 12, 4)] : [])],
      description: bounded ? "Probe uniform random positions with replacement. A miss at the probe limit is inconclusive." :
        "Probe uniform random positions with replacement until an a is found. Every successful return identifies its position.",
      code: ["A ← input; tries ← 0", bounded ? "while tries < limit:" : "while true:",
        "    j ← uniformInteger(0, length(A)−1); tries += 1", "    if A[j] = 'a': return j",
        ...(bounded ? ["return inconclusive"] : [])],
      trace(preset, params, rng) {
        const offset = index(rng, preset.letters.length);
        const rotated = preset.letters.slice(offset) + preset.letters.slice(0, offset);
        const letters = [...rotated].map(c => c === "a" ? "a" : String.fromCharCode(98 + index(rng, 25)));
        const misses = letters.map((c, i) => c === "a" ? -1 : i).filter(i => i >= 0);
        for (const i of misses.slice(0, params.extra)) letters[i] = "a";
        const frames = [], visits = letters.map(() => 0);
        const hits = letters.filter(c => c === "a").length, n = letters.length;
        function emit(line, work, chosen) {
          record(frames, line, work, letters.map((c, i) => cell("p" + i, i + "·" + c, (i % 4) * 2, visits[i],
            Math.floor(i / 4) * 3, c === "a" ? 1 : 0, i === chosen)));
        }
        const odds = bounded ? "P(all " + params.limit + " miss) = (" + (n - hits) + "/" + n + ")^" + params.limit +
          " ≈ " + ((1 - hits / n) ** params.limit).toFixed(5) : "Expected probes = " + n + "/" + hits;
        emit(0, "Input = " + show(letters) + ". P(hit) = " + hits + "/" + n + ". " + odds + ".");
        let tries = 0;
        while (!bounded || tries < params.limit) {
          const j = index(rng, n);
          tries++;
          visits[j]++;
          emit(2, "Probe " + tries + ": j = " + j + " among 0…" + (n - 1) + ". A[" + j + "] = " + letters[j] + ".", j);
          if (letters[j] === "a") {
            emit(3, "A[" + j + "] = a. Return index " + j + " after " + tries + " probes.", j);
            return frames;
          }
          emit(3, "A[" + j + "] = " + letters[j] + " ≠ a. Miss on probe " + tries + ".", j);
        }
        emit(4, "Used " + tries + " of " + params.limit + " probes. Return inconclusive.");
        return frames;
      }
    });
  }

  const packs = [
    { name: "Aviary", pool: ["tern","ibis","owl","wren","kite","robin","swift","crow"] },
    { name: "Paint box", pool: ["moss","ruby","teal","gold","ink","slate","rose","lime"] },
    { name: "Herb garden", pool: ["sage","mint","dill","thyme","basil","bay","chive","anise"] }
  ];
  for (const cards of [false, true]) {
    register({
      id: cards ? "card-guessing" : "coupon-collector", title: cards ? "Card guessing" : "Coupon collector", presets: packs,
      params: [range("size", cards ? "Cards in deck" : "Coupon types", 3, 7, 5),
        ...(cards ? [{ key: "memory", label: "Guess from", options: ["Unseen cards", "All cards"], value: "Unseen cards" }] : [])],
      description: cards ? "Guess before turning over each card. Compare the number correct with the expectation for the chosen memory rule." :
        "Draw uniform coupons with replacement until each type has appeared. Watch the probability of finding a new type fall as the collection grows.",
      code: cards ? ["deck ← shuffle(types); score ← 0", "for card in deck:",
        "    guess ← uniformChoice(unseen if usingMemory else types)", "    score += (guess = card); unseen.remove(card)", "return score"] :
        ["counts ← zeros(n); draws ← 0", "while any(counts = 0):", "    type ← uniformChoice(types)",
          "    counts[type] += 1; draws += 1", "return draws"],
      trace(preset, params, rng) {
        const n = params.size, types = shuffled(preset.pool, rng).slice(0, n);
        const counts = Array(n).fill(0), frames = [];
        function emit(line, work, chosen) {
          record(frames, line, work, types.map((t, i) => cell(t, t + "·" + counts[i], (i % 3) * 2, counts[i],
            Math.floor(i / 3) * 3, counts[i] ? 1 : 0, t === chosen, "bar")));
        }
        const harmonic = types.reduce((s, _, i) => s + 1 / (i + 1), 0);
        if (cards) {
          const deck = shuffled(types, rng);
          const unseen = new Set(types);
          let score = 0;
          emit(0, "Deck in reveal order = " + show(deck) + ". Score = 0.");
          for (const card of deck) {
            const pool = params.memory === "Unseen cards" ? [...unseen] : types;
            const guess = pool[index(rng, pool.length)];
            emit(2, "Guess " + guess + " from " + show(pool) + ". P(correct) = 1/" + pool.length + ".", guess);
            unseen.delete(card);
            counts[types.indexOf(card)]++;
            score += Number(guess === card);
            emit(3, "Reveal " + card + ". " + guess + (guess === card ? " = " : " ≠ ") + card + ". Score = " + score + ".", card);
          }
          emit(4, "Correct guesses = " + score + "/" + n + ". Expected correct = " +
            (params.memory === "Unseen cards" ? "H(" + n + ") ≈ " + harmonic.toFixed(4) : n + " × 1/" + n + " = 1") + ".");
        } else {
          emit(0, "Coupon types = " + show(types) + ". Collected = 0/" + n + ".");
          let distinct = 0, draws = 0;
          while (distinct < n) {
            const i = index(rng, n);
            emit(2, "P(new) = " + (n - distinct) + "/" + n + ". Draw " + (draws + 1) + " gives " + types[i] + ".", types[i]);
            if (counts[i] === 0) distinct++;
            counts[i]++;
            draws++;
            emit(3, types[i] + " count = " + counts[i] + ". Distinct types = " + distinct + "/" + n + ".", types[i]);
          }
          emit(4, "All " + n + " types collected in " + draws + " draws. Expected draws = " + n + " × H(" + n + ") ≈ " + (n * harmonic).toFixed(4) + ".");
        }
        return frames;
      }
    });
  }
})();
