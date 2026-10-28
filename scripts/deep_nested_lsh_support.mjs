// Page scripts, study data and helpers shared by the Deep Nested LSH checks (#31). Each check takes the page as its argument.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import vm from "node:vm";

const PAGE = process.argv[2];
if (!PAGE) throw new Error(`usage: node ${basename(process.argv[1])} <page>`);

export const PageScripts = {
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

// ---- StudyFixtures: the page maths and its embedded study ----
vm.runInThisContext(PageScripts.read("cascade-src"), { filename: "cascade-src" });
export const C = globalThis.Cascade;
export const study = JSON.parse(PageScripts.read("sim-data"));
export const MAX_DEPTH = study.provenance.grid.max_depth, PAIRS = study.facts.corpus?.pairs;
export const SEARCH_WORK = Number(PageScripts.read("explorer-src").match(/\bSEARCH_WORK = ([\d.e]+)/)?.[1]);

// ---- SharedHelpers ----
export const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const counts = (d, t) => C.expectedCounts((s) => C.curve(s, d), PAIRS, t);
export const tablesOf = (...kinds) => Object.values(study.tables).filter((t) => kinds.includes(t.kind));

// Runs a search to its end and fails once it takes more than maxSteps steps.
export function drainSearch(gen, maxSteps) {
  for (let steps = 0; ; steps++) {
    const r = gen.next();
    if (r.done) return r.value;
    assert.ok(steps < maxSteps, `the search ran past ${maxSteps} steps`);
  }
}

// Trial pairs: two sets at the corpus median size over the corpus vocabulary.
export const PAIR = { size: study.facts.corpus.set_median, vocab: study.facts.corpus.vocab };
export const realised = (s) => { const U = Math.round((2 * PAIR.size) / (1 + s)); return { U, I: Math.round(s * U) }; };

// Accept at quorum, alone or behind retrieval on the kept bands.
export const quorumTable = study.tables.lsh_quorum_table;
export const retrievalOf = (d) => [d[0], C.tails(d)[1]];
const quorumMemo = new Map();
export const quorumCounts = (n, t, index) => {
  const k = `${n}|${t}|${index}`;
  if (!quorumMemo.has(k)) quorumMemo.set(k, C.expectedCounts((s) => C.quorumCurve(s, n, t, index), PAIRS, t));
  return quorumMemo.get(k);
};
// Verify rows of the quorum table with the equal-rows tree whose kept bands they retrieve through.
export const verifyRows = () => quorumTable.rows.filter((r) => Array.isArray(r.retrieval)).map((r) => ({ r,
  d: tablesOf("equal_rows").filter((t) => t.target === r.target).flatMap((t) => t.rows)
    .find((x) => x.rows === r.rows && same(retrievalOf(x.dims), r.retrieval))?.dims }));
