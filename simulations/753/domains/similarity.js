(() => {
  'use strict';

  const range = (key, label, min, max, value) => ({ key, label, min, max, step: 1, value });
  const choice = (key, label, options) => ({ key, label, options, value: options[0] });
  const ints = n => Array.from({ length: n }, (_, i) => i);
  const draw = (rng, n) => Math.floor(rng() * n);
  const node = (id, label, x, y, z, group, active = false) =>
    ({ id, label: String(label), x, y, z, group, active });
  const register = spec => globalThis.Sims.register({ topic: 'Hashing and similarity', ...spec });
  const buckets = range('slots', 'Table slots', 2, 7, 4);
  const prime = 17;
  const keys = [
    { name: 'Shelf and bin', pairs: [[1, 2], [1, 4], [1, 6], [1, 8]] },
    { name: 'Diagonal tiles', pairs: [[2, 2], [4, 4], [6, 6], [8, 8]] },
    { name: 'Two aisles', pairs: [[2, 5], [4, 5], [2, 8], [4, 8]] },
  ];

  register({
    id: 'universal-hashing', title: 'Carter–Wegman universal hashing',
    description: 'Follow a key through a prime field into a table slot. Depth separates input, field residue and bucket.',
    params: [choice('kind', 'Key type', ['Two fields', 'Single number']), buckets], presets: keys,
    code: ['Choose field coefficients and translate the input keys.', 'Multiply each field by its coefficient and add the offset.',
      'Reduce the sum modulo the prime.', 'Reduce the residue modulo the table size.'],
    trace(preset, { kind, slots }, rng) {
      const shift = [draw(rng, prime), draw(rng, prime)];
      const single = kind === 'Single number';
      const a = single ? 1 + draw(rng, 16) : draw(rng, prime);
      const b = draw(rng, prime);
      const c = draw(rng, prime);
      const input = preset.pairs.map(([x, y], i) => single ? [(x + i + shift[0]) % prime]
        : [(x + shift[0]) % prime, (y + shift[1]) % prime]);
      const frames = [{ line: 0, work: `Keys ${input.map(v => '(' + v + ')').join(' ')}. Coefficients ${single ? a : [a, b]}, offset ${c}, prime 17.`,
        nodes: input.map((v, i) => node('k' + i, v.join(','), i, v[0], 0, 0)) }];
      const results = [];
      input.forEach((v, i) => {
        const sum = a * v[0] + (single ? 0 : b * v[1]) + c;
        const residue = sum % prime;
        const slot = residue % slots;
        const steps = [
          [`${a}×${v[0]}${single ? '' : ' + ' + b + '×' + v[1]} + ${c} = ${sum}`, sum],
          [`${sum} mod 17 = ${residue}`, residue],
          [`${residue} mod ${slots} = ${slot}`, slot],
        ];
        const stages = [node('key', '(' + v + ')', i, v[0] / 16, 0, 0)];
        steps.forEach(([work, value], j) => {
          const maximum = [single ? 272 : 528, 16, slots - 1][j];
          stages.push(node('s' + j, value, i, value / maximum, j + 1, j + 1));
          frames.push({ line: j + 1, work, nodes: [
            ...results.map(n => ({ ...n })),
            ...stages.map((n, k) => ({ ...n, active: k === j + 1 })),
          ] });
        });
        results.push(node('result' + i, '(' + v + ')→' + slot, i, slot / (slots - 1), 3, 3));
      });
      return frames;
    },
  });

  register({
    id: 'chained-dictionary', title: 'Chained hash dictionary',
    description: 'Insert keys, search a bucket and unlink a matching entry. Depth measures position in the chain.',
    params: [buckets, choice('query', 'Search and delete', ['Stored key', 'Missing key'])],
    presets: [
      { name: 'Even tickets', offsets: [0, 4, 2, 8] },
      { name: 'Adjacent lockers', offsets: [0, 1, 2, 3] },
      { name: 'Spaced crates', offsets: [0, 6, 3, 9] },
    ],
    code: ['Create empty chains.', 'Insert each new key at its bucket head.', 'Hash the query.',
      'Compare the next key.', 'Report membership.', 'Unlink the matching key if present.'],
    trace(preset, { slots, query }, rng) {
      const base = draw(rng, 31) + draw(rng, 31);
      const input = preset.offsets.map(x => x + base);
      const table = ints(slots).map(() => []);
      const frames = [];
      function emit(line, work, slot, key) {
        const nodes = [], edges = [];
        table.forEach((chain, s) => {
          let from = 'b' + s;
          nodes.push(node(from, '[' + s + ']', s, 0, 0, 0, s === slot));
          chain.forEach((v, j) => {
            const to = 'k' + v;
            nodes.push(node(to, v, s, 1, j + 1, 1, v === key));
            edges.push({ from, to, directed: true });
            from = to;
          });
        });
        frames.push({ line, work, nodes, edges });
      }
      emit(0, `Allocate ${slots} buckets for ${input.join(', ')}.`);
      for (const key of input) {
        const s = key % slots;
        table[s].unshift(key);
        emit(1, `${key} mod ${slots} = ${s}. Chain [${table[s]}].`, s, key);
      }
      const key = input[0] + (query === 'Missing key' ? slots * 10 : 0);
      const s = key % slots;
      emit(2, `Search for ${key} in bucket ${key} mod ${slots} = ${s}.`, s);
      let index = -1;
      for (const [j, v] of table[s].entries()) {
        emit(3, `${v} ${v === key ? '=' : '≠'} ${key}.`, s, v);
        if (v === key) { index = j; break; }
      }
      emit(4, `Contains ${key}? ${index >= 0 ? 'Yes' : 'No'}.`, s, key);
      if (index >= 0) table[s].splice(index, 1);
      emit(5, `${index >= 0 ? 'Remove' : 'No entry for'} ${key}. Chain [${table[s]}].`, s);
      return frames;
    },
  });

  register({
    id: 'shingling-jaccard', title: 'Character shingles and Jaccard similarity',
    description: 'Slide a window along each string. Each distinct shingle occupies one column, with a depth layer for each document.',
    params: [range('width', 'Characters per shingle', 1, 4, 2)],
    presets: [
      { name: 'Repeating motif', docs: ['ABABAC', 'ABABBC'] },
      { name: 'Reversed ending', docs: ['CABCDA', 'CABADC'] },
      { name: 'Different alphabets', docs: ['AABABB', 'CCDCDD'] },
    ],
    code: ['Read both strings.', 'Take the next window and insert it into the document set.',
      'Count shared and distinct shingles.', 'Divide intersection size by union size.'],
    trace(preset, { width }, rng) {
      const shift = (draw(rng, 26) + draw(rng, 26)) % 26;
      const docs = preset.docs.map(s => s.replace(/./g, ch => String.fromCharCode(65 + (ch.charCodeAt(0) - 65 + shift) % 26)));
      const repeat = draw(rng, docs[1].length);
      docs[1] = docs[1].slice(0, repeat + 1) + docs[1].slice(repeat);
      const sets = [new Set(), new Set()], union = new Set();
      function scene(current) {
        return [...union].flatMap((s, i) => sets.flatMap((set, d) => set.has(s)
          ? [node(d + s, s, i, Number(sets[1 - d].has(s)), d, d, s === current)] : []));
      }
      const frames = [{ line: 0, work: `A = ${docs[0]}, B = ${docs[1]}, window = ${width}.`,
        nodes: docs.map((s, d) => node('d' + d, s, d, 0, d, d)) }];
      docs.forEach((doc, d) => {
        for (let i = 0; i <= doc.length - width; i++) {
          const s = doc.slice(i, i + width), exists = sets[d].has(s);
          sets[d].add(s);
          union.add(s);
          frames.push({ line: 1, work: `${'AB'[d]}[${i}..${i + width - 1}] = ${s}. ${exists ? 'Repeat' : 'Insert'} → size ${sets[d].size}.`, nodes: scene(s) });
        }
      });
      const both = [...sets[0]].filter(s => sets[1].has(s));
      frames.push({ line: 2, work: `Intersection {${both}}. Union {${[...union]}}.`, nodes: scene() });
      frames.push({ line: 3, work: `Jaccard = ${both.length}/${union.size} ≈ ${(both.length / union.size).toFixed(3)}.`, nodes: scene() });
      return frames;
    },
  });

  const setPairs = [
    { name: 'One replacement', sets: [[0, 2, 3], [0, 2, 5]] },
    { name: 'Nested sets', sets: [[0, 1], [0, 1, 2, 4]] },
    { name: 'Disjoint sets', sets: [[1, 4], [2, 3, 6]] },
  ];
  const hashes = range('count', 'Signature rows', 1, 6, 3);
  function featureSets(preset, rng) {
    const shift = (draw(rng, 7) + draw(rng, 7)) % 7;
    return preset.sets.map(set => set.map(x => (x + shift) % 7));
  }
  const setWork = sets => `A = {${sets[0]}}, B = {${sets[1]}}.`;
  const show = x => Number.isFinite(x) ? x : '∞';
  const signatureScene = (sig, row, doc) => sig.flatMap((pair, i) => pair.map((v, d) =>
    ({ ...node(i + '-' + d, 'AB'[d] + (i + 1) + '=' + show(v), i, Number.isFinite(v) ? v : 7, d * 2, d,
      i === row && (doc === undefined || doc === d)), ...(Number.isFinite(v) ? { value: v } : {}) })));
  function agreement(frames, sig) {
    const matches = sig.filter(([a, b]) => a === b).length;
    frames.push({ line: 3, work: `Equal signature rows = ${matches}/${sig.length}. Estimated Jaccard = ${(matches / sig.length).toFixed(3)}.`,
      nodes: signatureScene(sig) });
    return frames;
  }

  register({
    id: 'minhash-permutation', title: 'MinHash by row permutation',
    description: 'Scan a shuffled feature order until each set records its first rank. Height shows the rank and depth identifies the set.',
    params: [hashes], presets: setPairs,
    code: ['Start two empty signatures.', 'Shuffle the feature rows.', 'Scan ranks, recording the first hit for each set.', 'Count equal ranks.'],
    trace(preset, { count }, rng) {
      const sets = featureSets(preset, rng);
      const sig = ints(count).map(() => [Infinity, Infinity]);
      const frames = [{ line: 0, work: setWork(sets), nodes: signatureScene(sig) }];
      sig.forEach((pair, i) => {
        const order = ints(7);
        for (let j = 6; j > 0; j--) {
          const k = draw(rng, j + 1);
          [order[j], order[k]] = [order[k], order[j]];
        }
        frames.push({ line: 1, work: `Permutation ${i + 1} visits [${order}]. Ranks start at 0.`, nodes: signatureScene(sig, i) });
        for (const [rank, x] of order.entries()) {
          sets.forEach((set, d) => { if (set.includes(x)) pair[d] = Math.min(pair[d], rank); });
          frames.push({ line: 2, work: `Rank ${rank}, feature ${x}. First ranks (A,B) = (${pair.map(show)}).`, nodes: signatureScene(sig, i) });
          if (pair.every(Number.isFinite)) break;
        }
      });
      return agreement(frames, sig);
    },
  });

  register({
    id: 'lsh-banding', title: 'LSH signature banding',
    description: 'Partition eight signature rows into equal bands. Depth separates bands, horizontal position identifies a row and height separates documents.',
    params: [choice('rows', 'Rows per band', ['2', '1', '4', '8'])],
    presets: [
      { name: 'Matching prefix', mask: '11110000' },
      { name: 'Alternating matches', mask: '10101010' },
      { name: 'Scattered gaps', mask: '11011101' },
    ],
    code: ['Partition the two signatures into bands.', 'Compare all rows of the current band.',
      'Add the pair if its full band matches.', 'Take the union of the candidate pairs.'],
    trace(preset, { rows }, rng) {
      const r = Number(rows);
      const offset = draw(rng, 8);
      const sig = ints(8).map(i => {
        const a = draw(rng, 7);
        return [a, preset.mask[(i + offset) % 8] === '1' ? a : (a + 1 + draw(rng, 6)) % 7];
      });
      const scene = band => sig.flatMap((pair, i) => pair.map((v, d) => node(i + '-' + d, v,
        i % r, d, Math.floor(i / r), d, Math.floor(i / r) === band)));
      const frames = [{ line: 0, work: `A = [${sig.map(p => p[0])}], B = [${sig.map(p => p[1])}]. 8/${r} = ${8 / r} bands.`, nodes: scene() }];
      const hits = [];
      for (let start = 0; start < 8; start += r) {
        const band = start / r, slice = sig.slice(start, start + r);
        const match = slice.every(([a, b]) => a === b);
        frames.push({ line: 1, work: `Band ${band + 1}: (${slice.map(p => p[0])}) ${match ? '=' : '≠'} (${slice.map(p => p[1])}).`, nodes: scene(band) });
        if (match) hits.push(band + 1);
        frames.push({ line: 2, work: `Band ${band + 1} emits ${match ? '(A,B)' : 'no pair'}. Matching bands = [${hits}].`, nodes: scene(band) });
      }
      frames.push({ line: 3, work: `${hits.length} matching bands. Candidate set = {${hits.length ? '(A,B)' : ''}}.`, nodes: scene() });
      return frames;
    },
  });

  register({
    id: 'lsh-amplification', title: 'AND/OR amplification and sensitivity',
    description: 'Tune independent MinHash tests for near and far pairs. Depth separates the base, AND and OR stages. Height gives the collision probability.',
    params: [range('k', 'Hashes that must all agree', 1, 6, 2), range('tables', 'Tables with any match', 1, 8, 3)],
    presets: [
      { name: 'Wide separation', near: 85, far: 15 },
      { name: 'Close thresholds', near: 65, far: 50 },
      { name: 'Similar documents', near: 90, far: 65 },
    ],
    code: ['Set the near and far Jaccard similarity thresholds.', 'AND: multiply independent collision probabilities.',
      'OR: subtract the probability every table misses from one.', 'Report near and far bounds at the distance thresholds.'],
    trace(preset, { k, tables }, rng) {
      const percent = [preset.near, preset.far].map(x => x + draw(rng, 5) - draw(rng, 5));
      const p = percent.map(x => x / 100);
      const and = p.map(x => x ** k);
      const or = and.map(x => 1 - (1 - x) ** tables);
      const nodes = [], frames = [];
      const names = ['near', 'far'];
      function emit(line, work) {
        frames.push({ line, work, nodes: nodes.map(n => ({ ...n, active: n.z === line })) });
      }
      p.forEach((v, d) => nodes.push(node('p' + d, names[d], d, v, 0, d)));
      emit(0, `MinHash collision bounds at the thresholds: near ≥ ${percent[0]}/100, far ≤ ${percent[1]}/100.`);
      and.forEach((v, d) => nodes.push(node('a' + d, v.toFixed(3), d, v, 1, d)));
      emit(1, and.map((v, d) => `${names[d]}: (${percent[d]}/100)^${k} ≈ ${v.toFixed(6)}`).join('. '));
      or.forEach((v, d) => nodes.push(node('o' + d, v.toFixed(3), d, v, 2, d)));
      emit(2, or.map((v, d) => `${names[d]}: 1 − (1 − (${percent[d]}/100)^${k})^${tables} ≈ ${v.toFixed(6)}`).join('. '));
      emit(3, `At distance ≤ ${(100 - percent[0]) / 100} use the near lower bound ≈ ${or[0].toFixed(6)}. At distance ≥ ${(100 - percent[1]) / 100} use the far upper bound ≈ ${or[1].toFixed(6)}.`);
      return frames;
    },
  });

  register({
    id: 'simhash', title: 'SimHash by random hyperplanes',
    description: 'Hash two three-dimensional vectors by their dot products with sampled integer plane normals. Compare the resulting sign bits.',
    params: [range('bits', 'Hyperplanes (bits)', 1, 8, 4)],
    presets: [
      { name: 'Aligned vectors', vectors: [[4, 2, 1], [4, 3, 1]] },
      { name: 'Opposing vectors', vectors: [[3, 2, 4], [-3, -2, -4]] },
      { name: 'Across axes', vectors: [[4, 0, 1], [0, 4, -1]] },
    ],
    code: ['Read the vector coordinates.', 'Sample a nonzero integer plane normal.',
      'Compute each dot product and take its sign bit (zero maps to one).', 'Count differing bits.'],
    trace(preset, { bits }, rng) {
      const scale = ints(3).map(() => 1 + draw(rng, 4));
      const vectors = preset.vectors.map(v => v.map((x, i) => x * scale[i]));
      const signatures = ['', ''];
      function scene(normal, active) {
        const points = [...vectors, ...(normal ? [normal] : [])];
        const labels = ['A', 'B', 'n'];
        return { nodes: [node('origin', '0', 0, 0, 0, 0), ...points.map((v, i) =>
          node(labels[i], labels[i], ...v, i + 1, i === active))],
          edges: points.map((_, i) => ({ from: 'origin', to: labels[i], directed: true, active: i === active })) };
      }
      const frames = [{ line: 0, work: `A = (${vectors[0]}), B = (${vectors[1]}).`, ...scene() }];
      for (let i = 0; i < bits; i++) {
        // Index the 5×5×5 lattice with the central zero vector removed.
        let index = draw(rng, 124);
        if (index >= 62) index++;
        const normal = [Math.floor(index / 25) - 2, Math.floor(index / 5) % 5 - 2, index % 5 - 2];
        frames.push({ line: 1, work: `Plane ${i + 1}: n = (${normal}), n·x = 0.`, ...scene(normal, 2) });
        vectors.forEach((v, d) => {
          const dot = v.reduce((sum, x, j) => sum + x * normal[j], 0);
          const bit = Number(dot >= 0);
          signatures[d] += bit;
          frames.push({ line: 2, work: `${'AB'[d]}·n = ${v.map((x, j) => '(' + x + '×' + normal[j] + ')').join(' + ')} = ${dot}. Bit = ${bit}; prefix ${signatures[d]}.`, ...scene(normal, d) });
        });
      }
      const distance = [...signatures[0]].filter((b, i) => b !== signatures[1][i]).length;
      frames.push({ line: 3, work: `Hamming distance(${signatures.join(', ')}) = ${distance}. Agreement = ${bits - distance}/${bits}.`, ...scene() });
      return frames;
    },
  });

  register({
    id: 'minhash-one-pass', title: 'One-pass MinHash',
    description: 'Visit each feature once and update signature minima with affine permutations modulo seven. Depth separates the two document columns.',
    params: [hashes], presets: setPairs,
    code: ['Initialise signature cells to infinity and choose affine hashes.', 'Read a feature and identify its sets.',
      'For each hash, minimise the cells of sets containing this feature.', 'Count equal minima.'],
    trace(preset, { count }, rng) {
      const sets = featureSets(preset, rng);
      const coeff = ints(count).map(() => [1 + draw(rng, 6), draw(rng, 7)]);
      const sig = ints(count).map(() => [Infinity, Infinity]);
      const frames = [{ line: 0, work: setWork(sets) + ` Hash coefficients (a,b): ${coeff.map(v => '(' + v + ')').join(' ')}.`, nodes: signatureScene(sig) }];
      for (const x of ints(7)) {
        const docs = [0, 1].filter(d => sets[d].includes(x));
        frames.push({ line: 1, work: `Feature ${x} belongs to ${docs.map(d => 'AB'[d]).join(' and ') || 'neither set'}.`, nodes: signatureScene(sig) });
        if (!docs.length) continue;
        coeff.forEach(([a, b], i) => {
          const h = (a * x + b) % 7;
          const updates = docs.map(d => {
            const old = sig[i][d];
            sig[i][d] = Math.min(old, h);
            return `${'AB'[d]} = min(${show(old)},${h}) = ${sig[i][d]}`;
          });
          frames.push({ line: 2, work: `h${i + 1}(${x}) = (${a}×${x}+${b}) mod 7 = ${h}. ${updates.join(', ')}.`, nodes: signatureScene(sig, i) });
        });
      }
      return agreement(frames, sig);
    },
  });
})();
