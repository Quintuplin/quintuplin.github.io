// node --test scripts/sim-753/shared-ui.test.cjs (Playwright or its CLI, and installed Chrome)
const { before, after, test } = require("node:test");
const assert = require("node:assert/strict");
const { delimiter, resolve } = require("node:path");
const { readFileSync } = require("node:fs");

const binPaths = process.env.PATH.split(delimiter);
const playwright = require(require.resolve("playwright", { paths: [
  __dirname, ...binPaths.flatMap(bin => ["node_modules", "../lib/node_modules"]
    .map(dir => resolve(bin, dir, "@playwright/cli")))
]}));
const shared = resolve(__dirname, "../../simulations/753/shared");
let browser;
before(async () => { browser = await playwright.chromium.launch({channel: process.env.SIM_BROWSER_CHANNEL || "chrome"}); });
after(async () => { await browser?.close(); });

function registerFixture() {
  const spec = {
    id: "sum", title: "Running sum", code: ["total = 0", "total += first", "return total + second"],
    params: [{ key: "scale", label: "Scale", min: 1, max: 4, step: 1, value: 1 },
      { key: "sign", label: "Sign", options: ["Positive", "Negative"], value: "Positive" }],
    presets: [{ name: "Pair", base: 0 }, { name: "Offset pair", base: 12 }, { name: "Large pair", base: 84 }],
    trace(preset, params, rng) {
      const a = preset.base + Math.floor(rng() * 100000);
      preset.base = 999999; // Detect reuse of mutable preset input across runs.
      const b = params.scale * (params.sign === "Positive" ? 1 : -1);
      const nodes = [
        { id: "near", label: "Tag 64", value: 64, x: 0, y: 0, z: 2, active: true },
        { id: "far", label: "Back", x: 0, y: 0, z: -2 },
        { id: "up", label: "Upper", x: 1, y: 2, z: 1 },
        { id: "down", label: "Lower", x: 1, y: -2, z: 1 }
      ];
      const edges = [{ from: "near", to: "far", directed: true, active: true },
        { from: "far", to: "near", directed: true }, { from: "near", to: "near", directed: true }];
      const frames = [`Inputs ${a}, ${b}`, `0 + ${a} = ${a}`, `${a} + ${b} = ${a+b}`]
        .map((work,line) => ({work, line, nodes: structuredClone(nodes), edges}));
      frames[1].nodes[0].label = "Adding";
      globalThis.fixtureFrames = frames;
      return frames;
    }
  };
  Sims.register(spec);
  Sims.register({ ...spec, id: "blocks", trace() {
    const nodes = [
      { id: "low", label: "Loss", x: -1, y: -3, z: 0, shape: "bar" },
      { id: "high", label: "Gain", x: 1, y: 3, z: 0, shape: "bar" },
      { id: "slot", label: "Slot 3", x: 2, y: 0, z: 1, shape: "cell" }
    ];
    return [{line: 0, work: "3 − 3 = 0", nodes}, {line: 1, work: "Both bars meet y = 0",
      nodes: nodes.map(n => ({...n, y: 0, shape: "cell"}))}];
  } });
  Sims.register({ ...spec, id: "dense", trace() {
    const nodes = Array.from({length: 100}, (_,i) => ({id: String(i),
      label: "Long label for item " + i, x: i % 10, z: Math.floor(i / 10), y: 0, shape: "cell"}));
    return [{line: 0, work: "10 × 10 = 100", nodes}];
  } });
}

async function open(t, { id = "sum", width = 1160, source = true } = {}) {
  const page = await browser.newPage({ viewport: { width, height: 820 } });
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  await page.clock.install();
  await page.route("http://sim.test/**", route => {
    const file = new URL(route.request().url()).pathname.slice(1);
    if (!file) return route.fulfill({ contentType: "text/html", body:
      `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="stylesheet" href="player.css"><main id="sim" ${source ? 'data-source="source.js"' : ""}></main>
      <script src="renderer.js"></script><script src="player.js"></script><script src="fixture.js"></script>
      <script>Sims.boot("${id}")</script>` });
    if (file === "fixture.js") return route.fulfill({contentType: "text/javascript", body: `(${registerFixture})();`});
    if (!["renderer.js","player.js","player.css"].includes(file)) return route.fulfill({status: 404});
    return route.fulfill({contentType: file.endsWith(".css") ? "text/css" : "text/javascript", body: readFileSync(resolve(shared,file))});
  });
  await page.goto("http://sim.test/");
  return page;
}

const button = (page, name) => page.getByRole("button", { name, exact: true });
async function state(page) {
  return page.evaluate(() => ({
    count: document.querySelector("#sp-count").textContent,
    work: [...document.querySelectorAll("#sp-work span")].map(n => n.textContent),
    line: document.querySelector("#sp-list [aria-current]").textContent,
    labels: [...document.querySelectorAll(".sp-labels text")].map(n => n.textContent),
    final: !!document.querySelector(".sp-final")
  }));
}

test("one cursor reverses, replays immutable frames and stops the old timer after a new boot", async t => {
  const page = await open(t);
  const initial = await state(page);
  assert.equal(initial.count, "Step 1 of 3");
  assert.equal(initial.line, "total = 0");
  assert.ok(initial.labels.includes("Tag 64"));
  assert.ok(await button(page, "Previous").isDisabled());
  await page.evaluate(() => { fixtureFrames[1].work = "mutated"; });
  await button(page, "Step").click();
  const second = await state(page);
  assert.equal(second.work.length, 2);
  assert.match(second.work[1], /^0 \+ \d+ = \d+$/);
  assert.equal(second.line, "total += first");
  assert.ok(second.labels.includes("Adding"));
  await button(page, "Previous").click();
  assert.deepEqual(await state(page), initial);
  await page.getByLabel("Speed").selectOption("0.25");
  await button(page, "Run").click();
  await page.clock.runFor(301);
  await button(page, "Pause").click();
  await page.clock.runFor(1200);
  assert.deepEqual(await state(page), second);
  await button(page, "Step").click();
  const end = await state(page);
  assert.equal(end.work.length, 3);
  assert.ok(end.final);
  assert.ok(await button(page, "Run").isDisabled());
  await button(page, "Replay").click();
  assert.deepEqual(await state(page), initial);
  await page.clock.runFor(605);
  assert.deepEqual(await state(page), end);
  await button(page, "Replay").click();
  await page.evaluate(() => { Sims.boot("blocks"); Sims.boot("sum"); });
  await page.clock.runFor(1400);
  assert.deepEqual(await state(page), initial);
});

test("preset, both parameter kinds and seed rebuild the input, randomize retains the preset", async t => {
  const page = await open(t);
  const initial = await state(page);
  const seed = page.getByLabel("Seed", {exact: true});
  const preset = page.getByLabel("Data preset");
  await button(page, "Step").click();
  await preset.selectOption("1");
  const offset = await state(page);
  assert.equal(offset.count, "Step 1 of 3");
  assert.notDeepEqual(offset.work, initial.work);
  await seed.fill("99"); await seed.press("Enter");
  assert.notDeepEqual((await state(page)).work, offset.work);
  await seed.fill("753"); await seed.press("Enter");
  assert.deepEqual(await state(page), offset);
  const scale = page.getByLabel("Scale");
  await scale.fill("3"); await scale.press("Enter");
  await page.getByLabel("Sign").selectOption("Negative");
  assert.match((await state(page)).work[0], /, -3$/);
  await button(page, "Randomize").click();
  assert.notEqual(await seed.inputValue(), "753");
  assert.equal(await preset.inputValue(), "1");
  assert.equal((await state(page)).count, "Step 1 of 3");
});

for (const [invalid, label, alternative] of [["", "Data preset", "1"], ["4294967296", "Sign", "Negative"]]) {
  test(`changing ${label} with an invalid seed restores and runs the last valid seed`, async t => {
    const page = await open(t);
    const seed = page.getByLabel("Seed", {exact: true});
    const control = page.getByLabel(label);
    const original = await control.inputValue();
    await seed.fill("427");
    await seed.press("Enter");
    await control.selectOption(alternative);
    const expected = await state(page);
    await control.selectOption(original);
    await seed.fill(invalid);
    await control.selectOption(alternative);
    assert.equal(await seed.inputValue(), "427");
    assert.deepEqual(await state(page), expected);
  });
}

test("point projection preserves signed height and depth, hover and camera controls work", async t => {
  const page = await open(t);
  const dots = page.locator("circle.sp-dot");
  const order = await dots.evaluateAll(nodes => nodes.map(n => n.dataset.node));
  assert.ok(order.indexOf("far") < order.indexOf("near"));
  const coords = () => dots.evaluateAll(nodes => Object.fromEntries(nodes.map(n =>
    [n.dataset.node, ["cx","cy","r"].map(k => Number(n.getAttribute(k)))])));
  const start = await coords();
  assert.ok(start.up[1] < start.down[1]);
  assert.ok(start.near[2] > start.far[2]);
  assert.equal(await page.locator(".sp-edge[marker-end]").count(), 3);
  await page.locator('circle[data-node="near"]').hover();
  assert.match(await page.locator("#sp-info").innerText(), /Tag 64 · value 64.*z 2/);
  const world = page.locator(".sp-world");
  await world.press("ArrowLeft");
  assert.notDeepEqual(await coords(), start);
  await world.press("Home");
  assert.deepEqual(await coords(), start);
  await button(page, "Zoom in").click();
  assert.notDeepEqual(await coords(), start);
  await button(page, "Reset view").click();
  const plot = await world.boundingBox();
  await page.mouse.move(plot.x + 12, plot.y + 12);
  await page.mouse.down();
  await page.mouse.move(plot.x + 90, plot.y + 45);
  await page.mouse.up();
  assert.notDeepEqual(await coords(), start);
  await button(page, "Reset view").click();
  assert.deepEqual(await coords(), start);
});

test("solid slots and signed bars have projected faces extending to the zero plane", async t => {
  const page = await open(t, {id: "blocks"});
  for (const id of ["low","high","slot"]) {
    assert.equal(await page.locator(`polygon[data-node="${id}"]`).count(), 6);
  }
  const vertices = id => page.locator(`polygon[data-node="${id}"]`).evaluateAll(faces =>
    [...new Set(faces.flatMap(f => [...f.points].map(p => p.x + "," + p.y)))]);
  const bars = [await vertices("low"), await vertices("high")];
  assert.equal(await page.locator('.sp-labels [data-node="slot"]').textContent(), "Slot 3");
  await button(page, "Step").click();
  for (const [i,id] of ["low","high"].entries()) {
    const zeroCell = await vertices(id);
    const base = bars[i].filter(p => zeroCell.includes(p));
    const tip = bars[i].filter(p => !zeroCell.includes(p));
    assert.equal(base.length, 4, "base corners coincide with a cell at zero");
    assert.equal(tip.length, 4);
    const meanY = corners => corners.reduce((sum,p) => sum + Number(p.split(",")[1]), 0) / corners.length;
    assert.ok(id === "low" ? meanY(tip) > meanY(base) : meanY(tip) < meanY(base));
  }
});

test("notebook and pseudocode share the desktop right column and stack below the scene on phones", async t => {
  const page = await open(t);
  const boxes = () => Promise.all([".sp-graph",".sp-paper",".sp-code"].map(s => page.locator(s).boundingBox()));
  let [graph, paper, code] = await boxes();
  assert.ok(code.x >= graph.x + graph.width - 1 && paper.x >= graph.x + graph.width - 1);
  assert.ok(code.y >= paper.y + paper.height - 1 && graph.y + graph.height >= code.y + code.height - 1);
  assert.equal(await page.getByRole("heading", {name: "Algorithm pseudocode"}).count(), 1);
  assert.equal(await page.getByRole("link", {name: "JavaScript source"}).getAttribute("href"), "source.js");
  await page.setViewportSize({width: 350, height: 740});
  [graph, paper, code] = await boxes();
  assert.ok(paper.y >= graph.y + graph.height - 1 && code.y >= paper.y + paper.height - 1);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
});

test("reservoir SVG labels expose both tags and sighting numbers after replacement", async t => {
  const page = await open(t);
  await page.addScriptTag({path: resolve(shared, "../domains/streams.js")});
  await page.evaluate(() => Sims.boot("reservoir-sampling"));
  for (let i = 0; i < 4; i++) await button(page, "Step").click();
  for (const label of ["S1: 60 (#1)", "S2: 64 (#3)"]) {
    assert.ok(await page.locator(".sp-labels").getByText(label, {exact: true}).isVisible(), label);
  }
  assert.match(await page.locator("#sp-work li").last().innerText(), /tag 60 → 64.*#2 → #3/);
});

test("dense slots fit the viewport and expose omitted labels in the accessible data view", async t => {
  const page = await open(t, {id: "dense", width: 360, source: false});
  assert.match(await page.getByRole("link", {name: "JavaScript source"}).getAttribute("href"), /fixture\.js$/);
  const result = await page.locator(".sp-world").evaluate(scene => {
    const bounds = scene.getBoundingClientRect();
    const inside = r => r.left >= bounds.left && r.right <= bounds.right && r.top >= bounds.top && r.bottom <= bounds.bottom;
    const boxes = [...scene.querySelectorAll(".sp-labels text")].map(n => n.getBoundingClientRect());
    return { fit: [...scene.querySelectorAll("polygon")].every(n => inside(n.getBoundingClientRect())),
      count: boxes.length, clear: boxes.every((r,i) => inside(r) && boxes.slice(i+1).every(o =>
        r.left >= o.right || r.right <= o.left || r.top >= o.bottom || r.bottom <= o.top)) };
  });
  assert.ok(result.fit && result.clear);
  assert.ok(result.count > 0 && result.count < 100);
  await page.getByText("Scene data", {exact: true}).click();
  assert.equal(await page.locator("#sp-data li").count(), 100);
  assert.match(await page.locator("#sp-data").innerText(), /Long label for item 99/);
});
