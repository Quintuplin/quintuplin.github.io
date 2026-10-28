// Maths parity and explorer behaviour checks for the Deep Nested LSH page (#31). Usage: node check_deep_nested_lsh.mjs <page>
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const PAGE = process.argv[2];
if (!PAGE) throw new Error("usage: node check_deep_nested_lsh.mjs <page>");

const PageScripts = {
  html: readFileSync(PAGE, "utf8"),
  // The body of the script tag with this id.
  read(id) {
    const m = this.html.match(new RegExp(`<script[^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)</script>`));
    if (!m) throw new Error(`${PAGE} has no script with id ${id}`);
    return m[1];
  },
  // The page with script bodies removed, so ids and classes named in code do not count.
  markup() { return this.html.replace(/(<script[^>]*>)[\s\S]*?<\/script>/g, "$1"); },
  markupIds() { return new Set([...this.markup().matchAll(/\bid="([^"]+)"/g)].map((m) => m[1])); },
  hasClass(c) { return [...this.markup().matchAll(/\bclass="([^"]+)"/g)].some((m) => m[1].split(/\s+/).includes(c)); },
};

vm.runInThisContext(PageScripts.read("cascade-src"), { filename: "cascade-src" });
const C = globalThis.Cascade;
const study = JSON.parse(PageScripts.read("sim-data"));
const parity = JSON.parse(readFileSync(new URL("fixtures/deep-nested-lsh-parity.json", import.meta.url), "utf8"));
const MAX_DEPTH = study.provenance.grid.max_depth, PAIRS = study.facts.corpus?.pairs;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const counts = (d, t) => C.expectedCounts((s) => C.curve(s, d), PAIRS, t);
const tablesOf = (...kinds) => Object.values(study.tables).filter((t) => kinds.includes(t.kind));

// Measured errors over the seed draws of the table tree with these dims at t, or null when the study ran none.
function measuredFor(d, t) {
  const seeds = tablesOf("seed_spread").flatMap((s) => s.rows);
  for (const table of tablesOf("cascade", "equal_rows").filter((x) => x.target === t)) {
    for (const r of table.rows.filter((x) => same(x.dims, d))) {
      const seed = seeds.find((x) => x.target === t && x.config === r.config);
      if (seed) return C.spread(seed["errors by draw"]);
    }
  }
  return null;
}

// ---- TableCheck: every printed table value the maths can reproduce ----
const EXPECTED = ["E[FP]", "E[FN]", "E[errors]", "E[retrieved]"];
const CHECKS = {
  cascade: ["rows", "threshold", "width", "fp_exp x fn_exp", ...EXPECTED],
  equal_rows: ["rows", "threshold", "width", "fp_exp x fn_exp", ...EXPECTED],
  high_cap_family: ["rows", "threshold", "width", "fp_exp x fn_exp"],
  error_area: ["rows", "threshold", "width", "error_area"],
  algorithm: ["rows", "fp_exp", "fn_exp"],
};

function computed(field, d, target) {
  switch (field) {
    case "rows": return C.rows(d);
    case "threshold": return C.threshold(d);
    case "width": return C.width(d);
    case "error_area": return C.errorArea(d, target);
    case "fp_exp": return C.tails(d)[0];
    case "fn_exp": return C.tails(d)[1];
    case "fp_exp x fn_exp": return C.tails(d);
    case "E[FP]": return counts(d, target).fp;
    case "E[FN]": return counts(d, target).fn;
    case "E[errors]": return counts(d, target).errors;
    // A query probes the banding (d0, f-), so its candidates are the retrieved volume.
    case "E[retrieved]": return counts([d[0], C.tails(d)[1]], target).candidates;
  }
}

// Compared at the precision the table prints. E[retrieved] prints as a rounded whole number.
const agrees = (printed, value, dec) => (Array.isArray(printed) || dec === undefined
  ? JSON.stringify(printed) === JSON.stringify(value)
  : Math.abs(value - printed) <= 0.5 * Math.pow(10, -dec) + 1e-9);

function tableChecks(tables) {
  const out = [];
  const seeds = Object.values(tables).filter((t) => t.kind === "seed_spread").flatMap((t) => t.rows);
  const push = (stem, t, d, field, printed, value, dec = t.decimals[field]) =>
    out.push({ table: stem, kind: t.kind, dims: d, field, printed, computed: value, ok: agrees(printed, value, dec) });
  for (const [stem, t] of Object.entries(tables)) {
    if (t.kind === "seed_spread") {
      for (const row of t.rows) {
        const draws = row["errors by draw"], { mean, sd } = C.spread(draws);
        push(stem, t, row.config, "draws", row.draws, draws.length);
        push(stem, t, row.config, "measured", row.measured, draws[0]);
        push(stem, t, row.config, "mean", row.mean, mean);
        push(stem, t, row.config, "sd", row.sd, sd);
      }
    }
    const fields = CHECKS[t.kind];
    if (!fields) continue;
    const dimsCol = t.kind === "algorithm" ? "tuple" : "dims";
    for (const row of t.rows) {
      const d = row[dimsCol];
      for (const field of fields) push(stem, t, d, field, row[field], computed(field, d, t.target), field === "E[retrieved]" ? 0 : undefined);
      // The table's measured errors are draw 0 of the seed spread.
      const seed = seeds.find((s) => s.target === t.target && s.config === row.config);
      if (seed && "errors" in row) push(stem, t, d, "errors as seed draw 0", row.errors, seed.measured);
    }
  }
  return out;
}

// ---- ParityChecks: the page maths against the study's reference values ----
function close(actual, expected, what) {
  if (expected === null) return assert.ok(Number.isNaN(actual), `${what}: expected NaN, got ${actual}`);
  const tol = Math.max(1e-12, 1e-9 * Math.abs(expected));
  assert.ok(Math.abs(actual - expected) <= tol, `${what}: ${actual} vs reference ${expected}`);
}

test("matchesReferenceParity", () => {
  assert.ok(parity.rows.length >= 100);
  for (const r of parity.rows) {
    const d = r.dims;
    parity.s.forEach((s, i) => close(C.curve(s, d), r.curve[i], `curve ${d} at ${s}`));
    parity.y.forEach((y, i) => close(C.inverse(y, d), r.inverse[i], `inverse ${d} at ${y}`));
    close(C.threshold(d), r.threshold, `threshold ${d}`);
    parity.targets.forEach((t, i) => close(C.bandsForThreshold(t, d), r.bands[i], `bands ${d} at ${t}`));
    close(C.width(d), r.width, `width ${d}`);
    parity.targets.forEach((t, i) => close(C.errorArea(d, t), r.area[i], `area ${d} at ${t}`));
    assert.deepEqual(C.tails(d), r.tails, `tails ${d}`);
    parity.targets.forEach((t, i) => {
      const c = counts(d, t), [fp, fn, candidates] = r.counts[i];
      close(c.fp, fp, `E[FP] ${d} at ${t}`);
      close(c.fn, fn, `E[FN] ${d} at ${t}`);
      close(c.candidates, candidates, `candidates ${d} at ${t}`);
    });
  }
});

test("parityPinnedAtProvenanceSha", () => {
  // The fixture and the page tables must come from the same study commit.
  assert.equal(parity.source, `lsh_grid_analysis at ${study.provenance.sha}`);
  const have = new Set(parity.rows.map((r) => r.dims.join(",")));
  const stems = ["lsh_cascade_table_", "lsh_error_area_table_", "lsh_high_cap_family_table_", "lsh_equal_rows_table_"];
  for (const [stem, t] of Object.entries(study.tables)) {
    if (!stems.some((s) => stem.startsWith(s))) continue;
    for (const r of t.rows) assert.ok(have.has(r.dims.join(",")), `${stem} tuple ${r.dims} has no parity row`);
  }
  assert.ok(parity.rows.every((r) => r.counts?.length === parity.targets.length), "every parity row carries expected counts per target");
});

test("reproducesPrintedTableValues", () => {
  const checks = tableChecks(study.tables);
  assert.ok(checks.length >= 1000, `only ${checks.length} checks`);
  const bad = checks.filter((c) => !c.ok);
  assert.deepEqual(bad, []);
  for (const kind of ["cascade", "equal_rows", "error_area", "high_cap_family", "algorithm", "seed_spread"]) {
    assert.ok(checks.some((c) => c.kind === kind), `no checks on ${kind}`);
  }
  for (const field of [...EXPECTED, "mean", "sd", "errors as seed draw 0"]) {
    assert.ok(checks.some((c) => c.field === field), `no checks on ${field}`);
  }
});

// ---- CurveChecks: search, tree, log tail and trial maths ----
// Cascade rows are the sharpest tree within n{budget} rows. Equal-rows rows hold their rows within the window around n{ref}.
test("bestTreeMatchesTables", () => {
  const { tolerance, max_free_arity: freeCap, equal_rows_tolerance: band } = study.provenance.grid;
  assert.equal(C.TOLERANCE, tolerance);
  assert.equal(C.MAX_FREE_ARITY, freeCap);
  let searched = 0;
  for (const t of tablesOf("cascade", "equal_rows")) {
    for (const row of t.rows) {
      const d = row.dims, [, ref, depth] = row.config.match(/^n(\d+)_d(\d+)$/).map(Number);
      const solved = C.bandsForThreshold(t.target, d);
      const options = [Math.max(2, Math.floor(solved)), Math.max(2, Math.ceil(solved))];
      assert.ok(options.includes(d[1]), `${row.config} t ${t.target}: d1 ${d[1]} not in ${options}`);
      const [low, high] = t.kind === "cascade" ? [1, ref] : [Math.floor(ref * (1 - band)), Math.floor(ref * (1 + band))];
      assert.deepEqual(C.bestTree(high, depth, t.target, low), d, `${t.kind} ${row.config} t ${t.target}`);
      searched += 1;
    }
  }
  assert.ok(searched >= 60, `only ${searched} tuples searched`);
});

// The depth 1 scan stops early once t̂ passes t, which no table row reaches.
test("bestTreeDepthOneMatchesFullScan", () => {
  const scan = (n, t) => {
    let best = null;
    for (let r = 1; r <= n; r++) {
      const d = [r];
      if (Math.abs(C.threshold(d) - t) <= C.TOLERANCE && (!best || C.width(d) < C.width(best))) best = d;
    }
    return best;
  };
  for (const n of [1, 2, 7, 64, 500, 5000]) {
    for (const t of [0.01, 0.05, 0.3, 0.5, 0.8, 0.95, 0.99]) assert.deepEqual(C.bestTree(n, 1, t), scan(n, t), `n ${n} t ${t}`);
  }
});

test("solveD1PicksSharpestMatch", () => {
  const near = (d, t) => Math.abs(C.threshold(d) - t) <= C.TOLERANCE;
  let both = 0;
  for (const t of Object.values(study.tables)) {
    if (!["cascade", "equal_rows", "high_cap_family"].includes(t.kind)) continue;
    for (const row of t.rows) {
      if (row.dims.length < 2) continue;
      const solved = C.bandsForThreshold(t.target, row.dims);
      const [lo, hi] = [Math.floor(solved), Math.ceil(solved)].map((b) => { const d = row.dims.slice(); d[1] = Math.max(2, b); return d; });
      if (lo[1] === hi[1] || !near(lo, t.target) || !near(hi, t.target)) continue;
      const want = C.width(hi) < C.width(lo) ? hi : lo;
      assert.deepEqual(C.solveD1(row.dims, t.target), { dims: want, matched: true }, `${row.config} t ${t.target}`);
      both += 1;
    }
  }
  assert.ok(both > 0, "some rows match at both floor and ceil");
  // Depth 1 solves d0. 0.5^(1/3) lies within the tolerance of 0.8.
  assert.deepEqual(C.solveD1([5], 0.8), { dims: [3], matched: true });
  // No single band reaches below 0.5, so the closest is d0 1 and unmatched.
  assert.deepEqual(C.solveD1([5], 0.3), { dims: [1], matched: false });
  // d1 5 and 6 both match t 0.9 and 5 is narrower, so the last matched option is not the pick.
  assert.deepEqual(C.solveD1([20, 1], 0.9), { dims: [20, 5], matched: true });
});

test("evalTreeMatchesCurve", () => {
  for (const dims of [[2], [2, 3], [2, 3, 2], [1, 2, 2, 2]]) {
    const n = C.rows(dims);
    for (const s of [0.2, 0.5, 0.7]) {
      let mass = 0;
      for (let m = 0; m < 1 << n; m++) {
        const bits = Uint8Array.from({ length: n }, (_, i) => (m >> i) & 1);
        const ones = bits.reduce((a, b) => a + b, 0);
        const levels = C.evalTree(bits, dims);
        assert.equal(levels.length, dims.length);
        assert.equal(levels[dims.length - 1].length, 1);
        if (levels[dims.length - 1][0]) mass += s ** ones * (1 - s) ** (n - ones);
      }
      assert.ok(Math.abs(mass - C.curve(s, dims)) < 1e-12, `${dims} at ${s}: ${mass}`);
    }
  }
  const [lo, hi] = [0, 5, 10].map((k) => C.wilson(k, 10)).reduce((a, w) => [[...a[0], w[0]], [...a[1], w[1]]], [[], []]);
  [0.0, 0.2366, 0.7225].forEach((v, i) => assert.ok(Math.abs(lo[i] - v) < 1e-4, `wilson lo ${i}`));
  [0.2775, 0.7634, 1.0].forEach((v, i) => assert.ok(Math.abs(hi[i] - v) < 1e-4, `wilson hi ${i}`));
  for (const r of parity.rows) {
    const { fplus, fminus } = C.localSlopes(r.dims);
    assert.ok(Math.abs(fplus / r.tails[0] - 1) < 1e-3, `f+ slope ${r.dims}: ${fplus}`);
    assert.ok(Math.abs(fminus / r.tails[1] - 1) < 1e-3, `f- slope ${r.dims}: ${fminus}`);
  }
  const trials = 20000;
  const hits = C.runTrials(0.5, [5, 20], trials, C.mulberry32(42));
  const p = C.curve(0.5, [5, 20]);
  assert.ok(Math.abs(hits / trials - p) < 4 * Math.sqrt(p * (1 - p) / trials), `bulk rate ${hits / trials} vs ${p}`);
  const one = C.sampleTree(0.5, [5, 20], C.mulberry32(7));
  assert.equal(one.bits.length, 100);
  assert.deepEqual(one.levels, C.evalTree(one.bits, [5, 20]));
});

// curve() loses digits once a level nears 0 or 1, so the reference carries the hit rate and its complement in linear space.
function hitMiss(s, d) {
  const ln = (x, xc) => (x < 0.5 ? Math.log(x) : Math.log1p(-xc));
  let p = s ** d[0], q = -Math.expm1(d[0] * Math.log(s));
  for (let j = 1; j < d.length; j++) {
    const [lp, lq] = [ln(p, q), ln(q, p)];
    [p, q] = j % 2 === 1 ? [-Math.expm1(d[j] * lq), Math.exp(d[j] * lq)] : [Math.exp(d[j] * lp), -Math.expm1(d[j] * lp)];
  }
  return [p, q];
}

// The slope check only sees differences of logs, so an offset in logPair would pass it. This pins absolute values.
test("logPairMatchesLogCurve", () => {
  const shapes = [[5, 20], [10, 710], [7, 23, 3], [3, 13, 8, 8, 4], [2, 16, 7, 11, 4], [8, 7, 5, 7, 5]];
  let compared = 0;
  for (const d of shapes) {
    for (const s of [0.2, 0.4, 0.5, 0.6, 0.8]) {
      const [p, q] = hitMiss(s, d);
      for (const [what, pair] of [["s", C.logPair(s, d)], ["1 - s", C.logPair(0, d, 1 - s)]]) {
        // Logs of underflowed rates are not comparable, so those sides are skipped.
        if (p > 1e-300) assert.ok(Math.abs(pair.lnp - Math.log(p)) < 1e-8, `ln p ${d} at ${what} ${s}: ${pair.lnp} vs ${Math.log(p)}`);
        if (q > 1e-300) assert.ok(Math.abs(pair.lnq - Math.log(q)) < 1e-8, `ln q ${d} at ${what} ${s}: ${pair.lnq} vs ${Math.log(q)}`);
        compared += (p > 1e-300) + (q > 1e-300);
      }
    }
  }
  assert.ok(compared >= 100, `only ${compared} comparisons`);
});

// profile(d)[j] describes the prefix tree d[0..j], the curve the explorer draws for level j.
test("profileMatchesPrefixCurves", () => {
  const deep = study.tables.lsh_algorithm_table_t50.rows[1].tuple;
  for (const d of [deep, [7, 23, 3], [7, 69], [100, 1], [3, 13, 1, 8, 4]]) {
    const prof = C.profile(d);
    assert.equal(prof.length, d.length, `levels of ${d}`);
    prof.forEach((p, j) => {
      const prefix = d.slice(0, j + 1);
      assert.equal(p.or, C.isOr(j), `op ${d} level ${j}`);
      assert.equal(p.arity, d[j], `arity ${d} level ${j}`);
      close(p.mid, C.inverse(0.5, prefix), `mid ${d} level ${j}`);
      // The forward curve pins the midpoint independently of inverse().
      close(C.curve(p.mid, prefix), 0.5, `curve at mid ${d} level ${j}`);
      close(p.width, C.width(prefix), `width ${d} level ${j}`);
      // An arity of 1 passes its one child through, so the level repeats the one below.
      if (d[j] === 1) {
        close(p.mid, prof[j - 1].mid, `arity 1 mid ${d} level ${j}`);
        close(p.width, prof[j - 1].width, `arity 1 width ${d} level ${j}`);
      }
    });
    assert.equal(prof.at(-1).mid, C.threshold(d), `root mid ${d}`);
    assert.equal(prof.at(-1).width, C.width(d), `root width ${d}`);
  }
});

test("profileStaysNumericAtLargestTuple", () => {
  // The largest tree the explorer accepts: every level at the arity cap and the depth at the grid max.
  const prof = C.profile(Array(MAX_DEPTH).fill(1e5));
  assert.equal(prof.length, MAX_DEPTH);
  for (const [j, p] of prof.entries()) {
    for (const key of ["mid", "width"]) {
      assert.ok(Number.isFinite(p[key]) || Number.isNaN(p[key]), `level ${j} ${key} is ${p[key]}`);
    }
  }
});

test("runTrialsMatchesCurveAtDepthFive", () => {
  const d = [3, 13, 8, 8, 4], trials = 20000;
  for (const s of [0.48, 0.5, 0.52]) {
    const hits = C.runTrials(s, d, trials, C.mulberry32(11));
    const p = C.curve(s, d);
    assert.ok(Math.abs(hits / trials - p) < 4 * Math.sqrt(p * (1 - p) / trials), `depth 5 rate ${hits / trials} vs ${p} at ${s}`);
  }
});

// ---- FakeDom: just enough Element for the explorer and its chart kit ----
class Element {
  constructor(tag) {
    Object.assign(this, { tagName: tag.toUpperCase(), attrs: new Map(), children: [], parentNode: null, listeners: {}, dataset: {}, style: {}, text: "" });
  }
  setAttribute(k, v) { this.attrs.set(k, String(v)); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  removeAttribute(k) { this.attrs.delete(k); }
  get id() { return this.getAttribute("id"); }
  set id(v) { this.setAttribute("id", v); }
  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }
  get classList() {
    const names = () => new Set(this.className.split(/\s+/).filter(Boolean));
    const put = (set) => { this.className = [...set].join(" "); };
    return {
      contains: (c) => names().has(c),
      add: (...cs) => { const s = names(); cs.forEach((c) => s.add(c)); put(s); },
      remove: (...cs) => { const s = names(); cs.forEach((c) => s.delete(c)); put(s); },
      toggle: (c, force) => { const s = names(), on = force === undefined ? !s.has(c) : !!force; on ? s.add(c) : s.delete(c); put(s); return on; },
    };
  }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { this.children = []; this.text = String(v); }
  set innerHTML(v) { this.children = []; this.text = String(v).replace(/<[^>]*>/g, ""); }
  get innerHTML() { return this.text; }
  appendChild(c) {
    if (typeof c === "string") { this.text += c; return c; }
    c.parentNode?.children.splice(c.parentNode.children.indexOf(c), 1);
    c.parentNode = this;
    this.children.push(c);
    return c;
  }
  append(...cs) { cs.forEach((c) => this.appendChild(c)); }
  replaceChildren(...cs) { this.children = []; this.text = ""; this.append(...cs); }
  replaceWith(n) {
    const kids = this.parentNode.children;
    n.parentNode?.children.splice(n.parentNode.children.indexOf(n), 1);
    kids.splice(kids.indexOf(this), 1, n);
    n.parentNode = this.parentNode;
    this.parentNode = null;
  }
  remove() { this.parentNode?.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
  addEventListener(type, f) { (this.listeners[type] ||= []).push(f); }
  dispatch(type, ev = {}) { for (const f of this.listeners[type] || []) f({ target: this, preventDefault() {}, ...ev }); }
  matches(sel) {
    const m = sel.match(/^([a-z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/i);
    if (!m) throw new Error(`fake DOM cannot match ${sel}`);
    if (m[1] && m[1].toUpperCase() !== this.tagName) return false;
    if (m[2] && !m[2].slice(1).split(".").every((c) => this.classList.contains(c))) return false;
    for (const [, k, v] of m[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
      const got = k.startsWith("data-") ? this.dataset[k.slice(5)] ?? this.getAttribute(k) : this.getAttribute(k);
      if (got === null || got === undefined || (v !== undefined && got !== v)) return false;
    }
    return true;
  }
  querySelectorAll(sel) { return this.children.flatMap((c) => [...(c.matches(sel) ? [c] : []), ...c.querySelectorAll(sel)]); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  getBoundingClientRect() { return { width: 560, height: 340, left: 0, top: 0, right: 560, bottom: 340 }; }
  get clientWidth() { return 560; }
  get offsetWidth() { return 560; }
  focus() {}
  scrollIntoView() {}
  setPointerCapture() {}
}

// Runs the page's chart kit and explorer. Frames queue until flush() runs them. Reduced motion takes the instant path.
// Missing ids are created on demand, so `looked` records every id the explorer asks for.
// `saved` is the explorer state found in storage on load.
function boot(saved) {
  const body = new Element("body"), frames = new Map(), looked = new Set();
  let nextFrame = 1;
  const add = (tag, cls) => { const e = body.appendChild(new Element(tag)); if (cls) e.className = cls; return e; };
  // The explorer finds its tree panel by class, so the fake page has it only when the real markup does.
  if (PageScripts.hasClass("ex-tree")) add("div", "ex-tree");
  const store = new Map();
  const document = {
    activeElement: null,
    createElement: (tag) => new Element(tag),
    createElementNS: (ns, tag) => new Element(tag),
    getElementById(id) {
      looked.add(id);
      let e = body.querySelector(`[id="${id}"]`);
      if (!e) { e = add(id === "ex-preset" ? "select" : "div"); e.setAttribute("id", id); }
      if (id === "sim-data") e.textContent = PageScripts.read("sim-data");
      return e;
    },
    querySelector: (sel) => body.querySelector(sel),
    querySelectorAll: (sel) => body.querySelectorAll(sel),
  };
  const ctx = vm.createContext({
    console, performance, setTimeout, clearTimeout, document,
    matchMedia: () => ({ matches: true }),
    localStorage: { getItem: (k) => store.get(k) ?? (saved ? JSON.stringify(saved) : null), setItem: (k, v) => store.set(k, v) },
    requestAnimationFrame: (f) => { frames.set(nextFrame, f); return nextFrame++; },
    cancelAnimationFrame: (id) => frames.delete(id),
    addEventListener: () => {},
  });
  // The maths is stateless, so the explorer shares this realm's copy. Inside a vm context it runs about 9 times slower.
  ctx.globalThis = ctx.window = ctx;
  ctx.Cascade = C;
  for (const id of ["chartkit-src", "explorer-src"]) vm.runInContext(PageScripts.read(id), ctx, { filename: id });
  // Runs the frames due now. True while more are queued.
  const step = () => {
    const due = [...frames.values()];
    frames.clear();
    due.forEach((f) => f(performance.now()));
    return frames.size > 0;
  };
  const flush = () => { for (let i = 0; i < 100 && step(); i++); };
  return { $: (id) => document.getElementById(id), body, flush, step, looked };
}

const depthInput = ($) => $("ex-depth").querySelector("input");
const setDepth = ($, flush, k) => { const input = depthInput($); input.value = String(k); input.dispatch("change"); flush(); };
// The arities the ladder shows, d0 first.
const arities = ($, k) => Array.from({ length: k }, (_, j) => Number($("ex-ladder").querySelector(`[aria-label="arity d${j}"]`).value));
const shows = (text, v) => new RegExp(`(^|[^\\d.])${String(v).replace(".", "\\.")}($|[^\\d])`).test(text);

// ---- BehaviourChecks ----
test("runRightAfterShapeChangeUsesNewTree", () => {
  const { $, flush } = boot();
  flush();
  const select = $("ex-preset"), pair = select.querySelectorAll("option").find((o) => o.textContent.startsWith("(7, 69)"));
  assert.ok(pair, "depth 2 preset (7, 69) is listed");
  select.value = pair.value;
  select.dispatch("change");
  // Run lands before the frame that redraws the ladder for the new tree.
  assert.doesNotThrow(() => $("ex-one").dispatch("click"));
  const rungs = $("ex-ladder").querySelectorAll(".rung");
  assert.equal(rungs.length, 3, "root, L0 and rows for a depth 2 tree");
  assert.ok(rungs[0].querySelector(".outcome"), "root rung shows the outcome chip");
});

test("everyExplorerIdInMarkup", () => {
  const { $, flush, looked } = boot();
  flush();
  for (const id of ["ex-one", "ex-many", "ex-sweep", "ex-clear", "ex-search"]) { $(id).dispatch("click"); flush(); }
  const have = PageScripts.markupIds();
  const missing = [...looked].filter((id) => !have.has(id));
  assert.ok(looked.size >= 20, `only ${looked.size} ids looked up`);
  assert.deepEqual(missing, [], "ids the explorer looks up but the markup lacks");
});

test("trialSeedReplaysTrials", () => {
  const { $, flush } = boot();
  flush();
  // Each trial dot carries a title with its counts at that s.
  const dots = () => $("ex-curve").querySelectorAll("title").map((t) => t.textContent);
  const run = () => { $("ex-many").dispatch("click"); flush(); return dots(); };
  // A browser fires change only when the value differs, so each seed here differs from the one before.
  const seed = (v) => { const input = $("ex-seed"); assert.notEqual(input.value, String(v)); input.value = String(v); input.dispatch("change"); };
  // At its threshold the tree fires about half the time, so two seeds almost surely differ.
  const at = $("ex-s");
  at.value = String(Math.round(C.threshold(arities($, Number(depthInput($).value))) * 1000) / 1000);
  at.dispatch("input");
  flush();
  seed(4242);
  const first = run();
  assert.equal(first.length, 1, "1000 at s draws one dot");
  assert.match(first[0], / of 1000 candidates/);
  $("ex-clear").dispatch("click");
  assert.deepEqual(run(), first, "Clear replays the trials from the shown seed");
  seed(7);
  const other = run();
  assert.equal(other.length, 1, "a new seed starts fresh trials");
  assert.match(other[0], / of 1000 candidates/);
  assert.notDeepEqual(other, first, "a different seed gives different trials");
  seed(4242);
  assert.deepEqual(run(), first, "returning to a seed replays its trials");
});

const enterSeed = ($, v) => { const input = $("ex-seed"); input.value = String(v); input.dispatch("change"); };

test("seedInputShowsEffectiveSeed", () => {
  const { $, flush } = boot();
  flush();
  enterSeed($, 12.6);
  flush();
  assert.equal(String($("ex-seed").value), "13", "a fractional seed rounds and the box shows the rounded seed");
  enterSeed($, 0);
  flush();
  assert.equal(String($("ex-seed").value), "13", "an invalid seed is refused and the box shows the current seed");
});

test("seedChangeKeepsRowCapMessage", () => {
  const { $, flush } = boot({ dims: [400, 400], T: 0.5, s: 0.5, seed: 753 });
  flush();
  const why = /Trials run on trees of at most/;
  assert.match($("ex-msg").textContent, why, "a tree over the row cap says why trials are off");
  enterSeed($, 754);
  flush();
  assert.ok($("ex-one").disabled, "trials stay off");
  assert.match($("ex-msg").textContent, why, "a seed change keeps the reason trials are off");
});

// Guard: the explorer once let the depth reach 13 while the study's search stops at its grid max.
test("depthCappedAtGrid", () => {
  for (let k = 1; k <= Math.max(13, MAX_DEPTH + 2); k++) {
    const { $, flush } = boot();
    flush();
    assert.equal(Number(depthInput($).max), MAX_DEPTH, "the depth box stops at the grid max");
    setDepth($, flush, k);
    const want = Math.min(k, MAX_DEPTH);
    assert.equal(Number(depthInput($).value), want, `depth ${k} asked`);
    assert.equal($("ex-ladder").querySelectorAll(".rung").length, want + 1, `rungs for depth ${k} asked`);
  }
  const { $, flush } = boot();
  flush();
  const select = $("ex-preset");
  for (const o of select.querySelectorAll("option").filter((x) => x.value !== "custom")) {
    select.value = o.value;
    select.dispatch("change");
    flush();
    assert.ok(Number(depthInput($).value) <= MAX_DEPTH, `preset ${o.textContent} loads within the grid max`);
  }
});

// Guard: a depth 13 state saved under the old cap must not load past the grid max.
test("savedDeepStateClamped", () => {
  const deep = [2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2];
  const { $, flush } = boot({ dims: deep, T: 0.5, s: 0.5, seed: 753 });
  flush();
  assert.equal(Number(depthInput($).value), MAX_DEPTH);
  assert.deepEqual(arities($, MAX_DEPTH), deep.slice(0, MAX_DEPTH), "the saved arities up to the grid max");
  assert.equal(Number($("ex-t").value), 0.5, "the rest of the saved state loads");
});

// Equal-rows ladders lose expected errors with every level. The page opens on the deepest one against its banding.
test("defaultReproducesStandaloneOrdering", () => {
  const ladders = tablesOf("equal_rows").sort((a, b) => a.target - b.target);
  assert.ok(ladders.length >= 3, "an equal-rows ladder per target");
  for (const t of ladders) {
    const rows = t.rows.slice().sort((a, b) => a.depth - b.depth), errs = rows.map((r) => counts(r.dims, t.target).errors);
    errs.slice(1).forEach((e, i) => assert.ok(e < errs[i], `t ${t.target}: depth ${rows[i + 1].depth} ${e} vs depth ${rows[i].depth} ${errs[i]}`));
  }
  const low = ladders[0], tree = low.rows.filter((r) => r.depth <= MAX_DEPTH).sort((a, b) => b.depth - a.depth)[0];
  const banding = C.bestTree(C.rows(tree.dims), 2, low.target);
  const mine = counts(tree.dims, low.target).errors, theirs = counts(banding, low.target).errors;
  assert.ok(mine < theirs, `${tree.dims} ${mine} vs banding ${banding} ${theirs}`);
  const { $, flush } = boot();
  flush();
  assert.deepEqual(arities($, tree.dims.length), tree.dims);
  assert.equal(Number($("ex-t").value), low.target);
  const text = $("ex-readout").textContent;
  for (const v of [mine, theirs]) assert.ok(shows(text, v), `readout shows expected errors ${v}: ${text}`);
  assert.ok(text.includes(`(${banding.join(", ")})`), `readout names the banding ${banding}: ${text}`);
  // Measured means over the seed draws sit beside the theory.
  for (const d of [tree.dims, banding]) {
    const m = measuredFor(d, low.target);
    assert.ok(m, `the study measured ${d}`);
    assert.ok(shows(text, m.mean.toFixed(1)), `readout shows measured mean ${m.mean.toFixed(1)} for ${d}: ${text}`);
  }
});

test("searchDepthFindsSharpestTree", () => {
  const { $, flush } = boot();
  flush();
  setDepth($, flush, 3);
  const n = C.rows(arities($, 3)), T = Number($("ex-t").value);
  $("ex-search").dispatch("click");
  flush();
  const want = C.bestTree(n, 3, T);
  assert.ok(want, `a depth 3 tree fits ${n} rows at t ${T}`);
  assert.deepEqual(arities($, 3), want);
});

// The heaviest search the explorer allows: the deepest tree just under the row limit, t 0.99.
const SEARCH_LIMIT = Number(PageScripts.read("explorer-src").match(/\bSEARCH_LIMIT = ([\d.e]+)/)[1]);
const FRAME_BUDGET_MS = 100;
function bootDeepSearch() {
  const k = MAX_DEPTH, side = Math.floor(Math.sqrt(SEARCH_LIMIT / 2 ** (k - 2))), T = 0.99;
  assert.ok(k >= 2 && side <= 1e5, `depth ${k} tree near ${SEARCH_LIMIT} rows within the arity cap`);
  const dims = [side, side, ...Array(k - 2).fill(2)];
  const page = boot({ dims, T, s: 0.5, seed: 753 });
  for (let i = 0; i < 1e4 && page.step(); i++);
  return { ...page, k, dims, T };
}

// Guard: the depth search once ran in one task, so a deep tree over many rows froze the tab for seconds.
test("searchDepthStaysResponsive", () => {
  const { $, step, k, dims, T } = bootDeepSearch();
  let worst = 0, frames = 0;
  const timed = (f) => { const t0 = performance.now(), more = f(); worst = Math.max(worst, performance.now() - t0); return more; };
  timed(() => $("ex-search").dispatch("click"));
  while (frames < 1e5 && timed(step)) frames++;
  assert.ok(worst < FRAME_BUDGET_MS, `a search task took ${worst.toFixed(0)} ms at depth ${k} over ${C.rows(dims)} rows`);
  assert.deepEqual(arities($, k), C.bestTree(C.rows(dims), k, T), "the async search lands on the bestTree result");
});

test("searchStopsWhenTreeChanges", () => {
  const { $, flush, step, k, dims } = bootDeepSearch();
  $("ex-search").dispatch("click");
  step();
  assert.match($("ex-msg").textContent, /Searching/, "a progress line while the search runs");
  setDepth($, flush, k - 1 || 2);
  const kept = Number(depthInput($).value);
  for (let i = 0; i < 1e5 && step(); i++);
  assert.deepEqual(arities($, kept), dims.concat(2).slice(0, kept), "the stale search leaves the new tree alone");
  assert.doesNotMatch($("ex-msg").textContent, /Searching/);
});
