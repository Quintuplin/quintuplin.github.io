(() => {
  "use strict";

  const register = spec => globalThis.Sims.register(spec);
  const topic = "Recommenders";
  const slider = (key, label, min, max, step, value) => ({ key, label, min, max, step, value });
  const choice = (key, label, options) => ({ key, label, options, value: options[0] });
  const sum = xs => xs.reduce((total, x) => total + x, 0);
  const mean = xs => sum(xs) / xs.length;
  const dot = (a, b) => sum(a.map((v, i) => v * b[i]));
  const norm = a => Math.sqrt(dot(a, a));
  const observed = row => row.filter(v => v !== null);
  const transpose = rows => rows[0].map((_, i) => rows.map(row => row[i]));
  const fmt = n => n === null ? "?" : String(+n.toFixed(4));
  const vec = xs => "[" + xs.map(fmt).join(", ") + "]";
  const node = (id, label, x, y, z, value, group, active = false) =>
    ({ id, label, x, y, z, value, group, active });
  const frame = (line, work, nodes) => ({ line, work, nodes });

  // Each deck describes a different pattern of tastes. Only observed cells vary.
  const users = ["Ada", "Bo", "Cy", "Dee"];
  const items = ["Ash", "Bay", "Elm", "Fir"];
  const decks = [
    { name: "Two taste camps", rows: [[4.7, 1.4, 4, null], [4.3, 1.6, 3.9, 4.6],
      [1.3, 4.6, 1.8, 1.5], [3, 2.2, null, 3.4]] },
    { name: "One generous rater", rows: [[2.7, 3.5, 2, null], [4.2, 4.8, 3.8, 4.4],
      [2.2, 3.9, 1.6, 3.1], [3.5, null, 2.8, 2.2]] },
    { name: "A divisive favourite", rows: [[3.1, 4.5, 2.2, null], [2.8, 4.7, 2.5, 1.5],
      [3.3, 4.2, 1.7, 4.8], [1.8, 2.7, null, 3.9]] }
  ];
  function ratings(rows, rng) {
    return rows.map(row => row.map(v => v === null ? null :
      Math.round((v + (rng() - 0.5) * 0.3) * 100) / 100));
  }
  function matrixNodes(rows, rowNames, colNames, activeRow = -1, activeCol = -1) {
    return rows.flatMap((row, r) => row.map((v, c) =>
      ({ ...node(`r${r}c${c}`, `${rowNames[r]}/${colNames[c]} ${fmt(v)}`,
        c * 3, v ?? 0, r * 3, v ?? 0, r, r === activeRow || c === activeCol), shape: "cell" })));
  }
  function matrixWork(rows, rowNames, colNames) {
    return `${colNames.join(" / ")}. ${rows.map((row, i) => rowNames[i] + " " + vec(row)).join(". ")}`;
  }
  function biasModel(rows) {
    const global = mean(observed(rows.flat()));
    const user = rows.map(row => mean(observed(row)) - global);
    const item = transpose(rows).map(col => mean(observed(col)) - global);
    return { global, user, item, at: (u, i) => global + user[u] + item[i] };
  }

  register({
    id: "content-profile", title: "Content ranking with TF-IDF", topic,
    description: "Turn tag counts into item profiles. Rank unread titles by their cosine similarity to a reader’s liked titles.",
    params: [slider("liked", "Liked titles in reading order", 1, 2, 1, 2)],
    presets: [
      { name: "Field guides", terms: ["fern", "trail", "bird"], titles: ["Moss", "Ridge", "Grove", "Wings", "Marsh"],
        counts: [[3, 1, 0], [0, 3, 1], [2, 1, 0], [0, 0, 3], [1, 0, 2]] },
      { name: "Studio shelves", terms: ["ink", "clay", "kiln"], titles: ["Slip", "Etch", "Glaze", "Print", "Fire"],
        counts: [[0, 3, 1], [3, 0, 0], [0, 2, 2], [2, 1, 0], [0, 1, 3]] },
      { name: "Harbour stories", terms: ["sail", "fog", "port"], titles: ["Gust", "Mist", "Dock", "Cape", "Haze"],
        counts: [[3, 0, 1], [0, 3, 1], [0, 1, 3], [2, 0, 1], [1, 2, 1]] }
    ],
    code: ["C[d,t] ← count(term[t], title[d])",
      "for t: idf[t] ← ln(N / count(d where C[d,t] > 0))",
      "for d: v[d] ← C[d,:] ⊙ idf",
      "reader ← sum(v[d] for d in liked) / count(liked)",
      "for d in unread: score[d] ← dot(reader, v[d]) / (‖reader‖ × ‖v[d]‖)",
      "return sort(unread, by = descending(score), tie = inputOrder)"],
    trace(p, { liked }, rng) {
      const counts = p.counts.map(row => row.map(v => v && 2 * v + Math.floor(3 * rng())));
      const frames = [frame(0, matrixWork(counts, p.titles, p.terms), matrixNodes(counts, p.titles, p.terms))];
      const idf = transpose(counts).map((col, j) => {
        const df = col.filter(Boolean).length;
        const value = Math.log(col.length / df);
        frames.push(frame(1, `${p.terms[j]} occurs in ${df} titles. ln(${col.length}/${df}) = ${fmt(value)}.`,
          matrixNodes(counts, p.titles, p.terms, -1, j)));
        return value;
      });
      const vectors = counts.map((row, i) => {
        const v = row.map((n, j) => n * idf[j]);
        frames.push(frame(2, `${p.titles[i]}: ${vec(row)} × ${vec(idf)} term by term = ${vec(v)}.`,
          matrixNodes([v], [p.titles[i]], p.terms).map((n, j) => ({ ...n, z: counts[i][j] }))));
        return v;
      });
      const profile = transpose(vectors.slice(0, liked)).map(mean);
      frames.push(frame(3, `Average ${p.titles.slice(0, liked).join(" and ")}: ${vec(profile)}.`,
        matrixNodes([...vectors.slice(0, liked), profile], [...p.titles.slice(0, liked), "Reader"], p.terms)));
      const scores = [];
      for (let i = liked; i < counts.length; i++) {
        const denominator = norm(profile) * norm(vectors[i]);
        const score = dot(profile, vectors[i]) / denominator;
        scores.push({ title: p.titles[i], score, i });
        frames.push(frame(4, `${p.titles[i]}: ${fmt(dot(profile, vectors[i]))} / (${fmt(norm(profile))} × ${fmt(norm(vectors[i]))}) = ${fmt(score)}.`,
          matrixNodes([profile, vectors[i]], ["Reader", p.titles[i]], p.terms)));
      }
      scores.sort((a, b) => b.score - a.score || a.i - b.i);
      frames.push(frame(5, scores.map((s, i) => `${i + 1}. ${s.title} ${fmt(s.score)}`).join(" · "),
        scores.map((s, i) => ({ ...node(s.title, s.title + " " + fmt(s.score), i * 2, s.score, norm(vectors[s.i]), s.score, i), shape: "bar" }))));
      return frames;
    }
  });

  const metric = choice("metric", "Neighbour similarity", ["Cosine", "Pearson"]);
  const neighbours = slider("k", "Neighbours by absolute similarity", 1, 3, 1, 2);
  function similarity(a, b, method) {
    let x, y;
    if (method === "Pearson") {
      const ma = mean(observed(a)), mb = mean(observed(b));
      const overlap = a.map((v, i) => v !== null && b[i] !== null);
      x = a.filter((_, i) => overlap[i]).map(v => v - ma);
      y = b.filter((_, i) => overlap[i]).map(v => v - mb);
    } else {
      x = a.map(v => v ?? 0);
      y = b.map(v => v ?? 0);
    }
    const denominator = norm(x) * norm(y);
    const weight = denominator ? dot(x, y) / denominator : 0;
    const calculation = denominator
      ? `${vec(x)} · ${vec(y)} / (${fmt(norm(x))} × ${fmt(norm(y))}) = ${fmt(weight)}`
      : "zero vector length gives weight 0";
    return { x, y, weight, calculation };
  }
  function neighbourSpec(id, title, byItem, residual) {
    const kind = byItem ? "items" : "users";
    const code = [byItem ? "V ← transpose(R); target ← Fir; column ← Ada" : "V ← R; target ← Ada; column ← Fir",
      residual ? "μ ← mean(observed(R)); B[u,i] ← mean(observed(R[u,:])) + mean(observed(R[:,i])) − μ"
        : "for j: m[j] ← mean(observed(V[j,:]))",
      "for j with V[j,column] known: a,b ← V[target], V[j]",
      "if Pearson: x,y ← overlap(a − meanKnown(a), b − meanKnown(b)); else: x,y ← zeroFill(a), zeroFill(b)",
      "lengthProduct ← ‖x‖ × ‖y‖; w[j] ← lengthProduct > 0 ? dot(x,y)/lengthProduct : 0",
      "N ← first(k, sort(eligible, by = descending(abs(w)), tie = inputOrder)); S,D ← 0,0",
      residual ? "for j in N: S += w[j] × (V[j,column] − B[j,column]); D += abs(w[j])"
        : "for j in N: S += w[j] × V[j,column]; D += abs(w[j])",
      "return D > 0 ? " + (residual ? "B[Ada,Fir] + " : "") + "S / D : baseline(Ada,Fir)"];
    register({ id, title, topic, description: residual
      ? "Estimate a usual rating from user and item biases. Correct it with the neighbours’ weighted surprises."
      : `Compare ${kind} to fill one missing rating. Inspect how common observations and negative similarities affect the estimate.`,
      params: [metric, neighbours], presets: decks, code,
      trace(p, { metric, k }, rng) {
        const rows = ratings(p.rows, rng);
        const model = biasModel(rows);
        const vectors = byItem ? transpose(rows) : rows;
        const names = byItem ? items : users;
        const target = byItem ? 3 : 0, column = byItem ? 0 : 3;
        const draw = (i = target) => byItem ? matrixNodes(rows, users, items, -1, i) : matrixNodes(rows, users, items, i);
        const frames = [frame(0, matrixWork(rows, users, items), draw())];
        frames.push(frame(1, residual
          ? `Global mean ${fmt(model.global)}. User offsets ${vec(model.user)}. Item offsets ${vec(model.item)}. Ada/Fir = ${fmt(model.global)} + (${fmt(model.user[0])}) + (${fmt(model.item[3])}) = ${fmt(model.at(0, 3))}.`
          : `All observed means: ${names.map((name, i) => name + " " + fmt(mean(observed(vectors[i])))).join(", ")}.`, draw()));
        const candidates = [];
        vectors.forEach((row, i) => {
          if (i === target || row[column] === null) return;
          frames.push(frame(2, `${names[target]} ${vec(vectors[target])}. ${names[i]} ${vec(row)}. ${names[i]} supplies ${fmt(row[column])}.`, draw(i)));
          const { x, y, weight, calculation } = similarity(vectors[target], row, metric);
          const prep = metric === "Pearson"
            ? `Subtract means ${fmt(mean(observed(vectors[target])))} and ${fmt(mean(observed(row)))} on their shared entries`
            : "Fill missing entries with zero";
          const dimensions = (byItem ? users : items).filter((_, j) =>
            metric === "Cosine" || (vectors[target][j] !== null && row[j] !== null));
          frames.push(frame(3, `${prep}: ${vec(x)} and ${vec(y)}.`,
            matrixNodes([x, y], [names[target], names[i]], dimensions)));
          candidates.push({ i, weight });
          frames.push(frame(4, `${metric} for ${names[target]} and ${names[i]}: ${calculation}.`, draw(i)));
        });
        const selected = candidates.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight) || a.i - b.i).slice(0, k);
        frames.push(frame(5, `Keep ${selected.map(c => names[c.i] + " (" + fmt(c.weight) + ")").join(", ")}.`, draw()));
        let numerator = 0, denominator = 0;
        selected.forEach(({ i, weight }) => {
          const value = vectors[i][column];
          const base = residual ? model.at(i, column) : 0;
          const previous = numerator;
          numerator += weight * (value - base);
          denominator += Math.abs(weight);
          frames.push(frame(6, `${names[i]}: ${fmt(previous)} + ${fmt(weight)} × (${fmt(value)}${residual ? " − " + fmt(base) : ""}) = ${fmt(numerator)}. Absolute weight total ${fmt(denominator)}.`, draw(i)));
        });
        const base = residual ? model.at(0, 3) : 0;
        const estimate = denominator ? base + numerator / denominator : model.at(0, 3);
        const filled = rows.map(row => [...row]);
        filled[0][3] = estimate;
        frames.push(frame(7, denominator
          ? `Ada/Fir = ${fmt(base)} + ${fmt(numerator)} / ${fmt(denominator)} = ${fmt(estimate)}.`
          : `No weight mass. Use the bias baseline ${fmt(estimate)}.`, matrixNodes(filled, users, items, 0, 3)));
        return frames;
      }
    });
  }
  neighbourSpec("user-collaborative-filtering", "User-based collaborative filtering", false, false);
  neighbourSpec("item-collaborative-filtering", "Item-based collaborative filtering", true, false);
  neighbourSpec("bias-residual", "Bias baseline and residual prediction", false, true);
const epochs = slider("epochs", "Training passes", 1, 6, 1, 2);
  register({
    id: "learned-interpolation", title: "Learning interpolation weights", topic,
    description: "Fit two neighbour weights to Ada’s observed ratings. Apply them to the neighbours’ residuals on Fir.",
    params: [choice("method", "Gradient update", ["Batch gradient descent", "Stochastic gradient descent"]),
      slider("rate", "Learning rate", 0.01, 0.2, 0.01, 0.08), epochs],
    presets: decks,
    code: ["B ← biasBaselines(observed(R)); w ← [0, 0]",
      "for j: x[j] ← [R[u,j] − B[u,j] for u in [Bo,Cy]]",
      "for epoch, j in trainingOrder: estimate ← B[Ada,j] + dot(w, x[j])",
      "g[j] ← (estimate − R[Ada,j]) × x[j]",
      "if SGD: w ← w − ηg[j]; else if last(j): w ← w − η mean(g)",
      "return B[Ada,Fir] + dot(w, x[Fir])"],
    trace(p, { method, rate, epochs }, rng) {
      const names = users.slice(0, 3);
      const rows = ratings(p.rows.slice(0, 3), rng);
      const model = biasModel(rows);
      const frames = [frame(0, matrixWork(rows, names, items), matrixNodes(rows, names, items))];
      const features = items.map((item, j) => {
        const pair = [1, 2].map(i => rows[i][j] - model.at(i, j));
        frames.push(frame(1, `${item}: Bo ${fmt(rows[1][j])} − ${fmt(model.at(1, j))}, Cy ${fmt(rows[2][j])} − ${fmt(model.at(2, j))}. Residuals ${vec(pair)}. Ada’s baseline ${fmt(model.at(0, j))}.`,
          matrixNodes(rows, names, items, -1, j)));
        return pair;
      });
      let weights = [0, 0];
      const batch = method === "Batch gradient descent";
      function draw(j) {
        return weights.map((w, i) => node(names[i + 1], `${names[i + 1]} w=${fmt(w)}`, i * 3, w, features[j][i], w, i, true));
      }
      function update(gradient, j) {
        const old = weights;
        weights = old.map((w, i) => w - rate * gradient[i]);
        frames.push(frame(4, `${vec(old)} − ${fmt(rate)} × ${vec(gradient)} = ${vec(weights)}.`, draw(j)));
      }
      for (let pass = 1; pass <= epochs; pass++) {
        const total = [0, 0];
        for (let j = 0; j < 3; j++) {
          const estimate = model.at(0, j) + dot(weights, features[j]);
          const error = estimate - rows[0][j];
          frames.push(frame(2, `Pass ${pass}, ${items[j]}: ${fmt(model.at(0, j))} + ${vec(weights)} · ${vec(features[j])} = ${fmt(estimate)}.`, draw(j)));
          const gradient = features[j].map(x => error * x);
          frames.push(frame(3, `(${fmt(estimate)} − ${fmt(rows[0][j])}) × ${vec(features[j])} = ${vec(gradient)}.`, draw(j)));
          if (batch) gradient.forEach((g, i) => { total[i] += g; });
          else update(gradient, j);
        }
        if (batch) update(total.map(g => g / 3), 2);
      }
      const estimate = model.at(0, 3) + dot(weights, features[3]);
      rows[0][3] = estimate;
      frames.push(frame(5, `Ada/Fir = ${fmt(model.at(0, 3))} + ${vec(weights)} · ${vec(features[3])} = ${fmt(estimate)}.`, matrixNodes(rows, names, items, 0, 3)));
      return frames;
    }
  });

  const latent = "Latent factors";
  register({
    id: "truncated-svd", title: "Truncated singular value decomposition", topic: latent,
    description: "Decompose a complete ratings table into rank-one patterns. Reconstruct the table and measure what the discarded pattern costs.",
    params: [slider("rank", "Singular components kept", 1, 2, 1, 1)],
    presets: [
      { name: "Parallel tastes", rows: [[1.4, 2.6, 4.5], [1.7, 2.8, 4.6]] },
      { name: "Crossed tastes", rows: [[4.6, 2.2, 1.3], [1.2, 2.7, 4.7]] },
      { name: "Shared favourite", rows: [[2.3, 4.5, 1.7], [1.4, 4.6, 3.4]] }
    ],
    code: ["R ← completeRatings(); A ← zeros(shape(R))", "G ← R Rᵀ; [[a,b],[b,d]] ← G",
      "σ ← sqrt((a + d ± hypot(a − d, 2b)) / 2)",
      "for f < rank: u ← unitEigenvector(G, σ[f]²); v ← Rᵀu / σ[f]",
      "A ← A + σ[f] u vᵀ", "return A, sqrt(mean((R − A)²))"],
    trace(p, { rank }, rng) {
      const rows = ratings(p.rows, rng);
      const names = users.slice(0, 2), titles = items.slice(0, 3);
      const draw = matrix => matrixNodes(matrix, names, titles);
      const frames = [frame(0, matrixWork(rows, names, titles), draw(rows))];
      const a = dot(rows[0], rows[0]), b = dot(rows[0], rows[1]), d = dot(rows[1], rows[1]);
      frames.push(frame(1, `G = [${fmt(a)}, ${fmt(b)}; ${fmt(b)}, ${fmt(d)}] from the four row dot products.`, matrixNodes([[a, b], [b, d]], names, names)));
      const gap = Math.hypot(a - d, 2 * b);
      const eigenvalues = [(a + d + gap) / 2, Math.max(0, (a + d - gap) / 2)];
      const angle = Math.atan2(2 * b, a - d) / 2;
      const left = [[Math.cos(angle), Math.sin(angle)], [-Math.sin(angle), Math.cos(angle)]];
      frames.push(frame(2, `λ = (${fmt(a + d)} ± ${fmt(gap)})/2 = ${vec(eigenvalues)}. σ = ${vec(eigenvalues.map(Math.sqrt))}.`, draw(rows)));
      const rebuilt = rows.map(row => row.map(() => 0));
      for (let f = 0; f < rank; f++) {
        const sigma = Math.sqrt(eigenvalues[f]), u = left[f];
        const v = transpose(rows).map(col => sigma ? dot(col, u) / sigma : 0);
        frames.push(frame(3, `Component ${f + 1}: u = ${vec(u)}. Rᵀu / ${fmt(sigma)} = ${vec(v)}.`,
          [...u, ...v].map((value, i) => node("factor" + i, (i < 2 ? names[i] : titles[i - 2]) + " " + fmt(value),
            i < 2 ? i * 2 : (i - 2) * 2, value, i < 2 ? 0 : 3, value, i < 2 ? 0 : 1))));
        rebuilt.forEach((row, i) => row.forEach((_, j) => { row[j] += sigma * u[i] * v[j]; }));
        frames.push(frame(4, `Add ${fmt(sigma)} × ${vec(u)} × ${vec(v)}ᵀ. ${matrixWork(rebuilt, names, titles)}.`, draw(rebuilt)));
      }
      const sse = sum(rows.flatMap((row, i) => row.map((r, j) => (r - rebuilt[i][j]) ** 2)));
      frames.push(frame(5, `All six cells: √(${fmt(sse)}/6) = ${fmt(Math.sqrt(sse / 6))}.`, draw(rebuilt)));
      return frames;
    }
  });

  register({
    id: "latent-factor-sgd", title: "Latent factors with stochastic gradient descent", topic: latent,
    description: "Learn one vector per user and item from observed ratings. Compare their dot products with and without learned bias offsets.",
    params: [slider("factors", "Factors per vector", 1, 3, 1, 2),
      slider("rate", "Learning rate", 0.01, 0.08, 0.01, 0.04),
      slider("penalty", "Shrinkage per observed rating", 0, 0.5, 0.05, 0.1),
      choice("bias", "Bias terms", ["Include biases", "Omit biases"]), epochs],
    presets: decks,
    code: ["Q,P ← randomFactors(k); bu,bi ← zeros(); μ ← bias ? mean(observed(R)) : 0",
      "for epoch, (u,i,r) in observedOrder: q,p ← Q[u],P[i]; estimate ← μ + bu[u] + bi[i] + q·p",
      "e ← r − estimate",
      "Q[u], P[i] ← q + 2η(e p − λq), p + 2η(e q − λp)",
      "if bias: for b in [bu[u], bi[i]]: b ← b + 2η(e − λb)",
      "if endOfPass: rmse ← sqrt(mean((r − predict(u,i))² for (u,i,r) observed))",
      "return μ + bu[Ada] + bi[Fir] + Q[Ada]·P[Fir]"],
    trace(p, { factors, rate, penalty, bias, epochs }, rng) {
      const rows = ratings(p.rows, rng);
      const enabled = bias === "Include biases";
      const base = enabled ? mean(observed(rows.flat())) : 0;
      const vector = () => Array.from({ length: factors }, () => 0.1 + 0.4 * rng());
      const q = users.map(vector), v = items.map(vector);
      const bu = users.map(() => 0), bi = items.map(() => 0);
      const predict = (u, i) => base + bu[u] + bi[i] + dot(q[u], v[i]);
      const frames = [frame(0, `${matrixWork(rows, users, items)}. Global term ${fmt(base)}. All offsets start at zero.`, matrixNodes(rows, users, items))];
      function draw(u, i) {
        return matrixNodes([q[u], v[i]], [users[u], items[i]], q[u].map((_, f) => "f" + (f + 1)));
      }
      const observations = rows.flatMap((row, u) => row.flatMap((r, i) => r === null ? [] : [{ u, i, r }]));
      for (let pass = 1; pass <= epochs; pass++) {
        for (const { u, i, r } of observations) {
          const oldUser = q[u], oldItem = v[i], estimate = predict(u, i);
          const error = r - estimate;
          frames.push(frame(1, `Pass ${pass}, ${users[u]}/${items[i]}: ${fmt(base + bu[u] + bi[i])} + ${vec(oldUser)} · ${vec(oldItem)} = ${fmt(estimate)}.`, draw(u, i)));
          frames.push(frame(2, `Error = ${fmt(r)} − ${fmt(estimate)} = ${fmt(error)}.`, draw(u, i)));
          const step = (x, other) => x + 2 * rate * (error * other - penalty * x);
          q[u] = oldUser.map((x, f) => step(x, oldItem[f]));
          v[i] = oldItem.map((x, f) => step(x, oldUser[f]));
          frames.push(frame(3, `η = ${fmt(rate)}, λ = ${fmt(penalty)}. ${users[u]}: ${vec(oldUser)} → ${vec(q[u])}. ${items[i]}: ${vec(oldItem)} → ${vec(v[i])}.`, draw(u, i)));
          if (enabled) {
            const old = [bu[u], bi[i]];
            bu[u] = step(bu[u], 1);
            bi[i] = step(bi[i], 1);
            frames.push(frame(4, `Offsets ${vec(old)} + 2 × ${fmt(rate)} × (error − ${fmt(penalty)} × old) = ${vec([bu[u], bi[i]])}.`, draw(u, i)));
          }
        }
        const sse = sum(observations.map(({ u, i, r }) => (r - predict(u, i)) ** 2));
        const fitted = rows.map((row, u) => row.map((r, i) => r === null ? null : predict(u, i)));
        frames.push(frame(5, `Pass ${pass} training RMSE = √(${fmt(sse)}/${observations.length}) = ${fmt(Math.sqrt(sse / observations.length))}.`, matrixNodes(fitted, users, items)));
      }
      const estimate = predict(0, 3);
      rows[0][3] = estimate;
      frames.push(frame(6, `Ada/Fir = ${fmt(base)} + (${fmt(bu[0])}) + (${fmt(bi[3])}) + ${vec(q[0])} · ${vec(v[3])} = ${fmt(estimate)}.`, matrixNodes(rows, users, items, 0, 3)));
      return frames;
    }
  });
const candidates = ["Ash", "Bay", "Elm", "Fir", "Ivy", "Oak"];
  register({
    id: "ranking-evaluation", title: "Precision, recall and ROC area", topic,
    description: "Evaluate a scored list against held-out likes. Sweep a score threshold through tied groups to draw the ROC curve.",
    params: [slider("k", "Recommended titles", 1, 6, 1, 3)],
    presets: [
      { name: "Mixed early hits", scores: [5, 4, 3, 2, 1, 0], liked: [1, 0, 1, 1, 0, 0] },
      { name: "Shared scores", scores: [4, 4, 3, 2, 2, 1], liked: [0, 1, 1, 0, 1, 0] },
      { name: "Late discoveries", scores: [1, 5, 2, 3, 0, 4], liked: [1, 0, 0, 0, 1, 0] }
    ],
    code: ["pairs ← zip(score, like); P ← sum(like); N ← count(like) − P",
      "ranked ← sort(pairs, by = descending(score), tie = inputOrder)",
      "hits ← sum(ranked[:k].like); precision ← hits/k; recall ← hits/P",
      "(x,y) ← (0,0); area ← 0",
      "for group in groupByScore(ranked): dx ← dislikes(group)/N; dy ← likes(group)/P; area += dx × (y + dy/2); (x,y) += (dx,dy)",
      "return precision, recall, area"],
    trace(p, { k }, rng) {
      const offsets = new Map();
      const entries = p.scores.map((s, i) => {
        if (!offsets.has(s)) offsets.set(s, (rng() - 0.5) * 1.5);
        return { i, score: Math.round((s + offsets.get(s)) * 100) / 100, like: p.liked[i] };
      });
      const draw = (order, take = 0) => order.map(({ i, score, like }, j) =>
        node(candidates[i], `${candidates[i]} ${fmt(score)}`, j * 2, score, like * 3, score, like, j < take));
      const frames = [frame(0, entries.map(({ i, score, like }) => `${candidates[i]} (${fmt(score)}, ${like})`).join(", "), draw(entries))];
      entries.sort((a, b) => b.score - a.score || a.i - b.i);
      frames.push(frame(1, `Top ${k}: ${entries.slice(0, k).map(e => candidates[e.i]).join(", ")}.`, draw(entries, k)));
      const positives = sum(p.liked), negatives = entries.length - positives;
      const hits = sum(entries.slice(0, k).map(e => e.like));
      frames.push(frame(2, `Precision@${k} = ${hits}/${k} = ${fmt(hits / k)}. Recall@${k} = ${hits}/${positives} = ${fmt(hits / positives)}.`, draw(entries, k)));
      const points = [[0, 0]];
      function rocFrame(line, work) {
        const nodes = points.map(([x, y], i) => node("p" + i, `(${fmt(x)}, ${fmt(y)})`, x, y,
          i / entries.length, y, 0, i === points.length - 1));
        const edges = nodes.slice(1).map((n, j) => ({ from: nodes[j].id, to: n.id, directed: true }));
        return { line, work, nodes, edges };
      }
      frames.push(rocFrame(3, `Above the largest score: FPR = 0/${negatives}, TPR = 0/${positives}.`));
      let tp = 0, fp = 0, area = 0;
      for (let j = 0; j < entries.length;) {
        const threshold = entries[j].score;
        const [x, y] = points[points.length - 1];
        do {
          tp += entries[j].like;
          fp += 1 - entries[j].like;
          j++;
        } while (j < entries.length && entries[j].score === threshold);
        const nextX = fp / negatives, nextY = tp / positives;
        const strip = (nextX - x) * (nextY + y) / 2;
        area += strip;
        points.push([nextX, nextY]);
        frames.push(rocFrame(4, `Score ≥ ${fmt(threshold)}: (${fp}/${negatives}, ${tp}/${positives}). Area added = (${fmt(nextX)} − ${fmt(x)}) × (${fmt(nextY)} + ${fmt(y)})/2 = ${fmt(strip)}.`));
      }
      frames.push(rocFrame(5, `ROC area = ${fmt(area)} over ${positives} × ${negatives} like/dislike pairs. A shared score earns half a win.`));
      return frames;
    }
  });

  register({
    id: "rating-rmse", title: "Root mean squared rating error", topic,
    description: "Compare predictions with held-out ratings on the same scale. Shift every prediction to see how calibration changes the error.",
    params: [slider("offset", "Prediction offset", -1, 1, 0.25, 0)],
    presets: [
      { name: "Consistent undershoot", actual: [4.2, 3.2, 2.4, 4.6], predicted: [3.4, 2.5, 1.7, 3.8] },
      { name: "One large miss", actual: [1.6, 4.2, 2.9, 3.8], predicted: [1.7, 1.4, 2.8, 4] },
      { name: "Balanced errors", actual: [2.2, 4.4, 3.3, 1.8], predicted: [2.8, 3.8, 3.9, 1.2] }
    ],
    code: ["actual, raw ← heldOutPairs(); SSE ← 0", "estimate ← raw + offset",
      "for i: SSE ← SSE + (estimate[i] − actual[i])²", "MSE ← SSE/count(actual); return sqrt(MSE)"],
    trace(p, { offset }, rng) {
      const [actual, raw] = ratings([p.actual, p.predicted], rng);
      const predicted = raw.map(v => v + offset);
      const labels = ["Actual", "Estimate"];
      const frames = [frame(0, matrixWork([actual, raw], labels, items), matrixNodes([actual, raw], labels, items)),
        frame(1, `${vec(raw)} + (${fmt(offset)}) per title = ${vec(predicted)}.`, matrixNodes([actual, predicted], labels, items))];
      let sse = 0;
      actual.forEach((rating, i) => {
        const squared = (predicted[i] - rating) ** 2;
        sse += squared;
        frames.push(frame(2, `${items[i]}: (${fmt(predicted[i])} − ${fmt(rating)})² = ${fmt(squared)}. Total = ${fmt(sse)}.`, matrixNodes([actual, predicted], labels, items, -1, i)));
      });
      const mse = sse / actual.length;
      frames.push(frame(3, `MSE = ${fmt(sse)}/${actual.length} = ${fmt(mse)}. RMSE = √${fmt(mse)} = ${fmt(Math.sqrt(mse))} rating points.`, matrixNodes([actual, predicted], labels, items)));
      return frames;
    }
  });
})();
