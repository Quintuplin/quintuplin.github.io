// Explorer behaviour checks for the Deep Nested LSH page (#31). Usage: node check_deep_nested_lsh_explorer.mjs <page>
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {
  PageScripts, C, study, MAX_DEPTH, SEARCH_WORK, same, counts, tablesOf, drainSearch, realised,
  quorumTable, retrievalOf, quorumCounts, verifyRows,
} from "./deep_nested_lsh_support.mjs";

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
function boot(saved, patch = (src) => src) {
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
  // The explorer shares this realm's maths, as inside a vm context it runs about 9 times slower.
  // Its only state is the tidy rule's cache of exact results for the last sweep, so sharing it changes no result.
  ctx.globalThis = ctx.window = ctx;
  ctx.Cascade = C;
  for (const id of ["chartkit-src", "explorer-src"]) vm.runInContext(id === "explorer-src" ? patch(PageScripts.read(id)) : PageScripts.read(id), ctx, { filename: id });
  // Runs the frames due now, each given the frame's one timestamp as a browser does. True while more are queued.
  const step = () => {
    const due = [...frames.values()], now = performance.now();
    frames.clear();
    due.forEach((f) => f(now));
    return frames.size > 0;
  };
  const flush = () => { for (let i = 0; i < 100 && step(); i++); };
  return { $: (id) => document.getElementById(id), body, flush, step, looked, store };
}

const depthInput = ($) => $("ex-depth").querySelector("input");
const setDepth = ($, flush, k) => { const input = depthInput($); input.value = String(k); input.dispatch("change"); flush(); };
// The arities the ladder shows, d0 first.
const arities = ($, k) => Array.from({ length: k }, (_, j) => Number($("ex-ladder").querySelector(`[aria-label="arity d${j}"]`).value));
const shows = (text, v) => new RegExp(`(^|[^\\d.])${String(v).replace(".", "\\.")}($|[^\\d])`).test(text);
// A saved depth 5 state for checks that need a fixed tree, so they do not move with the default.
const PINNED = { dims: [2, 17, 7, 8, 3], T: 0.3, s: 0.5, seed: 753 };

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
  assert.equal(rungs.length, 2, "L1 and L0 for a depth 2 tree");
  assert.ok(rungs[0].querySelector(".outcome"), "root rung shows the outcome chip");
});

// Guard: each rung once drew the fan-out of the level above it, so its tiles disagreed with its own arity.
test("rungTilesMatchArity", () => {
  const dims = [2, 18, 4, 3], s = 0.673, k = dims.length, p = C.levels(s, dims);
  const { $, flush, body } = boot({ dims, T: 0.5, s, seed: 753 });
  flush();
  const ladder = () => $("ex-ladder").querySelectorAll(".rung");
  // A rung's drawn tiles, the count its "+k · j on" tile hides and how many of all its tiles fired.
  const tilesOf = (r) => {
    const shown = r.querySelectorAll(".tile").filter((t) => !t.classList.contains("more")), more = r.querySelector(".tile.more");
    const [, hidden = 0, on = 0] = more?.textContent.match(/^\+(\d+)(?: · (\d+) on)?$/) || [];
    return { shown, more, hidden: Number(hidden), on: Number(on) + shown.filter((t) => t.classList.contains("on")).length };
  };
  assert.equal(ladder().length, k, "one rung per level");
  const curves = body.querySelectorAll(".lvl-curve");
  ladder().forEach((r, i) => {
    const j = k - 1 - i, { shown, more, hidden } = tilesOf(r);
    const [, op, level, shownP] = r.querySelector(".rung-l").textContent.match(/^(AND|OR) L(\d+)p (\S+)$/) || [];
    assert.equal(Number(level), j, `rung ${i} is L${j}`);
    assert.equal(op, C.isOr(j) ? "OR" : "AND", `L${j} names its operation`);
    assert.ok(Math.abs(Number(shownP) - p[j]) < 5e-4, `L${j} p ${shownP} against ${p[j]}`);
    assert.equal(r.querySelectorAll("input").length, 1, `L${j} holds one stepper`);
    assert.equal(Number(r.querySelector(`[aria-label="arity d${j}"]`)?.value), dims[j], `L${j} holds the arity d${j} stepper`);
    assert.equal(shown.length + hidden, dims[j], `L${j} tiles and +k add to d${j}`);
    assert.equal(!!more, dims[j] > shown.length, `L${j} shows +k only when d${j} exceeds the drawn tiles`);
    assert.equal(shown.every((t) => t.classList.contains("cell")), j === 0, "only L0 draws signature rows");
    r.dispatch("pointerenter");
    assert.deepEqual(curves.map((c) => c.classList.contains("hot")), curves.map((_, x) => x === j), `hovering L${j} picks out its curve`);
    r.dispatch("pointerleave");
  });
  $("ex-one").dispatch("click");
  flush();
  const after = ladder(), fires = (j, on) => (C.isOr(j) ? on > 0 : on === dims[j]);
  // Rung j draws the children of the first node on the rung above, so they must agree with that tile.
  after.forEach((r, i) => {
    if (i) assert.equal(fires(k - 1 - i, tilesOf(r).on), tilesOf(after[i - 1]).shown[0].classList.contains("on"), `L${k - 1 - i} children agree with their parent`);
  });
  const chip = after[0].querySelector(".outcome");
  assert.ok(chip, "the top rung carries the outcome chip");
  assert.equal(["TP", "FP"].includes(chip.dataset.k), fires(k - 1, tilesOf(after[0]).on), "the chip follows the root's children");
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
  const { $, flush, step } = boot(PINNED);
  flush();
  // Each trial dot carries a title with its counts at that s. Linear-hash runs take many frames, so run drains them.
  const dots = () => $("ex-curve").querySelectorAll("title").map((t) => t.textContent);
  const run = () => { $("ex-many").dispatch("click"); for (let i = 0; i < 1e5 && step(); i++); return dots(); };
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
  // The dot sits at the Jaccard the drawn pairs realise.
  const { U, I } = realised(Number(at.value));
  assert.ok(first[0].startsWith(`s ${Math.round((1000 * I) / U) / 1000}: `), `dot at ${I}/${U}: ${first[0]}`);
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
    assert.equal($("ex-ladder").querySelectorAll(".rung").length, want, `rungs for depth ${k} asked`);
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

// Guard: preset ids are positions, so a state saved under other study data once named a different preset than its tree.
test("savedPresetOfOtherTreeDropped", () => {
  const first = boot();
  first.flush();
  const p0 = first.$("ex-preset").querySelectorAll("option").find((o) => o.value === "p0");
  assert.ok(p0 && !p0.textContent.startsWith("(7, 69)"), "p0 is not the (7, 69) preset");
  const { $, flush } = boot({ dims: [7, 69], T: 0.5, s: 0.5, seed: 753, preset: "p0" });
  flush();
  assert.equal($("ex-preset").value, "custom", "a saved preset id whose tree differs reads as a custom tuple");
  assert.deepEqual(arities($, 2), [7, 69], "the saved tree loads");
});

// A saved preset that still names its tree reopens as that preset.
test("savedPresetOfSameTreeKept", () => {
  const first = boot();
  first.flush();
  const select = first.$("ex-preset"), pair = select.querySelectorAll("option").find((o) => o.textContent.startsWith("(7, 69)"));
  select.value = pair.value;
  select.dispatch("change");
  first.flush();
  const saved = JSON.parse([...first.store.values()].at(-1));
  assert.equal(saved.preset, pair.value, "the picked preset is saved");
  const { $, flush } = boot(saved);
  flush();
  assert.equal($("ex-preset").value, pair.value, "the saved preset reopens selected");
  assert.deepEqual(arities($, 2), [7, 69], "the saved tree loads");
});

// Equal-rows ladders lose expected errors with every level up to the trim depth, and every tree past depth 2 beats its banding.
// The page opens on the equal-rows tree at the deepest best measured depth across targets.
test("defaultReproducesStandaloneOrdering", () => {
  const ladders = tablesOf("equal_rows").sort((a, b) => a.target - b.target), trim = study.provenance.grid.trim_depth;
  assert.ok(ladders.length >= 3, "an equal-rows ladder per target");
  for (const t of ladders) {
    const rows = t.rows.slice().sort((a, b) => a.depth - b.depth), errs = rows.map((r) => counts(r.dims, t.target).errors);
    assert.ok(rows.some((r) => r.depth === trim), `t ${t.target} reaches depth ${trim}`);
    errs.slice(1).forEach((e, i) => rows[i + 1].depth > trim
      || assert.ok(e < errs[i], `t ${t.target}: depth ${rows[i + 1].depth} ${e} vs depth ${rows[i].depth} ${errs[i]}`));
    rows.forEach((r, i) => {
      const b = C.bestTree(C.rows(r.dims), 2, t.target), be = counts(b, t.target).errors;
      assert.ok(r.depth < 3 || errs[i] < be, `t ${t.target}: depth ${r.depth} ${errs[i]} vs banding ${b} ${be}`);
    });
  }
  const best = (study.tables.lsh_best_depth_table?.rows || []).filter((r) => r.sweep === "equal")
    .sort((a, b) => b["best depth"] - a["best depth"] || a.target - b.target)[0];
  assert.ok(best, "the best-depth table covers the equal-rows ladders");
  const ladder = ladders.find((t) => t.target === best.target), tree = ladder.rows.find((r) => r.depth === best["best depth"]);
  assert.ok(tree, `the t ${best.target} ladder has depth ${best["best depth"]}`);
  const banding = C.bestTree(C.rows(tree.dims), 2, ladder.target);
  const mine = counts(tree.dims, ladder.target).errors, theirs = counts(banding, ladder.target).errors;
  assert.ok(mine < theirs, `${tree.dims} ${mine} vs banding ${banding} ${theirs}`);
  const { $, flush } = boot();
  flush();
  assert.deepEqual(arities($, tree.dims.length), tree.dims);
  assert.equal(Number($("ex-t").value), ladder.target);
  const text = $("ex-readout").textContent;
  for (const v of [mine, theirs]) assert.ok(shows(text, v), `readout shows expected errors ${v}: ${text}`);
  assert.ok(text.includes(`(${banding.join(", ")})`), `readout names the banding ${banding}: ${text}`);
  // Measured means over the seed draws sit beside the theory.
  for (const d of [tree.dims, banding]) {
    const m = measuredFor(d, ladder.target);
    assert.ok(m, `the study measured ${d}`);
    assert.ok(shows(text, m.mean.toFixed(1)), `readout shows measured mean ${m.mean.toFixed(1)} for ${d}: ${text}`);
  }
});

// A ladder's best measured depth has the least mean errors over the seed draws, ties going to the shallower depth.
// The equal-rows and top-budget presets mark that tree on each ladder.
test("bestDepthTableMatchesSeedMeans", () => {
  const best = study.tables.lsh_best_depth_table?.rows || [], TOP = study.facts.top_budget;
  assert.ok(best.length >= 3, "the page embeds the study's best-depth table");
  const seeds = tablesOf("seed_spread").flatMap((s) => s.rows);
  const ladderOf = (t, sweep) => sweep === "equal" ? tablesOf("equal_rows").filter((x) => x.target === t).flatMap((x) => x.rows)
    : tablesOf("cascade").filter((x) => x.target === t).flatMap((x) => x.rows).filter((r) => r.config.startsWith(`${sweep}_`));
  const want = [];
  for (const { target: t, sweep, "best depth": depth } of best) {
    const scored = ladderOf(t, sweep).map((r) => {
      const draws = seeds.find((x) => x.target === t && x.config === r.config)?.["errors by draw"];
      assert.ok(draws, `the study measured ${r.config} at t ${t}`);
      return { r, mean: draws.reduce((a, b) => a + b, 0) / draws.length };
    });
    assert.ok(scored.length >= 2, `t ${t} ${sweep} ladder`);
    const pick = scored.reduce((a, b) => (b.mean < a.mean || (b.mean === a.mean && b.r.depth < a.r.depth) ? b : a));
    assert.equal(pick.r.depth, depth, `t ${t} ${sweep}`);
    if (sweep === "equal" || sweep === `n${TOP}`) want.push(`${t} ${pick.r.dims}`);
  }
  const { $, flush } = boot();
  flush();
  const select = $("ex-preset"), marked = [];
  for (const o of select.querySelectorAll("option").filter((x) => /best measured/.test(x.textContent))) {
    select.value = o.value;
    select.dispatch("change");
    flush();
    const k = Number(depthInput($).value);
    marked.push(`${Number($("ex-t").value)} ${arities($, k)}`);
  }
  assert.deepEqual(marked.sort(), want.sort());
});

const drain = (step) => { for (let i = 0; i < 1e5 && step(); i++); };
const tick = ($, id, on) => { $(id).checked = on; $(id).dispatch("change"); };
const seedRow = (t, config) => tablesOf("seed_spread").flatMap((x) => x.rows).find((x) => x.target === t && x.config === config);

test("pipelineToggleShowsStudyCounts", () => {
  const { $, flush, step } = boot();
  flush();
  const d = arities($, Number(depthInput($).value)), T = Number($("ex-t").value), n = C.rows(d);
  // A verify row names its rows and retrieval banding, which two ladder trees can share.
  const r = quorumTable.rows.find((x) => x.target === T && x.rows === n && same(x.retrieval, retrievalOf(d)));
  assert.ok(r, `the study verified the default tree ${d}`);
  assert.equal($("ex-pipeline").checked, false, "pipeline off by default");
  assert.equal($("ex-quorum").checked, false, "quorum off by default");
  assert.doesNotMatch($("ex-readout").textContent, /pipeline|quorum/);
  tick($, "ex-pipeline", true);
  drain(step);
  let text = $("ex-readout").textContent;
  const m = C.spread(seedRow(T, `verify_${n}_${d.join("x")}`)["errors by draw"]).mean.toFixed(1);
  for (const v of [r["E[errors]"], r.retrieved, m]) assert.ok(shows(text, v), `pipeline card shows ${v}: ${text}`);
  assert.match(text, /pipeline expected errors \(theory\)/);
  tick($, "ex-quorum", true);
  drain(step);
  text = $("ex-readout").textContent;
  assert.match(text, /quorum check expected errors \(theory\)/);
  assert.ok(shows(text, quorumCounts(n, T).errors), `quorum card shows ${quorumCounts(n, T).errors}: ${text}`);
});

// Guard: a slow pipeline count for one tree must never land on the next tree.
test("pipelineCountsFollowShape", () => {
  const { $, flush, step } = boot();
  flush();
  const select = $("ex-preset"), pick = (dims) => {
    const o = select.querySelectorAll("option").find((x) => x.textContent.startsWith("t 0.3 depth") && x.textContent.includes(`(${dims.join(", ")})`));
    select.value = o.value;
    select.dispatch("change");
  };
  const errorsOf = (d) => verifyRows().find((v) => same(v.d, d) && v.r.target === 0.3).r["E[errors]"];
  const pipeCard = () => $("ex-readout").textContent.match(/pipeline expected errors \(theory\)(.*?)f\+ AND tail/)[1];
  const deep = [2, 17, 7, 8, 3], banding = [6, 951];
  pick(banding);
  tick($, "ex-pipeline", true);
  drain(step);
  assert.ok(shows(pipeCard(), errorsOf(banding)), `pipeline card for ${banding}: ${pipeCard()}`);
  // Each move leaves the deep tree's count part done. The next tree is over the row limit, then one whose count is cached.
  const moves = [["a tree over the row limit", () => {
    const d1 = $("ex-ladder").querySelector('[aria-label="arity d1"]');
    d1.value = "100";
    d1.dispatch("change");
  }, /^n\/a/], [`the cached ${banding}`, () => pick(banding), new RegExp(`^${errorsOf(banding)}(?!\\d)`)]];
  for (const [what, move, want] of moves) {
    pick(deep);
    step();
    assert.match(pipeCard(), /^Computing/, `the ${deep} count is still running`);
    move();
    assert.equal(step(), false, `the ${deep} count stops after the move to ${what}`);
    drain(step);
    const card = pipeCard();
    assert.match(card, want, `pipeline card for ${what}`);
    assert.ok(!shows(card, errorsOf(deep)), `pipeline card for ${what} shows the ${deep} errors: ${card}`);
  }
});

test("searchDepthFindsSharpestTree", () => {
  const { $, flush } = boot(PINNED);
  flush();
  setDepth($, flush, 3);
  const n = C.rows(arities($, 3)), T = Number($("ex-t").value);
  $("ex-search").dispatch("click");
  flush();
  const want = C.bestTree(n, 3, T);
  assert.ok(want, `a depth 3 tree fits ${n} rows at t ${T}`);
  assert.deepEqual(arities($, 3), want);
});

// The largest tree the explorer searches: the deepest one just under the row limit, here at t 0.99.
const SEARCH_LIMIT = Number(PageScripts.read("explorer-src").match(/\bSEARCH_LIMIT = ([\d.e]+)/)[1]);
const FRAME_BUDGET_MS = 100;
// Sets the explorer's search work cap to `work`.
const WORK_DECLARATION = /\bSEARCH_WORK = [\d.e]+/;
const withWork = (work) => (src) => {
  assert.match(src, WORK_DECLARATION, "the explorer declares SEARCH_WORK");
  return src.replace(WORK_DECLARATION, `SEARCH_WORK = ${work}`);
};
// Guard: a page already at the requested cap once failed as if it lacked the declaration.
test("withWorkPatchesTheDeclaration", () => {
  const src = "const SEARCH_WORK = 30000000;";
  assert.equal(withWork(30000000)(src), src);
  assert.equal(withWork(5)(src), "const SEARCH_WORK = 5;");
  assert.throws(() => withWork(5)("const SEARCH_STEP = 1;"), /declares SEARCH_WORK/);
});
function bootDeepSearch(work = SEARCH_WORK) {
  const k = MAX_DEPTH, side = Math.floor(Math.sqrt(SEARCH_LIMIT / 2 ** (k - 2))), T = 0.99;
  assert.ok(k >= 2 && side <= 1e5, `depth ${k} tree near ${SEARCH_LIMIT} rows within the arity cap`);
  const dims = [side, side, ...Array(k - 2).fill(2)];
  const page = boot({ dims, T, s: 0.5, seed: 753 }, withWork(work));
  for (let i = 0; i < 1e4 && page.step(); i++);
  return { ...page, k, dims, T };
}

// Guard: the depth search once ran in one task, so a deep tree over many rows froze the tab for seconds.
// A tenth of the page's work cap still takes several frame budgets in one task.
test("searchDepthStaysResponsive", () => {
  const work = 3e6, { $, step, k, dims, T } = bootDeepSearch(work);
  let worst = 0, frames = 0;
  const timed = (f) => { const t0 = performance.now(), more = f(); worst = Math.max(worst, performance.now() - t0); return more; };
  timed(() => $("ex-search").dispatch("click"));
  while (frames < 1e5 && timed(step)) frames++;
  assert.ok(worst < FRAME_BUDGET_MS, `a search task took ${worst.toFixed(0)} ms at depth ${k} over ${C.rows(dims)} rows`);
  const want = drainSearch(C.treeSearch(C.rows(dims), k, T, 1, work), Infinity).dims;
  assert.deepEqual(arities($, k), want, "the async search lands on the capped treeSearch result");
});

// Searches the pinned tree in an explorer whose work cap is `work`, beside the capped treeSearch reference.
function searchCapped(work) {
  const { $, flush, step } = boot(PINNED, withWork(work));
  flush();
  const k = Number(depthInput($).value), before = arities($, k), n = C.rows(before), T = Number($("ex-t").value);
  const ref = drainSearch(C.treeSearch(n, k, T, 1, work), Infinity);
  $("ex-search").dispatch("click");
  for (let i = 0; i < 1e5 && step(); i++);
  return { k, n, before, ref, after: arities($, k), msg: $("ex-msg").textContent };
}

// A search the work cap stops names the arity shells it finished.
test("searchDepthNamesBound", () => {
  const work = 2000, { k, n, ref, after, msg } = searchCapped(work);
  assert.ok(ref.complete === false && ref.arity >= 2, `depth ${k} within ${n} rows stops at ${work} nodes after a whole shell`);
  assert.match(msg, /Bounded search/);
  assert.ok(msg.includes(`free arities up to ${ref.arity}`) && msg.includes(String(C.MAX_FREE_ARITY)), msg);
  assert.deepEqual(after, ref.dims);
});

// A cap inside the first shell says so, with a tree found and with none yet.
test("searchDepthNamesShellTwoBound", () => {
  for (const [work, found] of [[10, true], [1, false]]) {
    const { k, n, before, ref, after, msg } = searchCapped(work);
    assert.ok(ref.complete === false && ref.arity < 2 && !!ref.dims === found, `depth ${k} within ${n} rows stops at ${work} nodes inside shell 2`);
    assert.ok(msg.includes("Bounded search. The work cap stopped it inside the free arity 2 shell.") && msg.includes(String(C.MAX_FREE_ARITY)), msg);
    if (found) assert.deepEqual(after, ref.dims);
    else {
      assert.match(msg, new RegExp(`^No depth ${k} tree within ${n} rows`));
      assert.deepEqual(after, before, "a search with no tree leaves the tree alone");
    }
  }
});

// Guard: the pipeline count and a sweep once each took a full slice per frame, so frames ran twice the slice.
const SLICE_MS = Number(PageScripts.read("explorer-src").match(/\bSLICE_MS = (\d+)/)[1]);
test("sweepWithPipelineStaysInFrame", () => {
  const { $, flush, step } = boot();
  flush();
  tick($, "ex-pipeline", true);
  step();
  $("ex-sweep").dispatch("click");
  const ms = [];
  while (ms.length < 1e4 && /Computing/.test($("ex-readout").textContent)) {
    const t0 = performance.now();
    step();
    ms.push(performance.now() - t0);
  }
  assert.match($("ex-msg").textContent, /Sweeping/, "the sweep outlasts the pipeline count");
  const mid = ms.sort((a, b) => a - b)[ms.length >> 1];
  assert.ok(ms.length >= 5 && mid < 1.5 * SLICE_MS, `frames took ${mid.toFixed(1)} ms at the median over ${ms.length} frames, slice ${SLICE_MS} ms`);
});

// Guard: a depth search beside a pipeline count must share the slice too. At t 0.95 near the pipeline limit both take a while.
const PIPE_LIMIT = Number(PageScripts.read("explorer-src").match(/\bPIPE_LIMIT = (\d+)/)[1]);
test("searchWithPipelineStaysInFrame", () => {
  const dims = [23, 3, 8, 12, 3], T = 0.95;
  assert.ok(C.rows(dims) <= PIPE_LIMIT, `${dims} gets a pipeline count`);
  const { $, flush, step } = boot({ dims, T, s: 0.5, seed: 753 });
  flush();
  tick($, "ex-pipeline", true);
  step();
  $("ex-search").dispatch("click");
  step();
  const ms = [], both = () => /Computing/.test($("ex-readout").textContent) && /Searching/.test($("ex-msg").textContent);
  assert.ok(both(), "the search starts while the pipeline count runs");
  while (ms.length < 1e4 && both()) {
    const t0 = performance.now();
    step();
    ms.push(performance.now() - t0);
  }
  const mid = ms.sort((a, b) => a - b)[ms.length >> 1];
  assert.ok(ms.length >= 5 && mid < 1.5 * SLICE_MS, `frames took ${mid.toFixed(1)} ms at the median over ${ms.length} frames, slice ${SLICE_MS} ms`);
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

// ---- RetuneChecks: the Re-tune button applies the tidy rule at the shown N, c and t ----
const TIDY = study.tidy, TOP = study.facts.top_budget;
const enter = ($, id, v) => { const input = $(id); input.value = String(v); input.dispatch("change"); };
const target = ($, t) => { const input = $("ex-t"); input.value = String(t); input.dispatch("input"); };
const retune = ($, flush, step) => { $("ex-retune").dispatch("click"); drain(step); flush(); };
// The rule's tuple for this dataset and target within the top budget.
const ruleTuple = (N, c, t) => C.tidyTune(N, C.nearMass(N, c, TIDY), t, TOP, TIDY.gamma).dims;
const tidyRow = (n, mix, t) => TIDY?.rows.find((r) => r.n === n && r.mix === mix && r.t === t);

test("retuneLocksAfterTune", () => {
  const { $, flush, step } = boot(PINNED);
  flush();
  assert.equal($("ex-retune").disabled, false, "a fresh page can tune");
  $("ex-retune").dispatch("click");
  step();
  assert.equal($("ex-retune").disabled, true, "the button waits while the rule runs");
  drain(step);
  flush();
  assert.equal($("ex-retune").disabled, true, "a second tune at the same N, c and t would change nothing");
});

test("retuneUnlocksOnInputChange", () => {
  const { $, flush, step } = boot(PINNED);
  flush();
  retune($, flush, step);
  const locked = () => { flush(); return $("ex-retune").disabled; };
  for (const [change, back] of [
    [() => enter($, "ex-n", 2000), () => enter($, "ex-n", 1000)],
    [() => enter($, "ex-mix", 10), () => enter($, "ex-mix", 19)],
    [() => target($, 0.31), () => target($, 0.3)],
  ]) {
    change();
    assert.equal(locked(), false, "a new input unlocks the button");
    back();
    assert.equal(locked(), true, "the tuned inputs lock it again");
  }
});

// A tune started for the old inputs must not land after a change, also when the inputs come back (A to B to A).
test("retuneCancelsOnInputChange", () => {
  for (const changes of [
    [($) => enter($, "ex-n", 2000)],
    [($) => enter($, "ex-n", 2000), ($) => enter($, "ex-n", 1000)],
    [($) => enter($, "ex-mix", 10)],
    [($) => target($, 0.31), ($) => target($, 0.3)],
  ]) {
    const { $, flush, step } = boot(PINNED);
    flush();
    const before = arities($, PINNED.dims.length);
    $("ex-retune").dispatch("click");
    step();
    assert.match($("ex-msg").textContent, /Tuning/, "the tune is still running");
    for (const change of changes) change($);
    drain(step);
    flush();
    assert.deepEqual(arities($, PINNED.dims.length), before, "the stale tune leaves the tree alone");
    assert.doesNotMatch($("ex-msg").textContent, /Tidy rule tree|Tuning/);
    assert.equal($("ex-retune").disabled, false, "the cancelled tune can run again");
  }
});

// An entry that rounds or clamps to the tuned value is no change, so the tune lands.
test("retuneKeepsRunningOnSameValue", () => {
  for (const [id, v] of [["ex-n", 1000.4], ["ex-n", 500], ["ex-mix", 19.2]]) {
    const { $, flush, step } = boot(PINNED);
    flush();
    $("ex-retune").dispatch("click");
    step();
    assert.match($("ex-msg").textContent, /Tuning/, "the tune is still running");
    enter($, id, v);
    drain(step);
    flush();
    const d = ruleTuple(1000, 19, 0.3);
    assert.deepEqual(arities($, d.length), d, `${id} ${v} keeps N 1000 c 19, so the rule's tree loads`);
    assert.match($("ex-msg").textContent, /Tidy rule tree/);
  }
});

test("retuneLoadsRuleTuple", () => {
  assert.ok(TIDY, "the page embeds the tidy rule");
  for (const r of [tidyRow(1000, 19, 0.3), tidyRow(30000, 40, 0.5)]) {
    assert.ok(r, "a study row to tune for");
    const { $, flush, step } = boot(PINNED);
    flush();
    enter($, "ex-n", r.n);
    enter($, "ex-mix", r.mix);
    target($, r.t);
    flush();
    retune($, flush, step);
    const k = r.dims.length;
    assert.equal(Number(depthInput($).value), k, `N ${r.n} c ${r.mix} t ${r.t} loads a depth ${k} tree`);
    assert.deepEqual(arities($, k), r.dims, "the tree the study's rule picks");
    assert.deepEqual(ruleTuple(r.n, r.mix, r.t), r.dims, "the page rule agrees");
    assert.equal($("ex-auto").checked, false, "a tuned tree is set by hand");
    assert.equal($("ex-preset").value, "custom");
  }
});

test("retuneShowsCountsOnlyWhenMeasured", () => {
  const r = tidyRow(1000, 19, 0.3);
  assert.ok(r, "the study measured N 1000 c 19 at t 0.3");
  for (const [N, t, measured] of [[1000, 0.3, true], [1000, 0.33, false], [2000, 0.3, false]]) {
    const { $, flush, step } = boot(PINNED);
    flush();
    enter($, "ex-n", N);
    target($, t);
    flush();
    retune($, flush, step);
    const msg = $("ex-msg").textContent, d = ruleTuple(N, 19, t);
    assert.ok(msg.includes(`(${d.join(", ")})`), `the message names the tuple: ${msg}`);
    assert.equal(/Expected errors \(study\)/.test(msg), measured, `N ${N} t ${t}: ${msg}`);
    if (measured) assert.ok(shows(msg, Math.round(r.e)), `the study's ${Math.round(r.e)} expected errors: ${msg}`);
  }
});

// Guard: the rule scores every matched tree, so a cold run at t 0.95 must still yield to the frame.
test("retuneStaysResponsive", () => {
  const T = 0.95, { $, flush, step } = boot({ ...PINNED, T });
  flush();
  let worst = 0, frames = 0;
  const timed = (f) => { const t0 = performance.now(), more = f(); worst = Math.max(worst, performance.now() - t0); return more; };
  timed(() => $("ex-retune").dispatch("click"));
  while (frames < 1e5 && timed(step)) frames++;
  flush();
  assert.ok(frames >= 3, `the tune ran in ${frames} frames`);
  assert.ok(worst < FRAME_BUDGET_MS, `a tune task took ${worst.toFixed(0)} ms at t ${T}`);
  const d = ruleTuple(1000, 19, T);
  assert.deepEqual(arities($, d.length), d);
});

test("retuneInputsPersistValidated", () => {
  const { $, flush, store } = boot(PINNED);
  flush();
  const m = (N, c) => C.nearMass(N, c, TIDY).toFixed(2);
  assert.equal(String($("ex-n").value), "1000", "N opens at the study's corpus");
  assert.equal(String($("ex-mix").value), "19");
  assert.equal($("ex-m-out").textContent, m(1000, 19), "m follows N and c");
  for (const [id, v, want] of [["ex-n", 12345.6, 12346], ["ex-n", 10, 1000], ["ex-n", 1e7, 100000], ["ex-n", "x", 100000],
    ["ex-mix", 1, 2], ["ex-mix", 99, 50], ["ex-mix", 7.4, 7]]) {
    enter($, id, v);
    flush();
    assert.equal(String($(id).value), String(want), `${id} ${v} shows ${want}`);
  }
  assert.equal($("ex-m-out").textContent, m(100000, 7));
  const saved = JSON.parse([...store.values()].at(-1));
  assert.deepEqual([saved.N, saved.c], [100000, 7], "N and c are saved");
  const again = boot(saved);
  again.flush();
  assert.deepEqual([again.$("ex-n").value, again.$("ex-mix").value].map(Number), [100000, 7], "the saved N and c reopen");
  const bad = boot({ ...PINNED, N: 5, c: 3.5 });
  bad.flush();
  assert.deepEqual([bad.$("ex-n").value, bad.$("ex-mix").value].map(Number), [1000, 19], "invalid saved values fall back");
  assert.deepEqual(arities(bad.$, PINNED.dims.length), PINNED.dims, "the rest of the saved state loads");
});

test("retuneTermsDefined", () => {
  const terms = PageScripts.markup().match(/<details class="terms"[\s\S]*?<\/details>/)?.[0] || "";
  const defined = new Map([...terms.matchAll(/<dt>([\s\S]*?)<\/dt>\s*<dd>([\s\S]*?)<\/dd>/g)].map((m) => [m[1], m[2]]));
  for (const t of ["Dataset size N", "Cluster size c", "Near-pair mass m", "Tidy rule (Re-tune)", "Weight λ", "A_lo and A_hi", "Expected errors (study)"]) {
    assert.ok(defined.get(t)?.length > 20, `the terms define ${t}`);
  }
  const rule = defined.get("Tidy rule (Re-tune)");
  assert.match(rule, /3000[\s\S]*100000/, "the rule names its fitted N range");
  assert.match(rule, /\b10\b[\s\S]*\b40\b/, "the rule names its fitted c range");
});

test("pageNamesNoPrivateRepo", () => {
  assert.doesNotMatch(PageScripts.html, /superLSH|COMPSCI|compsci-753/i);
});
