(() => {
  "use strict";

  const register = spec => globalThis.Sims.register({ topic: "Streams and sketches", ...spec });
  const range = (key, label, min, max, value, step = 1) => ({ key, label, min, max, step, value });
  const choice = (key, label, options) => ({ key, label, options, value: options[0] });
  const query = choice("query", "Key to look up", ["First arrival", "Last arrival", "Unseen key"]);
  const hashes = range("hashes", "Hash functions per filter", 1, 3, 2);
  const presets = [
    { name: "Returning flock", pattern: [0, 0, 1, 2, 0, 3, 0, 0, 1] },
    { name: "Overlapping flights", pattern: [0, 1, 0, 2, 1, 2, 3, 1, 4, 2] },
    { name: "Late migration", pattern: [0, 1, 2, 3, 4, 5, 4, 5, 5, 5] }
  ];

  const draw = (rng, limit) => Math.floor(rng() * limit);
  const list = (length, fn) => Array.from({ length }, (_, i) => fn(i));
  const total = values => values.reduce((sum, n) => sum + n, 0);
  const node = (id, label, x, y, z, group, active = false, value = 0) =>
    ({ id, label, x, y, z, group, active, value });

  function arrivals(preset, rng) {
    // Give each flock a fresh set of tag numbers while preserving its return pattern.
    const tags = list(90, i => i + 10);
    const symbols = list(Math.max(...preset.pattern) + 2, () => tags.splice(draw(rng, tags.length), 1)[0]);
    return { stream: preset.pattern.map(i => symbols[i]), unseen: symbols.at(-1) };
  }

  function target({ stream, unseen }, selection) {
    if (selection === "Unseen key") return unseen;
    return selection === "Last arrival" ? stream.at(-1) : stream[0];
  }

  // A fixed table of independent uniform draws is a random function on this small universe.
  function hashTable(data, size, rng) {
    const table = new Map([...new Set([...data.stream, data.unseen])].map(key => [key, draw(rng, size)]));
    return key => table.get(key);
  }

  function recorder(stream, view) {
    const frames = [];
    function emit(line, work, key, active) {
      const nodes = view(active);
      if (key !== undefined) nodes.push(node("key", "Tag " + key, 0, 1, -3, 0, true, key));
      frames.push(Object.freeze({ line, work, nodes: Object.freeze(nodes.map(n => Object.freeze(n))) }));
    }
    emit(0, "Tag arrivals in order = [" + stream.join(", ") + "].");
    return { emit, frames };
  }

  register({
    id: "fixed-proportion-sampling", title: "Fixed-proportion key sampling", presets,
    description: "Hash each bird tag into one of six buckets. Every sighting of a tag follows its first sighting into or out of the sample.",
    params: [range("keep", "Buckets to keep out of six", 1, 5, 2)],
    code: ["Start six empty arrival counters.", "Look up the tag’s fixed bucket.",
      "Count the sighting and keep it if its bucket is below the cutoff.", "Compare retained sightings with all arrivals."],
    trace(preset, { keep }, rng) {
      const data = arrivals(preset, rng);
      const hash = hashTable(data, 6, rng);
      const counts = Array(6).fill(0);
      const { emit, frames } = recorder(data.stream, active => counts.map((n, b) =>
        node("bucket-" + b, "B" + b + " · " + n, b % 3 * 2, n / 2, Math.floor(b / 3) * 2, b < keep ? 1 : 2, b === active, n)));
      for (const key of data.stream) {
        const b = hash(key);
        emit(1, "h(" + key + ") = " + b + ". Keep buckets 0 through " + (keep - 1) + ".", key, b);
        counts[b]++;
        emit(2, "Bucket " + b + (b < keep ? " < " + keep + " → keep" : " ≥ " + keep + " → skip") +
          " tag " + key + ". Retained " + total(counts.slice(0, keep)) + " of " + total(counts) + " sightings.", key, b);
      }
      emit(3, "Each tag had probability " + keep + "/6 of selection. Observed sighting fraction = " +
        total(counts.slice(0, keep)) + "/" + data.stream.length + ".");
      return frames;
    }
  });

  register({
    id: "reservoir-sampling", title: "Reservoir sampling", presets,
    description: "Draw a uniform sample of sightings as they arrive. One slot gives RS1, several give RSs, and independent copies can sample the same sighting.",
    params: [range("slots", "Slots in each reservoir", 1, 4, 2),
      choice("mode", "Reservoirs", ["One reservoir", "Three independent reservoirs"])],
    code: ["Allocate empty slots.", "Fill the next empty slot.",
      "Draw a slot number uniformly from 1 to the arrival number.", "Replace the numbered slot if it exists.",
      "Keep the current sample when the draw exceeds capacity.", "Compute each sighting’s inclusion probability."],
    trace(preset, { slots, mode }, rng) {
      const { stream } = arrivals(preset, rng);
      const copies = mode === "One reservoir" ? 1 : 3;
      const rows = list(copies, () => Array(slots).fill(null));
      const { emit, frames } = recorder(stream, active => rows.flatMap((row, r) => row.map((t, s) =>
        node(r + "-" + s, t ? "#" + t + " · " + stream[t - 1] : "Empty " + (s + 1), s * 2, t ? 1 : 0,
          r * 2, r + 1, active === r + "-" + s, t || 0))));
      stream.forEach((key, i) => rows.forEach((row, r) => {
        const t = i + 1;
        const slot = t <= slots ? t : 1 + draw(rng, t);
        const prefix = "Reservoir " + (r + 1) + ", sighting #" + t + " (tag " + key + "). ";
        const id = r + "-" + (slot - 1);
        if (t > slots) emit(2, prefix + "Draw from 1…" + t + " = " + slot + ".", key, id);
        if (slot <= slots) {
          const old = row[slot - 1];
          row[slot - 1] = t;
          emit(old ? 3 : 1, prefix + "Slot " + slot + " changes from " + (old ? "#" + old : "empty") + " to #" + t + ".", key, id);
        } else {
          emit(4, prefix + slot + " > " + slots + ". Keep the sample.", key);
        }
      }));
      emit(5, "Each sighting has probability " + Math.min(slots, stream.length) + "/" + stream.length +
        " of appearing in each reservoir. Slots identify sightings by arrival number.");
      return frames;
    }
  });

  for (const layout of ["Standard", "Partitioned", "Repeated"]) {
    const partitioned = layout === "Partitioned";
    const repeated = layout === "Repeated";
    register({
      id: layout.toLowerCase() + "-bloom-filter", title: layout + " Bloom filter", presets,
      description: {
        Standard: "Several hashes set bits in one shared array. A zero at any queried address proves the tag is absent.",
        Partitioned: "Each hash owns an equal slice of the bit array. A query checks one bit in each slice.",
        Repeated: "Insert each tag into independent copies. A membership query passes only when every copy accepts it."
      }[layout],
      params: [range("bits", "Bits per filter", 6, 18, 12, 6), hashes,
        ...(repeated ? [range("copies", "Independent filters", 2, 3, 2)] : []), query],
      code: ["Clear all bits.", "Hash the arriving tag and set the addressed bit. Repeat for every hash and filter.",
        "Look up the query tag and read each addressed bit.", "Combine the tested bits and compare with exact membership.",
        "For a fresh unseen tag, multiply the occupied fractions for its independent hash draws."],
      trace(preset, { bits, hashes, copies = 1, query }, rng) {
        const data = arrivals(preset, rng);
        const width = partitioned ? bits / hashes : bits;
        const bank = list(copies, () => Array(bits).fill(0));
        const functions = bank.map(() => list(hashes, () => hashTable(data, width, rng)));
        const { emit, frames } = recorder(data.stream, active => bank.flatMap((row, r) => row.map((v, b) => {
          const slice = partitioned ? Math.floor(b / width) : 0;
          const local = b - slice * width;
          const columns = Math.min(6, width);
          const layer = slice * Math.ceil(width / columns) + Math.floor(local / columns);
          return node(r + "-" + b, b + "·" + v, local % columns * 2, v, layer * 2 + r * (2 * Math.ceil(bits / 6) + 2),
            partitioned ? slice + 1 : r + 1, active === r + "-" + b, v);
        })));
        function probe(key, writing) {
          const readings = [];
          functions.forEach((row, r) => row.forEach((hash, h) => {
            const offset = partitioned ? h * width : 0;
            const b = offset + hash(key);
            const before = bank[r][b];
            if (writing) bank[r][b] = 1;
            readings.push(bank[r][b]);
            const address = partitioned ? offset + " + " + hash(key) + " = " + b : String(b);
            emit(writing ? 1 : 2, "Filter " + (r + 1) + ", hash " + (h + 1) + " of " + key + " → " + address +
              ". Bit " + b + (writing ? " changes " + before + " → 1." : " reads " + before + "."), key, r + "-" + b);
          }));
          return readings;
        }
        for (const key of data.stream) probe(key, true);
        const key = target(data, query);
        const readings = probe(key, false);
        const pass = readings.every(Boolean);
        const member = data.stream.includes(key);
        emit(3, "Tag " + key + " tests [" + readings.join(", ") + "] → " + (pass ? "possibly present" : "definitely absent") +
          ". Exact membership = " + (member ? "present" : "absent") + (pass && !member ? " (false positive)." : "."), key);
        const occupied = bank.flatMap(row => list(hashes, h =>
          partitioned ? total(row.slice(h * width, (h + 1) * width)) : total(row)));
        const probability = occupied.reduce((p, n) => p * (n / width), 1);
        emit(4, "Given these bits, a fresh unseen tag passes with probability " +
          occupied.map(n => n + "/" + width).join(" × ") + " ≈ " + (probability * 100).toFixed(2) + "%.", key);
        return frames;
      }
    });
  }

  register({
    id: "misra-gries", title: "Misra–Gries frequent items", presets,
    description: "Keep a short list of candidate tags. When every counter is occupied, cancel one sighting of each candidate together with the incoming sighting.",
    params: [range("capacity", "Available counters", 1, 4, 2), query],
    code: ["Start with empty counters.", "Increment the matching counter.", "Put the new tag in a free slot at one.",
      "For a new tag at capacity, decrement all counters and empty the zero slots.", "Bound the exact frequency using the cancellation count."],
    trace(preset, { capacity, query }, rng) {
      const data = arrivals(preset, rng);
      const slots = Array(capacity).fill(null);
      let cancellations = 0;
      const { emit, frames } = recorder(data.stream, active => slots.map((slot, i) => {
        const count = slot?.count || 0;
        return node("slot-" + i, slot ? slot.key + " ×" + count : "Empty", i * 2, count, 1, i + 1,
          active === i || active === "all", count);
      }));
      for (const key of data.stream) {
        const match = slots.findIndex(slot => slot?.key === key);
        const free = slots.indexOf(null);
        if (match >= 0) {
          const n = ++slots[match].count;
          emit(1, "Tag " + key + " has a counter. " + (n - 1) + " + 1 = " + n + ".", key, match);
        } else if (free >= 0) {
          slots[free] = { key, count: 1 };
          emit(2, "Tag " + key + " takes slot " + (free + 1) + " with count 1.", key, free);
        } else {
          const changes = slots.map((slot, i) => {
            const n = --slot.count;
            if (n === 0) slots[i] = null;
            return slot.key + " (" + (n + 1) + " → " + n + ")";
          });
          cancellations++;
          emit(3, "Cancel tag " + key + " with " + changes.join(", ") + ". Cancellation rounds = " + cancellations + ".", key, "all");
        }
      }
      const key = target(data, query);
      const estimate = slots.find(slot => slot?.key === key)?.count || 0;
      const sum = total(slots.map(s => s?.count || 0));
      emit(4, "Tag " + key + " has exact count " + data.stream.filter(x => x === key).length + ". Bounds = [" + estimate +
        ", " + (estimate + cancellations) + "] because (" + data.stream.length + " − " + sum + ") / " + (capacity + 1) + " = " + cancellations + ".", key);
      return frames;
    }
  });

  for (const signed of [false, true]) {
    register({
      id: signed ? "count-sketch" : "count-min-sketch", title: signed ? "Signed Count Sketch" : "Count-Min Sketch", presets,
      description: signed ? "Signed counters can move below zero. Undo the tag’s sign in each row and take the median to estimate its frequency." :
        "Hash each tag to one counter per row. Other tags can inflate those counters, so take the smallest reading.",
      params: [range("width", "Counters per row", 2, 6, 4), range("rows", "Hash rows", 1, 5, 3, signed ? 2 : 1), query],
      code: ["Start all row counters at zero.", signed ? "Add the tag’s row sign to its bucket." : "Add one to the tag’s bucket in every row.",
        signed ? "Multiply each looked-up counter by the query tag’s row sign." : "Read the query tag’s bucket in each row.",
        signed ? "Take the median row estimate and compare with the exact count." : "Take the minimum row estimate and compare with the exact count."],
      trace(preset, { width, rows, query }, rng) {
        const data = arrivals(preset, rng);
        const counters = list(rows, () => Array(width).fill(0));
        const buckets = list(rows, () => hashTable(data, width, rng));
        const signs = signed ? list(rows, () => hashTable(data, 2, rng)) : [];
        const sign = (r, key) => signed ? 2 * signs[r](key) - 1 : 1;
        const { emit, frames } = recorder(data.stream, active => counters.flatMap((row, r) => row.map((v, b) =>
          node(r + "-" + b, b + "·" + v, b * 2, v, r * 2, r + 1, active === r + "-" + b, v))));
        for (const key of data.stream) {
          counters.forEach((row, r) => {
            const b = buckets[r](key);
            const old = row[b];
            const delta = sign(r, key);
            row[b] += delta;
            emit(1, "Row " + (r + 1) + ", h(" + key + ") = " + b + ". " + old + (delta > 0 ? " + 1" : " − 1") + " = " + row[b] + ".", key, r + "-" + b);
          });
        }
        const key = target(data, query);
        const readings = counters.map((row, r) => {
          const b = buckets[r](key);
          const value = sign(r, key) * row[b] || 0;
          emit(2, "Row " + (r + 1) + ", h(" + key + ") = " + b + ". Read " +
            (signed ? sign(r, key) + " × " + row[b] + " = " : "") + value + ".", key, r + "-" + b);
          return value;
        });
        readings.sort((a, b) => a - b);
        const estimate = readings[signed ? Math.floor(rows / 2) : 0];
        const exact = data.stream.filter(x => x === key).length;
        emit(3, "Tag " + key + " → " + (signed ? "median" : "minimum") + " [" + readings.join(", ") + "] = " + estimate +
          ". Exact count = " + exact + ". Error = " + (estimate - exact) + "." + (signed ? "" :
            " Independent uniform rows give Pr(error ≥ 2 × " + data.stream.length + "/" + width + ") ≤ 1/" + (2 ** rows) + "."), key);
        return frames;
      }
    });
  }
})();
