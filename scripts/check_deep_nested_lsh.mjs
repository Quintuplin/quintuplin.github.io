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
  // Every id in the markup, with script bodies removed so ids named in code do not count.
  markupIds() {
    const markup = this.html.replace(/(<script[^>]*>)[\s\S]*?<\/script>/g, "$1");
    return new Set([...markup.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
  },
};

vm.runInThisContext(PageScripts.read("cascade-src"), { filename: "cascade-src" });
const C = globalThis.Cascade;
const study = JSON.parse(PageScripts.read("sim-data"));
const parity = JSON.parse(readFileSync(new URL("fixtures/deep-nested-lsh-parity.json", import.meta.url), "utf8"));

// ---- TableCheck: every printed table value the maths can reproduce ----
const CHECKS = {
  cascade: ["rows", "threshold", "width", "fp_exp x fn_exp"],
  equal_rows: ["rows", "threshold", "width", "fp_exp x fn_exp"],
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
  }
}

// Compared at the precision the table prints.
function tableChecks(tables) {
  const out = [];
  for (const [stem, t] of Object.entries(tables)) {
    const fields = CHECKS[t.kind];
    if (!fields) continue;
    const dimsCol = t.kind === "algorithm" ? "tuple" : "dims";
    for (const row of t.rows) {
      const d = row[dimsCol];
      for (const field of fields) {
        const printed = row[field], value = computed(field, d, t.target), dec = t.decimals[field];
        const ok = Array.isArray(printed) || dec === undefined
          ? JSON.stringify(printed) === JSON.stringify(value)
          : Math.abs(value - printed) <= 0.5 * Math.pow(10, -dec) + 1e-9;
        out.push({ table: stem, kind: t.kind, dims: d, field, printed, computed: value, ok });
      }
      if (t.kind === "cascade" && row.depth === 2) {
        const best = C.bestDepth2(Number(row.config.match(/^n(\d+)_/)[1]), t.target);
        out.push({ table: stem, kind: t.kind, dims: d, field: "sharpest depth 2", printed: d, computed: best,
          ok: JSON.stringify(best) === JSON.stringify(d) });
      }
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
});

test("reproducesPrintedTableValues", () => {
  const checks = tableChecks(study.tables);
  assert.ok(checks.length >= 500, `only ${checks.length} checks`);
  const bad = checks.filter((c) => !c.ok);
  assert.deepEqual(bad, []);
  for (const kind of ["cascade", "equal_rows", "error_area", "high_cap_family", "algorithm"]) {
    assert.ok(checks.some((c) => c.kind === kind), `no checks on ${kind}`);
  }
});

// ---- CurveChecks: solver, tree, log tail and trial maths ----
test("solverMatchesTables", () => {
  let d2 = 0;
  for (const t of Object.values(study.tables)) {
    if (t.kind !== "cascade") continue;
    for (const row of t.rows) {
      const d = row.dims;
      const solved = C.bandsForThreshold(t.target, d);
      const options = [Math.max(2, Math.floor(solved)), Math.max(2, Math.ceil(solved))];
      assert.ok(options.includes(d[1]), `${row.config} t ${t.target}: d1 ${d[1]} not in ${options}`);
      if (row.depth === 2) {
        const budget = Number(row.config.match(/^n(\d+)_/)[1]);
        assert.deepEqual(C.bestDepth2(budget, t.target), d, `bestDepth2 ${budget} t ${t.target}`);
        d2 += 1;
      }
    }
  }
  assert.equal(d2, 12);
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
  const deep = study.facts.algorithm["0.5"].cascade.tuple;
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
  const prof = C.profile(Array(13).fill(1e5));
  assert.equal(prof.length, 13);
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
function boot() {
  const body = new Element("body"), frames = new Map(), looked = new Set();
  let nextFrame = 1;
  const add = (tag, cls) => { const e = body.appendChild(new Element(tag)); if (cls) e.className = cls; return e; };
  add("div", "ex-tree");
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
    localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) },
    requestAnimationFrame: (f) => { frames.set(nextFrame, f); return nextFrame++; },
    cancelAnimationFrame: (id) => frames.delete(id),
    addEventListener: () => {},
  });
  ctx.globalThis = ctx.window = ctx;
  for (const id of ["cascade-src", "chartkit-src", "explorer-src"]) vm.runInContext(PageScripts.read(id), ctx, { filename: id });
  const flush = () => {
    for (let i = 0; i < 100 && frames.size; i++) {
      const due = [...frames.values()];
      frames.clear();
      due.forEach((f) => f(performance.now()));
    }
  };
  return { $: (id) => document.getElementById(id), body, flush, looked };
}

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
  for (const id of ["ex-one", "ex-many", "ex-sweep", "ex-clear"]) { $(id).dispatch("click"); flush(); }
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
  const runAtSeed = (seed) => {
    $("ex-clear").dispatch("click");
    const input = $("ex-seed");
    input.value = String(seed);
    input.dispatch("change");
    $("ex-many").dispatch("click");
    flush();
    return dots();
  };
  const first = runAtSeed(4242);
  assert.equal(first.length, 1, "1000 at s draws one dot");
  assert.match(first[0], / of 1000 candidates/);
  assert.deepEqual(runAtSeed(4242), first, "the same trial seed replays the same trials");
});
