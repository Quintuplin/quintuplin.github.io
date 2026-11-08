(() => {
  'use strict';

  // The fourth coordinate is used only for the two-pair product code.
  const presets = [
    { name: 'Two tight clouds', points: [[2,3,2,4],[4,5,4,3],[3,2,6,5],[5,3,3,6],[11,12,10,11],[14,10,13,9],[12,14,14,13],[10,11,14,12]], query: [11,13,12,10] },
    { name: 'Rising staircase', points: [[1,3,2,2],[3,5,3,7],[5,6,5,3],[6,8,6,9],[8,9,9,5],[10,10,11,11],[12,12,13,8],[14,13,15,14]], query: [7,8,9,7] },
    { name: 'Fork around a gap', points: [[2,7,7,3],[4,6,8,6],[6,3,9,10],[9,2,11,14],[12,3,13,12],[6,10,6,4],[9,12,4,7],[13,13,3,9]], query: [11,10,5,10] }
  ];
  const number = (key, label, min, max, value) => ({ key, label, min, max, value, step: 1 });
  const choice = (key, label, options) => ({ key, label, options, value: options[0] });
  const kParam = number('k', 'Neighbours to return', 1, 5, 2);
  const fmt = x => String(Number(x.toFixed(3)));
  const tuple = v => '(' + v.map(fmt).join(', ') + ')';
  const sq = (a, b) => a.reduce((sum, x, i) => sum + (x - b[i]) ** 2, 0);
  const manhattan = (a, b) => a.reduce((sum, x, i) => sum + Math.abs(x - b[i]), 0);
  const byScore = (a, b) => a.score - b.score || a.i - b.i;
  const ranked = (ids, score) => Array.from(ids, i => ({ i, score: score(i) })).sort(byScore);
  const ids = rows => rows.map(row => row.i);
  const name = i => String.fromCharCode(65 + i);
  const names = indices => indices.map(name).join(', ') || 'none';
  const scores = rows => rows.map(({ i, score }) => name(i) + ' ' + fmt(score)).join(', ');
  const point = (id, v) => ({ id, label: id, x: v[0], y: v[1], z: v[2] });
  const edge = (from, to) => ({ from: name(from), to: name(to), directed: true });

  function sample(preset, rng, dimensions = 3) {
    const vary = v => v.slice(0, dimensions).map(x => x + Math.floor(rng() * 3) - 1);
    const points = preset.points.map(vary);
    const q = vary(preset.query);
    const all = points.map((_, i) => i);
    const nodes = points.map((v, i) => point(name(i), v));
    nodes.push(point('Q', q));
    return { points, q, all, nodes };
  }

  function notebook() {
    const frames = [];
    function add(line, work, nodes, active = [], edges = []) {
      frames.push(Object.freeze({
        line, work,
        nodes: Object.freeze(nodes.map(n => Object.freeze({ ...n, active: active.includes(n.id) }))),
        edges: Object.freeze(edges.map(e => Object.freeze({ ...e })))
      }));
    }
    return { frames, add };
  }

  function register(id, title, description, params, code, trace) {
    globalThis.Sims.register({
      id, title, topic: 'Nearest-neighbour search', description, params, presets, code,
      trace: (preset, controls, rng) => Object.freeze(trace(preset, controls, rng))
    });
  }

  register('exact-neighbours', 'Exact nearest-neighbour scan',
    'Measure every point against the query. Watch the nearest k change as each point arrives.',
    [choice('metric', 'Distance measure', ['Euclidean', 'Manhattan']), kParam], [
      'best ← []',
      'for p in points: d ← distance[metric](p, Q)',
      '    best ← sort(best ∪ {(d, p)}, by distance then name)[:k]',
      'return best'
    ], (preset, { metric, k }, rng) => {
      const { points, q, all, nodes } = sample(preset, rng);
      const { frames, add } = notebook();
      const best = [];
      add(0, 'Q = ' + tuple(q) + '. Keep ' + k + ' by ' + metric + ' distance.', nodes, ['Q']);
      for (const i of all) {
        const v = points[i];
        const differences = v.map((x, j) => Math.abs(x - q[j]));
        const l2 = metric === 'Euclidean';
        const score = l2 ? Math.sqrt(sq(v, q)) : manhattan(v, q);
        const sum = differences.map(d => fmt(d) + (l2 ? '²' : '')).join(' + ');
        add(1, name(i) + ' = ' + tuple(v) + '. Distance = ' + (l2 ? '√(' + sum + ')' : sum) + ' ≈ ' + fmt(score), nodes, [name(i), 'Q']);
        best.push({ i, score });
        best.sort(byScore).splice(k);
        add(2, 'Keep ' + scores(best), nodes, ids(best).map(name));
      }
      add(3, 'Nearest first: ' + scores(best), nodes, ids(best).map(name));
      return frames;
    });

  register('lsh-radius', 'Locality-sensitive hashing for a radius query',
    'When a point lies within the target radius, the search aims to find one within factor × radius. Random coordinate cuts form the bits. Match every bit in one table to become a candidate.',
    [number('bits', 'Cuts per table (AND)', 1, 5, 3), number('tables', 'Hash tables (OR)', 1, 5, 3),
      number('budget', 'Retrieved-entry limit (0 uses twice the table count)', 0, 10, 0), number('radius', 'Target Manhattan radius', 1, 10, 4),
      number('factor', 'Approximation factor', 1, 3, 2)], [
      'for t in 1..tables: cuts[t] ← sampleCuts(bits)',
      '    for p in points: index[t][bitTuple(p, cuts[t])].append(p)',
      'retrieved ← 0; limit ← budget or 2 × tables; for t in 1..tables: bucket ← index[t].get(bitTuple(Q, cuts[t]), [])',
      '    for p in bucket: retrieved += 1; stop if L1(Q,p) ≤ factor × radius or retrieved = limit',
      'return firstCheckedWithin(factor × radius) or MISS'
    ], (preset, { bits, tables, budget, radius, factor }, rng) => {
      const { points, q, all, nodes } = sample(preset, rng);
      const { frames, add } = notebook();
      const index = [];
      const hash = (v, cuts) => cuts.map(([axis, t]) => Number(v[axis] >= t)).join('');
      for (let t = 0; t < tables; t++) {
        // On the integer cube [0,16]^3 the collision probability is 1 - L1/48.
        const cuts = Array.from({ length: bits }, () => [Math.floor(rng() * 3), 1 + Math.floor(rng() * 16)]);
        const buckets = new Map();
        add(0, 'Table ' + (t + 1) + ' bits in order: ' + cuts.map(([a, v]) => 'xyz'[a] + ' ≥ ' + v).join(', '), nodes);
        const indexed = nodes.map(n => ({ ...n }));
        for (const i of all) {
          const key = hash(points[i], cuts);
          if (!buckets.has(key)) buckets.set(key, []);
          buckets.get(key).push(i);
          indexed[i].group = parseInt(key, 2);
          add(1, name(i) + ' ' + tuple(points[i]) + ' → ' + key + '. Bucket now holds ' + names(buckets.get(key)), indexed, [name(i)]);
        }
        index.push({ cuts, buckets });
      }
      const limit = budget || 2 * tables;
      let retrieved = 0;
      let answer;
      for (const [t, { cuts, buckets }] of index.entries()) {
        const key = hash(q, cuts);
        const matches = buckets.get(key) || [];
        add(2, 'Q ' + tuple(q) + ' → table ' + (t + 1) + ' bucket ' + key + ': ' + names(matches), nodes, matches.map(name));
        for (const i of matches) {
          retrieved++;
          const d = manhattan(q, points[i]);
          const ok = d <= radius * factor;
          add(3, 'Check ' + retrieved + '/' + limit + '. d(Q,' + name(i) + ') = ' + d + (ok ? ' ≤ ' : ' > ') + factor + ' × ' + radius, nodes, ['Q', name(i)]);
          if (ok) answer = i;
          if (ok || retrieved === limit) break;
        }
        if (answer !== undefined || retrieved === limit) break;
      }
      const result = answer !== undefined ? 'Return ' + name(answer) + ' within ' + radius * factor :
        'Search miss: ' + (retrieved === limit ? 'entry limit reached' : 'matching buckets exhausted');
      add(4, result + '. Checked ' + retrieved + ' retrieved entries.', nodes, answer === undefined ? [] : [name(answer)]);
      return frames;
    });

  const graphLinks = [[1,2],[0,3],[0,5],[1,4],[3,6],[2,7],[4,7],[5,6]];

  register('greedy-graph', 'Greedy graph search',
    'Expand the closest discovered point first. The expansion budget decides how far the search can travel from its entry point.',
    [choice('entry', 'Entry point', ['A','D','H']), number('expansions', 'Points to expand', 1, 8, 3), kParam], [
      'seen ← {entry}; frontier ← {(distance(Q, entry), entry)}',
      'repeat up to expansions while frontier ≠ ∅: p ← popMin(frontier)',
      '    for n in links[p] − seen: seen.add(n); frontier.push(distance(Q, n), n)',
      'return nearest(Q, seen)[:k]'
    ], (preset, { entry, expansions, k }, rng) => {
      const { points, q, nodes } = sample(preset, rng);
      const { frames, add } = notebook();
      const edges = graphLinks.flatMap((links, i) => links.filter(j => j > i).map(j => ({ from: name(i), to: name(j) })));
      const start = entry.charCodeAt(0) - 65;
      const distance = i => Math.sqrt(sq(points[i], q));
      const frontier = new Set([start]);
      const seen = new Set([start]);
      add(0, 'Q = ' + tuple(q) + '. Start at ' + entry + ' ' + tuple(points[start]) + ', distance ' + fmt(distance(start)), nodes, [entry], edges);
      for (let n = 1; n <= expansions && frontier.size; n++) {
        const order = ranked(frontier, distance);
        const i = order[0].i;
        frontier.delete(i);
        add(1, 'Expansion ' + n + '/' + expansions + '. Frontier: ' + scores(order) + '. Take ' + name(i), nodes, [name(i)], edges);
        for (const j of graphLinks[i]) {
          if (seen.has(j)) continue;
          seen.add(j);
          frontier.add(j);
          add(2, name(i) + ' → ' + name(j) + ' ' + tuple(points[j]) + '. Distance to Q ≈ ' + fmt(distance(j)), nodes, [name(i), name(j)], edges);
        }
      }
      const best = ranked(seen, distance).slice(0, k);
      add(3, 'Nearest among ' + seen.size + ' measured: ' + scores(best), nodes, ids(best).map(name), edges);
      return frames;
    });

  // Each layer keeps outgoing lists. Inserting a pair adds both directions.
  // Pruning removes only the outgoing link from the overflowing list.
  function searchLayer(layer, starts, distance, width, record) {
    const seen = new Set(starts);
    const frontier = new Set(starts);
    let best = ranked(starts, distance).slice(0, width);
    record(10, 'Initial frontier: ' + names(starts) + '. Retain up to ' + width + ': ' + scores(best), starts);
    while (frontier.size) {
      const next = ranked(frontier, distance)[0];
      frontier.delete(next.i);
      if (best.length === width && byScore(next, best[best.length - 1]) > 0) {
        record(11, 'Stop at ' + scores([next]) + ', ranked after the last retained point ' + scores(best.slice(-1)), [next.i]);
        break;
      }
      record(11, 'Expand ' + scores([next]) + '. Remaining frontier: ' + names([...frontier]), [next.i]);
      const fresh = layer.get(next.i).filter(i => !seen.has(i));
      record(12, 'Unseen links from ' + name(next.i) + ': ' + (scores(ranked(fresh, distance)) || 'none'), [next.i, ...fresh]);
      for (const i of fresh) {
        seen.add(i);
        const row = { i, score: distance(i) };
        if (best.length === width && byScore(row, best[best.length - 1]) >= 0) continue;
        frontier.add(i);
        best.push(row);
        best.sort(byScore).splice(width);
      }
      record(13, 'Keep ' + scores(best) + '. Frontier: ' + names([...frontier]), ids(best));
    }
    record(14, 'Layer result: ' + scores(best), ids(best));
    return ids(best);
  }

  register('hnsw', 'Hierarchical navigable small-world graph',
    'Insert points into nested graph layers, then route a query from the highest layer to the base. Each layer view shows the original three coordinates.',
    [number('degree', 'Outgoing links per layer', 2, 4, 2), number('width', 'Base query search width', 1, 8, 3)], [
      'layers[0..1] ← {A}; entry ← A; top ← 1',
      'for p in points[1:]: h ← cappedGeometric(0.5, 3); starts ← [entry]',
      '    for L from top down to h+1: starts ← searchLayer(p, starts, L, 1)',
      '    for L from min(h, top) down to 0: starts ← searchLayer(p, starts, L, 2 × linkLimit)',
      '        for n in starts[:linkLimit]: link(L, p, n); link(L, n, p)',
      '        for n in starts[:linkLimit]: links[L,n] ← nearest(n, links[L,n])[:linkLimit]',
      '    if h > top: layers[top+1..h] ← {p}; top ← h; entry ← p',
      'starts ← [entry]; for L from top down to 1: starts ← searchLayer(Q, starts, L, 1)',
      'best ← searchLayer(Q, starts, 0, width)',
      'return best[0]',
      'function searchLayer(t, S, L, w): F ← S; seen ← set(S); best ← nearest(t,S)[:w]',
      '    while F ≠ ∅: p ← popClosest(F,t); if full(best,w) and p ranks after last(best): break',
      '        new ← links[L,p] − seen; seen ← seen ∪ new',
      '        for n in new: if qualifies(n,best,w): F.add(n); best ← nearest(t,best ∪ {n})[:w]',
      '    return best'
    ], (preset, { degree, width }, rng) => {
      const { points, q, all, nodes } = sample(preset, rng);
      const { frames, add } = notebook();
      const layers = [new Map([[0, []]]), new Map([[0, []]])];
      let entry = 0;
      function show(line, level, work, active, target) {
        const layer = layers[level];
        const present = new Set([...layer.keys(), target]);
        const visible = nodes.filter((_, i) => present.has(i));
        const links = Array.from(layer, ([i, list]) => list.map(j => edge(i, j))).flat();
        add(line, 'Layer ' + level + '. ' + work, visible, active.map(name), links);
      }
      function search(line, level, starts, target, breadth) {
        const vector = target === points.length ? q : points[target];
        const distance = i => Math.sqrt(sq(vector, points[i]));
        show(line, level, 'Search from ' + names(starts) + ' toward ' + nodes[target].id + ' ' + tuple(vector) + ' with width ' + breadth, starts, target);
        return searchLayer(layers[level], starts, distance, breadth, (step, work, active) => show(step, level, work, active, target));
      }
      show(0, 1, 'Anchor A = ' + tuple(points[0]) + ' also belongs to layer 0.', [0], 0);
      for (const i of all.slice(1)) {
        let height = 0;
        while (height < 3 && rng() < 0.5) height++;
        const top = layers.length - 1;
        let starts = [entry];
        show(1, top, 'Insert ' + name(i) + ' = ' + tuple(points[i]) + ' up to layer ' + height + '. Entry ' + name(entry), [i], i);
        for (let level = top; level >= 0; level--) {
          if (level > height) {
            starts = search(2, level, starts, i, 1);
            continue;
          }
          starts = search(3, level, starts, i, 2 * degree);
          const layer = layers[level];
          const near = starts.slice(0, degree);
          layer.set(i, near);
          for (const j of near) layer.get(j).push(i);
          show(4, level, name(i) + ' ↔ ' + names(near) + '. Link limit ' + degree, [i, ...near], i);
          for (const j of near) {
            const links = layer.get(j);
            if (links.length <= degree) continue;
            const order = ranked(links, n => Math.sqrt(sq(points[j], points[n])));
            layer.set(j, ids(order.slice(0, degree)));
            show(5, level, 'From ' + name(j) + ': ' + scores(order) + '. Drop outgoing ' + names(ids(order.slice(degree))), [j], i);
          }
        }
        if (height > top) {
          for (let level = top + 1; level <= height; level++) layers.push(new Map([[i, []]]));
          entry = i;
          show(6, height, name(i) + ' becomes the highest entry at layer ' + height, [i], i);
        }
      }
      let starts = [entry];
      for (let level = layers.length - 1; level > 0; level--) starts = search(7, level, starts, points.length, 1);
      starts = search(8, 0, starts, points.length, width);
      show(9, 0, 'Q = ' + tuple(q) + '. Return ' + name(starts[0]) + ' at distance ' + fmt(Math.sqrt(sq(q, points[starts[0]]))), [starts[0]], points.length);
      return frames;
    });

  function nearest(v, centers) {
    const rows = centers.map((c, i) => ({ i, score: sq(v, c) }));
    return rows.sort(byScore)[0].i;
  }

  function mean(vectors) {
    return vectors[0].map((_, j) => vectors.reduce((sum, v) => sum + v[j], 0) / vectors.length);
  }

  // Farthest-first initialization followed by Lloyd assignment and update steps.
  function train(points, count, rounds, observe = () => {}) {
    const centers = [points[0].slice()];
    while (centers.length < count) {
      const gaps = points.map(v => Math.min(...centers.map(c => sq(v, c))));
      centers.push(points[gaps.indexOf(Math.max(...gaps))].slice());
    }
    observe('seed', centers);
    for (let t = 1; t <= rounds; t++) {
      const groups = points.map(v => nearest(v, centers));
      observe('assign', centers, groups, t);
      let moved = false;
      for (let j = 0; j < centers.length; j++) {
        const members = points.filter((_, i) => groups[i] === j);
        if (members.length) {
          const next = mean(members);
          if (sq(next, centers[j]) > 0) moved = true;
          centers[j] = next;
        }
        observe('update', centers, groups, t, j);
      }
      if (!moved) break;
    }
    return { centers, groups: points.map(v => nearest(v, centers)) };
  }

  const centerName = j => 'C' + (j + 1);
  function clusterView(points, centers, groups, q) {
    const nodes = [];
    points.forEach((v, i) => {
      if (centers.some(c => sq(v, c) === 0)) return;
      nodes.push({ ...point(name(i), v), group: groups?.[i] });
    });
    centers.forEach((v, j) => {
      const n = point(centerName(j), v);
      const same = points.flatMap((p, i) => sq(p, v) === 0 ? [name(i)] : []);
      n.label = [n.id, ...same].join('/');
      nodes.push({ ...n, group: j });
    });
    if (q) nodes.push(point('Q', q));
    return nodes;
  }
  const clusterLists = (groups, j) => groups.flatMap((g, i) => g === j ? [i] : []);
  const probeLists = (q, centers, count) => ids(ranked(centers.keys(), j => sq(q, centers[j])).slice(0, count));

  register('k-means-codebook', 'K-means coarse codebook training',
    'Train a small set of representatives for an inverted index. Each update moves one centre to the mean of its assigned points.',
    [number('count', 'Coarse centres', 2, 4, 3), number('rounds', 'Maximum training rounds', 1, 8, 5)], [
      'C ← [A]; while size(C) < count: C.append(argmax_p min_c squaredDistance(p, c))',
      'repeat until fixed or round limit: for p in points: group[p] ← argmin_j squaredDistance(p, C[j])',
      '    for j with members(j) ≠ ∅: C[j] ← mean(members(j))',
      'group ← assign(points, C); return C, group, Σ_p squaredDistance(p, C[group[p]])'
    ], (preset, { count, rounds }, rng) => {
      const { points } = sample(preset, rng);
      const { frames, add } = notebook();
      const { centers, groups } = train(points, count, rounds, (step, centers, groups, round, j) => {
        const view = clusterView(points, centers, groups);
        if (step === 'seed') {
          add(0, 'Initial centres: ' + centers.map((v, i) => centerName(i) + ' ' + tuple(v)).join(', '), view);
        } else if (step === 'assign') {
          for (const [i, v] of points.entries()) {
            const distances = centers.map(c => fmt(sq(v, c))).join(', ');
            add(1, 'Round ' + round + '. ' + name(i) + ' ' + tuple(v) + ' squared distances [' + distances + '] → ' + centerName(groups[i]),
              clusterView(points, centers, groups.slice(0, i + 1)), [name(i), centerName(groups[i])]);
          }
        } else {
          const members = clusterLists(groups, j);
          const sum = centers[j].map((_, axis) => members.reduce((total, i) => total + points[i][axis], 0));
          const work = members.length ? names(members) + ' sum to ' + tuple(sum) + '. Divide by ' + members.length : 'Empty list. Keep previous centre';
          add(2, work + ' → ' + centerName(j) + ' ≈ ' + tuple(centers[j]), view, [centerName(j)]);
        }
      });
      const loss = points.reduce((sum, v, i) => sum + sq(v, centers[groups[i]]), 0);
      add(3, 'Final squared error ≈ ' + fmt(loss) + '. Lists: ' + centers.map((_, j) => centerName(j) + ' [' + names(clusterLists(groups, j)) + ']').join(', '),
        clusterView(points, centers, groups));
      return frames;
    });

  register('inverted-file', 'Inverted file search',
    'Index points by their closest trained centre. Probe the nearest lists and measure the original vectors inside them.',
    [number('probes', 'Coarse lists to probe', 1, 3, 1), kParam], [
      'C ← kMeans(points, 3); best ← []',
      'for p in points: j ← nearestCentre(p, C); lists[j].append(p)',
      'open ← argsort_j distance(Q, C[j])[:probes]',
      'for j in open: for p in lists[j]: best ← smallestK(best ∪ {(distance(Q,p), p)})',
      'return best'
    ], (preset, { probes, k }, rng) => {
      const { points, all, q } = sample(preset, rng);
      const { frames, add } = notebook();
      const { centers, groups } = train(points, 3, 8);
      const view = clusterView(points, centers, groups, q);
      add(0, 'Trained centres: ' + centers.map((v, j) => centerName(j) + ' ' + tuple(v)).join(', '), clusterView(points, centers, [], q));
      for (const i of all) {
        const j = groups[i];
        add(1, name(i) + ' ' + tuple(points[i]) + ' → ' + centerName(j) + ', squared distance ' + fmt(sq(points[i], centers[j])),
          clusterView(points, centers, groups.slice(0, i + 1), q), [centerName(j)]);
      }
      const lists = probeLists(q, centers, probes);
      add(2, 'Q ' + tuple(q) + '. Open ' + lists.map(j => centerName(j) + ' at ' + fmt(Math.sqrt(sq(q, centers[j])))).join(', '), view, lists.map(centerName));
      const best = [];
      for (const j of lists) {
        for (const i of clusterLists(groups, j)) {
          const score = Math.sqrt(sq(points[i], q));
          best.push({ i, score });
          best.sort(byScore).splice(k);
          add(3, centerName(j) + ' → ' + name(i) + ', distance ≈ ' + fmt(score) + '. Keep ' + scores(best), view, [name(i), centerName(j)]);
        }
      }
      add(4, 'Nearest in ' + probes + ' lists: ' + scores(best),
        [...points.map((v, i) => ({ ...point(name(i), v), group: groups[i] })), point('Q', q)], ids(best).map(name));
      return frames;
    });

  register('product-quantization', 'Product quantization distance lookup',
    'Split four coordinates into two pairs and store one code per pair. Compare an uncompressed query to these codes by adding two lookup entries. The plot shows the first three coordinates.',
    [number('words', 'Codewords per coordinate pair', 2, 4, 3), number('probes', 'Coarse lists to probe', 1, 3, 3), kParam], [
      'for s in [1,2]: book[s] ← kMeans([pair(p,s) for p in points], words)',
      'for p in points: code[p] ← [nearestCentre(pair(p,s), book[s]) for s in [1,2]]',
      'for s in [1,2]: for j in 0..words−1: T[s,j] ← squaredDistance(pair(Q,s), book[s][j])',
      'lists ← buildIVF(points, 3); candidates ← probeNearestLists(Q, lists, probes)',
      'for p in candidates: (a,b) ← code[p]; score[p] ← T[1,a] + T[2,b]',
      'return argsort(score)[:k]'
    ], (preset, { words, probes, k }, rng) => {
      const { points, all, q, nodes } = sample(preset, rng, 4);
      const { frames, add } = notebook();
      const parts = v => [v.slice(0, 2), v.slice(2)];
      const books = [0, 1].map(s => train(points.map(v => parts(v)[s]), words, 8).centers);
      for (const [s, book] of books.entries()) {
        add(0, 'Book ' + (s + 1) + ': ' + book.map((v, code) => code + ' = ' + tuple(v)).join(', '), nodes);
      }
      const codes = points.map(v => parts(v).map((sub, s) => nearest(sub, books[s])));
      for (const i of all) {
        nodes[i].label = name(i) + '·' + codes[i].join('');
        add(1, name(i) + ' ' + parts(points[i]).map(tuple).join(' | ') + ' → codes [' + codes[i].join(', ') + ']', nodes, [name(i)]);
      }
      const tables = books.map((book, s) => book.map(v => sq(parts(q)[s], v)));
      const cells = [];
      for (const [s, row] of tables.entries()) {
        for (const [code, distance] of row.entries()) {
          const id = 'T' + (s + 1) + '[' + code + ']';
          cells.push({ id, label: id, x: code * 6, y: s * 6, z: Math.sqrt(distance), value: distance, group: s, shape: 'cell' });
          add(2, id + ' = squared distance from ' + tuple(parts(q)[s]) + ' to ' + tuple(books[s][code]) + ' ≈ ' + fmt(distance) + '. Depth shows distance.', cells, [id]);
        }
      }
      const { centers, groups } = train(points, 3, 8);
      const lists = probeLists(q, centers, probes);
      const candidates = lists.flatMap(j => clusterLists(groups, j));
      add(3, 'Q = ' + tuple(q) + '. Open ' + lists.map(j => centerName(j) + ' ' + tuple(centers[j]) + ' [' + names(clusterLists(groups, j)) + ']').join(', '), nodes, candidates.map(name));
      const rows = [];
      for (const i of candidates) {
        const [a, b] = codes[i];
        const first = tables[0][a];
        const second = tables[1][b];
        const score = first + second;
        rows.push({ i, score });
        add(4, name(i) + ' [' + a + ', ' + b + ']: ' + fmt(first) + ' + ' + fmt(second) + ' ≈ ' + fmt(score), nodes, [name(i)]);
      }
      const best = rows.sort(byScore).slice(0, k);
      add(5, 'Nearest by approximate squared distance: ' + scores(best), nodes, ids(best).map(name));
      return frames;
    });
})();
