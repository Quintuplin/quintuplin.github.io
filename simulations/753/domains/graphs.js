(() => {
  "use strict";

  const id = i => String.fromCharCode(65 + i);
  const nfmt = x => String(Number(x.toFixed(5)));
  const list = xs => xs.map(nfmt).join(", ");
  const sum = xs => xs.reduce((a, b) => a + b, 0);
  const zeros = n => Array(n).fill(0);
  const indices = n => Array.from({ length: n }, (_, i) => i);
  const key = (a, b) => [Math.min(a, b), Math.max(a, b)].join("-");
  const slider = (key, label, min, max, step, value) => ({ key, label, min, max, step, value });
  const menu = (key, label, options) => ({ key, label, options, value: options[0] });
  const register = spec => globalThis.Sims.register({ topic: "Graphs", ...spec });

  // Each motif keeps its defining links. Seeded additions are actual input edges.
  const web = [
    { name: "Reading list with a dead end", links: "AB AC BD CB CD DA", extra: "BC AD CA DB", n: 5, fixed: "CE" },
    { name: "Index feeding a two-page trap", links: "AB BA BC CD DC", extra: "AC EB EA BE", n: 5, fixed: "AE", trap: [2, 3] },
    { name: "Two directories and an archive", links: "AB BC CA BD DE ED EF", extra: "AC AD BE CE DB", n: 6, fixed: "CB" }
  ];
  const networks = [
    { name: "Workshop rings", links: "AB BC CD DA DE EF FG GE", extra: "AC BD", n: 7 },
    { name: "Neighbourhood footpaths", links: "AB BC CA CD DE EF FG", extra: "DF EG", n: 7 },
    { name: "Relay junctions", links: "AB AC BD CD DE DF EG FG", extra: "BC EF", n: 7 }
  ];
  function parse(links) {
    return links.split(" ").map(pair => [...pair].map(letter => letter.charCodeAt(0) - 65));
  }
  function extraEdges(preset, rng) {
    return parse(preset.extra).filter(() => rng() < 0.5);
  }
  function graph(preset, rng, directed = false) {
    const edges = [...parse(preset.links), ...extraEdges(preset, rng)];
    if (directed) edges.push(...parse(preset.fixed));
    else edges.push([Math.floor(rng() * preset.n), preset.n]);
    return { n: preset.n + Number(!directed), edges, directed };
  }
  function neighbours(g) {
    const adj = indices(g.n).map(() => []);
    for (const [a, b] of g.edges) {
      adj[a].push(b);
      if (!g.directed) adj[b].push(a);
    }
    return adj;
  }
  function notebook(g) {
    const frames = [];
    function show(line, work, { values, groups, active = [], lit = [], depth } = {}) {
      const degrees = neighbours(g).map(ns => ns.length);
      const nodes = indices(g.n).map(i => {
        const angle = 2 * Math.PI * i / g.n;
        const value = values ? values[i] : degrees[i];
        return {
          id: id(i), label: id(i), x: Math.sin(angle), y: Math.cos(angle),
          z: depth ? depth[i] : degrees[i] / g.n,
          active: active.includes(i), group: groups?.[i] ?? 0,
          ...(value === undefined ? {} : { value })
        };
      });
      const links = g.edges.map(([a, b]) => ({
        from: id(a), to: id(b), directed: !!g.directed,
        active: lit.some(([u, v]) => (a === u && b === v) || (!g.directed && a === v && b === u))
      }));
      frames.push({ line, work, nodes, edges: links });
    }
    const pairs = g.edges.map(([a, b]) => id(a) + (g.directed ? "→" : "–") + id(b));
    show(0, `Input links (${g.edges.length}) = ${pairs.join(", ")}. Depth shows ${g.directed ? "out-degree" : "degree"}.`);
    return { frames, show };
  }

  const damping = slider("follow", "Probability of following a link", 0, 1, 0.05, 0.85);
  const rounds = slider("rounds", "Power iterations", 1, 30, 1, 8);
  const teleport = menu("restart", "Teleport destinations", ["A", "B", "A and B"]);
  function distribution(n, seeds) {
    return indices(n).map(i => seeds.includes(i) ? 1 / seeds.length : 0);
  }
  function rankStep(adj, rank, prior, beta) {
    const incoming = zeros(rank.length);
    let dangling = 0;
    adj.forEach((targets, i) => {
      if (!targets.length) dangling += rank[i];
      for (const j of targets) incoming[j] += beta * rank[i] / targets.length;
    });
    const restart = 1 - beta + beta * dangling;
    return { incoming, dangling, restart, next: incoming.map((v, i) => v + restart * prior[i]) };
  }
  const rankCode = [
    "out ← adjacencyLists(V, E)",
    "r ← uniform(V); p ← uniform(restartSet); receipts ← zeros(n)",
    "for i in V: for j in out[i]: receipts[j] += β * r[i] / |out[i]|",
    "restart ← 1 − β + β * sum(r[i] for i if out[i] is empty)",
    "r ← receipts + restart * p; receipts ← zeros(n); repeat for T rounds"
  ];
  for (const personal of [false, true]) {
    register({
      id: personal ? "personalised-pagerank" : "pagerank",
      title: personal ? "Personalised PageRank" : "PageRank",
      description: personal ? "Watch a chosen restart set change where a walk spends its time." :
        "At link probability 1, the walk follows every available link step without ordinary teleportation. Walks at dead ends still restart uniformly.",
      presets: web, params: personal ? [damping, rounds, teleport] : [damping, rounds], code: rankCode,
      trace(preset, params, rng) {
        const g = graph(preset, rng, true);
        const { frames, show } = notebook(g);
        const adj = neighbours(g);
        let rank = distribution(g.n, indices(g.n));
        const prior = personal ? distribution(g.n, params.restart.split(" and ").map(s => s === "A" ? 0 : 1)) : rank;
        show(1, `Start r = [${list(rank)}]. Teleport p = [${list(prior)}] in alphabetical order. Depth now tracks the mass at each page.`, { values: rank, depth: rank });
        for (let t = 1; t <= params.rounds; t++) {
          const { incoming, dangling, restart, next } = rankStep(adj, rank, prior, params.follow);
          if (t === 1) {
            adj.forEach((ns, i) => {
              const work = ns.length ? `${id(i)} sends ${params.follow} × ${nfmt(rank[i])} / ${ns.length} = ${nfmt(params.follow * rank[i] / ns.length)} to each of ${ns.map(id).join(", ")}.` :
                `${id(i)} has no out-links. Set aside its rank ${nfmt(rank[i])}.`;
              show(2, work, { values: rank, depth: rank, active: [i], lit: ns.map(j => [i, j]) });
            });
          }
          show(3, `Round ${t}. Link receipts = [${list(incoming)}]. Restart mass = 1 − ${params.follow} + ${params.follow} × ${nfmt(dangling)} = ${nfmt(restart)}.`,
            { values: incoming, depth: incoming });
          rank = next;
          const trapped = preset.trap ? ` C and D link only to one another. Their combined rank = ${nfmt(sum(preset.trap.map(i => rank[i])))}.` : "";
          show(4, `r[${t}] = receipts + ${nfmt(restart)} p = [${list(rank)}]. Sum = ${nfmt(sum(rank))}.` + trapped, { values: rank, depth: rank });
        }
        return frames;
      }
    });
  }

  function betweenness(g, roots, describe) {
    const adj = neighbours(g);
    const scores = new Map(g.edges.map(([a, b]) => [key(a, b), 0]));
    for (const root of roots) {
      const dist = Array(g.n).fill(-1);
      const paths = zeros(g.n);
      const parents = indices(g.n).map(() => []);
      const queue = [root];
      dist[root] = 0;
      paths[root] = 1;
      describe?.(1, `Root ${id(root)}. Start with one empty path at ${id(root)} and zero paths elsewhere. Depth tracks BFS distance (−1 until discovered).`,
        { active: [root], values: paths, depth: dist });
      for (const v of queue) {
        const updated = [];
        for (const w of adj[v]) {
          if (dist[w] < 0) {
            dist[w] = dist[v] + 1;
            queue.push(w);
          }
          if (dist[w] === dist[v] + 1) {
            parents[w].push(v);
            paths[w] += paths[v];
            updated.push([v, w]);
          }
        }
        const fromParents = parents[v].map(u => paths[u]).join(" + ") || "1";
        describe?.(2, `Root ${id(root)}. At distance ${dist[v]}, paths to ${id(v)} = ${fromParents} = ${paths[v]}. After visiting its neighbours the counts are [${paths.join(", ")}].`,
          { active: [v], values: paths, depth: dist, lit: updated });
      }
      const credit = Array(g.n).fill(1);
      for (const w of queue.reverse()) {
        for (const v of parents[w]) {
          const share = credit[w] * paths[v] / paths[w];
          credit[v] += share;
          const edge = key(v, w);
          scores.set(edge, scores.get(edge) + share);
          describe?.(3, `Root ${id(root)}. ${id(w)} returns ${nfmt(credit[w])} × ${paths[v]}/${paths[w]} = ${nfmt(share)} to ${id(v)}. Credit at ${id(v)} = ${nfmt(credit[v])}.`,
            { active: [v, w], values: credit, depth: dist, lit: [[v, w]] });
          describe?.(4, `Add ${nfmt(share)} to ${edgeName([v, w])}. Running edge credit = ${nfmt(scores.get(edge))}.`,
            { active: [v, w], values: credit, depth: dist, lit: [[v, w]] });
        }
      }
    }
    if (roots.length === g.n) {
      for (const [edge, total] of scores) scores.set(edge, total / 2);
    }
    return scores;
  }
  const edgeName = ([a, b]) => id(a) + "–" + id(b);
  const totals = (edges, scores) => edges.map(e => edgeName(e) + " " + nfmt(scores.get(key(...e)))).join(", ");
  register({
    id: "brandes", title: "Brandes edge betweenness",
    description: "Count shortest paths breadth first. Send credit back through their parents in reverse order.",
    presets: networks, params: [menu("roots", "Starting vertices", ["All vertices", "A only", "B only"])],
    code: ["adj ← undirectedAdjacency(V, E); score ← zeros(E)",
      "for root in roots: paths ← zeros(V); paths[root] ← 1; credit ← ones(V)",
      "    for v in BFS(root): for w in nextLayer(v): paths[w] += paths[v]",
      "    for w in reverse(BFS): for v in parents[w]: share ← credit[w]*paths[v]/paths[w]; credit[v] += share",
      "        score[v,w] += share",
      "return score / 2 if roots == V else score"],
    trace(preset, params, rng) {
      const g = graph(preset, rng);
      const { frames, show } = notebook(g);
      const all = params.roots === "All vertices";
      const scores = betweenness(g, all ? indices(g.n) : [params.roots === "A only" ? 0 : 1], show);
      show(5, `${all ? "All-root credits ÷ 2" : "Single-root credits"} = ${totals(g.edges, scores)}.`);
      return frames;
    }
  });

  function components(g) {
    const adj = neighbours(g);
    const groups = Array(g.n).fill(-1);
    let count = 0;
    for (let i = 0; i < g.n; i++) {
      if (groups[i] !== -1) continue;
      const queue = [i];
      groups[i] = count;
      for (const v of queue) {
        for (const w of adj[v]) {
          if (groups[w] !== -1) continue;
          groups[w] = count;
          queue.push(w);
        }
      }
      count++;
    }
    return groups;
  }
  function partition(groups) {
    return [...new Set(groups)].map(c => indices(groups.length).filter(i => groups[i] === c).map(id).join("")).join(" | ");
  }
  register({
    id: "girvan-newman", title: "Girvan–Newman community detection",
    description: "Remove one highest-betweenness edge and measure the remaining graph again. Ties follow input order.",
    presets: networks, params: [slider("count", "Stop at this many components", 2, 6, 1, 3)],
    code: ["G ← undirectedGraph(V, E); groups ← components(G)",
      "while count(groups) < target: score ← brandes(G, roots=V)",
      "    G.remove(firstArgmax(score)); groups ← components(G)"],
    trace(preset, params, rng) {
      const g = graph(preset, rng);
      const { frames, show } = notebook(g);
      let groups = components(g);
      while (new Set(groups).size < params.count) {
        const scores = betweenness(g, indices(g.n));
        const best = g.edges.reduce((a, b) => scores.get(key(...b)) > scores.get(key(...a)) + 1e-10 ? b : a);
        show(1, `Remaining edge scores = ${totals(g.edges, scores)}. Maximum = ${nfmt(scores.get(key(...best)))}.`,
          { groups, lit: [best], active: best });
        g.edges = g.edges.filter(e => e !== best);
        groups = components(g);
        show(2, `Remove ${edgeName(best)}. ${new Set(groups).size} component(s) = ${partition(groups)}.`, { groups, active: best });
      }
      return frames;
    }
  });

  function communities(g, groups, degrees) {
    const blocks = new Map();
    groups.forEach((c, i) => {
      if (!blocks.has(c)) blocks.set(c, { internal: 0, volume: 0 });
      blocks.get(c).volume += degrees[i];
    });
    const between = new Map();
    for (const [a, b] of g.edges) {
      if (groups[a] === groups[b]) blocks.get(groups[a]).internal++;
      else {
        const pair = key(groups[a], groups[b]);
        between.set(pair, (between.get(pair) ?? 0) + 1);
      }
    }
    const m = g.edges.length;
    const q = sum([...blocks.values()].map(b => b.internal / m - (b.volume / (2 * m)) ** 2));
    return { blocks, between, q };
  }
  register({
    id: "greedy-newman", title: "Greedy Newman modularity",
    description: "Start with one community per vertex and merge the pair with the greatest gain in modularity.",
    presets: networks, params: [menu("stop", "Stopping rule", ["Positive gains only", "Show full hierarchy"])],
    code: ["m ← |E|; degree ← countIncidentEdges(E)",
      "P ← singletons(V); Q(P) ← Σc (internal[c]/m − (volume[c]/(2m))²)",
      "ΔQ[a,b] ← links[a,b]/m − volume[a]*volume[b]/(2m²); (a,b) ← argmaxAdjacent(ΔQ)",
      "if fullHierarchy or ΔQ[a,b] > 0: merge(P,a,b); record(P,Q(P)); repeat",
      "return argmax(partitionsSeen, Q)"],
    trace(preset, params, rng) {
      const g = graph(preset, rng);
      const { frames, show } = notebook(g);
      const degrees = neighbours(g).map(ns => ns.length);
      let groups = indices(g.n);
      let state = communities(g, groups, degrees);
      let peak = state.q, bestGroups = groups;
      show(1, `m = ${g.edges.length}. Singleton volumes = [${degrees}]. Q = ${nfmt(state.q)}.`, { groups });
      while (state.between.size) {
        let gain = -Infinity, pair, formula;
        const m = g.edges.length;
        for (const [k, links] of state.between) {
          const [a, b] = k.split("-").map(Number);
          const v = state.blocks.get(a).volume, w = state.blocks.get(b).volume;
          const delta = links / m - v * w / (2 * m * m);
          if (delta > gain + 1e-12) {
            gain = delta;
            pair = [a, b];
            formula = `${links}/${m} − ${v} × ${w}/(2 × ${m}²)`;
          }
        }
        const [a, b] = pair;
        show(2, `Best pair led by ${id(a)} and ${id(b)}. ΔQ = ${formula} = ${nfmt(gain)}.`,
          { groups, active: indices(g.n).filter(i => pair.includes(groups[i])) });
        if (gain <= 1e-12 && params.stop === "Positive gains only") break;
        groups = groups.map(c => c === b ? a : c);
        state = communities(g, groups, degrees);
        show(3, `Merge to ${partition(groups)}. Q = ${nfmt(state.q)}.`, { groups });
        if (state.q > peak + 1e-12) {
          peak = state.q;
          bestGroups = groups;
        }
      }
      show(4, `Peak Q = ${nfmt(peak)} for ${partition(bestGroups)}.`, { groups: bestGroups });
      return frames;
    }
  });

  register({
    id: "graph-cuts", title: "Graph cuts",
    description: "Try every two-sided partition of a small graph and compare the cost under three objectives.",
    presets: networks, params: [menu("objective", "Cut objective", ["Minimum cut", "Ratio cut", "Normalized cut"])],
    code: ["degree ← countIncidentEdges(E)",
      "for S in nonemptySubsets(V ∖ {A}): T ← V ∖ S",
      "    c ← countEdges(S,T); cost[S] ← choose(c, c/|S| + c/|T|, c/vol(S) + c/vol(T))",
      "return argmin(cost), min(cost)"],
    trace(preset, params, rng) {
      const g = graph(preset, rng);
      const { frames, show } = notebook(g);
      const degrees = neighbours(g).map(ns => ns.length);
      const count = 2 ** (g.n - 1) - 1;
      let best = Infinity, winner, crossing;
      show(1, `With A fixed there are 2^${g.n - 1} − 1 = ${count} partitions. Degree sums use [${degrees}].`);
      for (let mask = 1; mask <= count; mask++) {
        const groups = indices(g.n).map(i => i === 0 ? 0 : (mask >> (i - 1)) & 1);
        const cut = g.edges.filter(([a, b]) => groups[a] !== groups[b]);
        const size = sum(groups);
        const volume = sum(groups.map((v, i) => v * degrees[i]));
        const [a, b] = params.objective === "Ratio cut" ? [g.n - size, size] : [2 * g.edges.length - volume, volume];
        const c = cut.length;
        const plain = params.objective === "Minimum cut";
        const cost = plain ? c : c / a + c / b;
        if (mask <= 4 || cost < best - 1e-12) {
          show(2, `Partition ${mask}, ${partition(groups)}. ${c} crossing links. ${params.objective} = ${plain ? c : `${c}/${a} + ${c}/${b} = ${nfmt(cost)}`}.`, { groups, lit: cut });
        }
        if (cost < best - 1e-12) {
          best = cost; winner = groups; crossing = cut;
        }
      }
      show(3, `Minimum of ${count} scores = ${nfmt(best)}. ${partition(winner)} cuts ${crossing.map(edgeName).join(", ")}.`, { groups: winner, lit: crossing });
      return frames;
    }
  });

  register({
    id: "clustering-coefficient", title: "Clustering coefficient",
    description: "Inspect every pair of neighbours around a vertex to see which possible triangles close.",
    presets: networks, params: [menu("focus", "Vertex to inspect", indices(8).map(id))],
    code: ["adj ← undirectedAdjacency(V, E)",
      "N ← adj[v]; possible ← |N|*(|N|−1)/2; closed ← 0",
      "for {a,b} in pairs(N): if b in adj[a]: closed += 1",
      "return closed / possible if possible > 0 else 0"],
    trace(preset, params, rng) {
      const g = graph(preset, rng);
      const { frames, show } = notebook(g);
      const adj = neighbours(g);
      const i = params.focus.charCodeAt(0) - 65;
      const ns = adj[i], possible = ns.length * (ns.length - 1) / 2;
      let closed = 0;
      show(1, `${id(i)} has neighbours ${ns.map(id).join(", ")}. Possible pairs = ${ns.length} × ${ns.length - 1} / 2 = ${possible}.`, { active: [i], lit: ns.map(v => [v, i]) });
      ns.forEach((a, j) => {
        for (const b of ns.slice(j + 1)) {
          const linked = adj[a].includes(b);
          if (linked) closed++;
          const lit = [[i, a], [i, b]];
          if (linked) lit.push([a, b]);
          show(2, `${id(a)} and ${id(b)} ${linked ? "share an edge" : "have no edge"}. Closed pairs so far = ${closed}.`, { active: [i, a, b], lit });
        }
      });
      const value = possible ? closed / possible : 0;
      show(3, `C(${id(i)}) = ${possible ? `${closed}/${possible} = ${nfmt(value)}` : "0 by the degree-below-two convention"}.`,
        { values: indices(g.n).map(v => v === i ? value : undefined), active: [i] });
      return frames;
    }
  });

  const farms = [
    { name: "Directory listings", links: "AB BC CA", extra: "AC BA CB", n: 3 },
    { name: "Review exchange", links: "AB BA BC CD DC DA", extra: "AC CA BD DB", n: 4 },
    { name: "Mirror catalogue", links: "AB BC CD DE EA CE", extra: "AC BE DA EC", n: 5 }
  ];
  function farm(preset, rng, count) {
    const target = preset.n;
    const entry = Math.floor(rng() * target);
    const edges = [...parse(preset.links), ...extraEdges(preset, rng), [entry, target]];
    for (let i = 1; i <= count; i++) edges.push([target, target + i], [target + i, target]);
    return { n: target + count + 1, edges, directed: true, target, entry };
  }
  const farmSize = slider("supporters", "Pages returning links to the target", 1, 5, 1, 3);
  const stableFollow = { ...damping, min: 0.5, max: 0.95 };
  for (const trust of [true, false]) {
    register({
      id: trust ? "trustrank" : "link-farm",
      title: trust ? "TrustRank and spam mass" : "Link farm",
      description: trust ? "Compare uniform PageRank with a walk that restarts on a trusted directory." :
        "Trace the feedback between a target and its supporting pages. Change the farm size to measure its effect.",
      params: trust ? [stableFollow, farmSize, { ...teleport, label: "Trusted restart pages" }] : [stableFollow, farmSize], presets: farms,
      code: ["out ← adjacencyLists(directoryLinks ∪ farmLinks)",
        trust ? "u ← uniform(V); p ← uniform(trustedSet); r,t ← u,u" : "u ← uniform(V); r ← u",
        trust ? "repeat r ← β*M*r+(1−β)*u; t ← β*M*t+(1−β)*p until maxChange < 10⁻¹¹" :
          "repeat r ← β*M*r + (1−β)*u until maxChange < 10⁻¹¹",
        trust ? "for i in V: spam[i] ← (r[i] − t[i]) / r[i]" : "x ← β*r[entry]/|out[entry]|; targetRank ← (x + (1−β)*(1+β*Mfarm)/n)/(1−β²)"],
      trace(preset, params, rng) {
        const g = farm(preset, rng, params.supporters);
        const { frames, show } = notebook(g);
        const adj = neighbours(g);
        const uniform = distribution(g.n, indices(g.n));
        const prior = trust ? distribution(g.n, params.restart.split(" and ").map(s => s === "A" ? 0 : 1)) : uniform;
        let rank = uniform, trusted = uniform;
        const beta = params.follow;
        const a = g.target;
        const groups = indices(g.n).map(i => i < a ? 0 : i === a ? 1 : 2);
        show(1, `Directory ${id(g.entry)} links to target ${id(a)}. Its ${params.supporters} supporters each link back. M splits each page’s rank equally over its out-links. Initial rank = 1/${g.n}.` +
          (trust ? ` Trusted restart pages = ${params.restart}.` : ""), { groups, values: rank, active: [a] });
        for (let t = 1; ; t++) {
          const ordinary = rankStep(adj, rank, uniform, beta);
          const biased = trust ? rankStep(adj, trusted, prior, beta) : ordinary;
          const delta = Math.max(...rank.map((v, i) => Math.abs(v - ordinary.next[i])), ...trusted.map((v, i) => Math.abs(v - biased.next[i])));
          rank = ordinary.next;
          trusted = biased.next;
          if (t <= 3 || t % 10 === 0 || delta < 1e-11) {
            show(2, `Round ${t}. ${id(a)} receives links ${nfmt(ordinary.incoming[a])} + teleport ${nfmt((1 - beta) / g.n)} = ${nfmt(rank[a])}.` +
              (trust ? ` Trusted walk gives ${nfmt(biased.incoming[a])} + 0 = ${nfmt(trusted[a])}.` : "") +
              ` Largest change = ${delta.toExponential(2)}.`, { groups, values: trust ? trusted : rank, depth: trust ? trusted : rank, active: [a] });
          }
          if (delta < 1e-11) break;
        }
        if (trust) {
          const mass = rank.map((r, i) => (r - trusted[i]) / r);
          mass.forEach((v, i) => show(3, `Spam mass at ${id(i)} = (${nfmt(rank[i])} − ${nfmt(trusted[i])}) / ${nfmt(rank[i])} = ${nfmt(v)}.`,
            { groups, values: mass, depth: mass, active: [i] }));
        } else {
          const x = beta * rank[g.entry] / adj[g.entry].length;
          const jump = (1 - beta) / g.n;
          show(3, `Outside inflow x = ${nfmt(x)}. Each page gets teleport t = ${nfmt(jump)}. Target = (x + t × (1 + ${beta} × ${params.supporters})) / (1 − ${beta}²) = ${nfmt(rank[a])}.`,
            { groups, values: rank, depth: rank, active: [a] });
        }
        return frames;
      }
    });
  }

  // Orthogonal Jacobi rotations diagonalise the small symmetric Laplacian.
  function eigenpairs(matrix) {
    const n = matrix.length;
    const d = matrix.map(row => [...row]);
    const vectors = indices(n).map(i => indices(n).map(j => Number(i === j)));
    for (;;) {
      let p = 0, q = 1;
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          if (Math.abs(d[i][j]) > Math.abs(d[p][q])) [p, q] = [i, j];
        }
      }
      if (Math.abs(d[p][q]) < 1e-12) break;
      const angle = Math.atan2(2 * d[p][q], d[q][q] - d[p][p]) / 2;
      const c = Math.cos(angle), s = Math.sin(angle);
      const pp = d[p][p], qq = d[q][q], pq = d[p][q];
      d[p][p] = c*c*pp - 2*c*s*pq + s*s*qq;
      d[q][q] = s*s*pp + 2*c*s*pq + c*c*qq;
      d[p][q] = d[q][p] = 0;
      for (let i = 0; i < n; i++) {
        if (i !== p && i !== q) {
          const ip = d[i][p], iq = d[i][q];
          d[i][p] = d[p][i] = c*ip - s*iq;
          d[i][q] = d[q][i] = s*ip + c*iq;
        }
        const vp = vectors[i][p], vq = vectors[i][q];
        vectors[i][p] = c*vp - s*vq;
        vectors[i][q] = s*vp + c*vq;
      }
    }
    return indices(n).map(j => ({ lambda: d[j][j], vector: vectors.map(row => row[j]) })).sort((a, b) => a.lambda - b.lambda);
  }
  const squaredDistance = (a, b) => sum(a.map((v, i) => (v - b[i]) ** 2));
  function clusterRows(rows, k, show) {
    const n = rows.length;
    const seeds = [0];
    while (seeds.length < k) {
      const distances = rows.map(r => Math.min(...seeds.map(i => squaredDistance(r, rows[i]))));
      const candidates = indices(n).filter(i => !seeds.includes(i));
      seeds.push(candidates.reduce((a, b) => distances[b] > distances[a] ? b : a));
    }
    let centres = seeds.map(i => rows[i]);
    const depth = rows.map(row => row[1]);
    show(3, `Initial row centres (farthest first) = ${seeds.map(id).join(", ")}.`, { active: seeds, depth });
    let previous = [];
    for (let t = 1; ; t++) {
      const distances = rows.map(row => centres.map(c => squaredDistance(row, c)));
      const groups = distances.map(ds => ds.indexOf(Math.min(...ds)));
      // An empty cell takes the worst-fit point from a cell with more than one member.
      for (const c of indices(k)) {
        if (groups.includes(c)) continue;
        const donors = indices(n).filter(i => groups.filter(v => v === groups[i]).length > 1);
        const worst = donors.reduce((a, b) => distances[b][groups[b]] > distances[a][groups[a]] ? b : a);
        groups[worst] = c;
      }
      const errors = rows.map((r, i) => squaredDistance(r, centres[groups[i]]));
      show(4, `Round ${t}. Squared distances from A = [${list(distances[0])}]. Assignments = ${partition(groups)}. Sum of squared distances = ${nfmt(sum(errors))}.`,
        { groups, values: errors, depth });
      if (groups.every((v, i) => v === previous[i])) return;
      centres = indices(k).map(c => {
        const members = rows.filter((_, i) => groups[i] === c);
        return indices(k).map(j => sum(members.map(r => r[j])) / members.length);
      });
      show(5, `Mean of rows in each cluster = ${centres.map(c => "[" + list(c) + "]").join(", ")}.`, { groups, depth });
      previous = groups;
    }
  }
  for (const kway of [false, true]) {
    register({
      id: kway ? "spectral-k-means" : "fiedler-partition",
      title: kway ? "Spectral clustering with k-means" : "Fiedler spectral partition",
      description: kway ? "Embed each vertex in the lowest Laplacian eigenvectors and run k-means on those rows." :
        "Use the second-smallest Laplacian eigenvector to split connected vertices into two groups.",
      presets: networks, params: kway ? [slider("k", "Number of clusters", 2, 4, 1, 3)] :
        [menu("split", "Partition rule", ["Sign of the Fiedler vector", "Equal halves by sorted value"])],
      code: ["W ← adjacencyMatrix(V,E)",
        "for i in V: L[i,:] ← degree[i]*unit(i) − W[i,:]",
        kway ? "λ,U ← symmetricEigenpairs(L, ascending); rows ← U[:,1..k]" :
          "λ,U ← symmetricEigenpairs(L, ascending); v ← U[:,2]; check L*v ≈ λ[2]*v",
        ...(kway ? ["centres ← farthestFirst(rows,k)",
          "group[i] ← argmin(c, ‖rows[i]−centres[c]‖²); if unchanged: return group",
          "for c in clusters: centres[c] ← mean(rows[group == c]); repeat"] :
          ["v ← U[:,2]; group[i] ← (v[i] > 0) if signRule else inUpperHalf(v,i)"])],
      trace(preset, params, rng) {
        const g = graph(preset, rng);
        const { frames, show } = notebook(g);
        const adj = neighbours(g);
        const lap = adj.map((ns, i) => indices(g.n).map(j => i === j ? ns.length : -Number(ns.includes(j))));
        lap.forEach((row, i) => show(1, `L row ${id(i)} = [${row}]. Degree ${adj[i].length} on the diagonal.`,
          { values: row, active: [i], lit: adj[i].map(j => [i, j]) }));
        const pairs = eigenpairs(lap);
        const v = pairs[1].vector;
        show(2, `Eigenvalues = [${list(pairs.map(p => p.lambda))}]. Fiedler coordinates = [${list(v)}]. Depth now shows the Fiedler coordinate.`,
          { values: v, depth: v });
        if (kway) {
          const rows = indices(g.n).map(i => pairs.slice(0, params.k).map(p => p.vector[i]));
          rows.forEach((r, i) => show(2, `Embedding row ${id(i)} = [${list(r)}] from the first ${params.k} eigenvectors.`, { values: v, depth: v, active: [i] }));
          clusterRows(rows, params.k, show);
        } else {
          const order = indices(g.n).sort((a, b) => v[a] - v[b]);
          const bySign = params.split === "Sign of the Fiedler vector";
          const groups = v.map((x, i) => Number(bySign ? x > 1e-10 : order.indexOf(i) >= g.n / 2));
          const rowProduct = sum(lap[0].map((x, j) => x * v[j]));
          show(2, `Check A. (Lv) at A = ${nfmt(rowProduct)} = λ₂ × v[A] = ${nfmt(pairs[1].lambda)} × ${nfmt(v[0])}.`, { values: v, depth: v, active: [0] });
          show(3, `${bySign ? "Positive coordinates versus zero or negative" : "Split the sorted coordinates halfway"}. Partition = ${partition(groups)}.`, { values: v, depth: v, groups });
        }
        return frames;
      }
    });
  }
})();
