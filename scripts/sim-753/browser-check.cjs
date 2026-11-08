// node scripts/sim-753/browser-check.cjs SITE_ROOT [http://127.0.0.1:PORT/]
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { chromium } = require(process.env.PLAYWRIGHT_CORE || "playwright-core");

const course = "simulations/753/";
const desktop = { width: 1360, height: 900 };
const mobile = { width: 375, height: 812 };
const type = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".png": "image/png", ".woff2": "font/woff2" };

async function serve(root) {
  const server = http.createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
      if (!/^\/(simulations\/753\/|projects\/|assets\/)/.test(pathname) ||
          pathname.split(/[\\/]/).some(part => part.startsWith("."))) {
        res.writeHead(404).end();
        return;
      }
      let file = path.resolve(root, "." + pathname);
      if ((await fs.stat(file)).isDirectory()) file = path.join(file, "index.html");
      const relative = path.relative(root, await fs.realpath(file));
      if (relative.startsWith("..") || path.isAbsolute(relative)) throw Error("Outside site");
      const body = await fs.readFile(file);
      res.writeHead(200, { "Content-Type": type[path.extname(file)] || "application/octet-stream" }).end(body);
    } catch {
      res.writeHead(404).end();
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server;
}

async function readSpecs(root) {
  const dir = path.join(root, course, "domains"), specs = new Map();
  for (const file of (await fs.readdir(dir)).filter(f => f.endsWith(".js")).sort()) {
    vm.runInNewContext(await fs.readFile(path.join(dir, file), "utf8"), {
      structuredClone, Sims: { register(spec) {
        assert.ok(!specs.has(spec.id), "Duplicate registration " + spec.id);
        specs.set(spec.id, { spec, file });
      } }
    }, { filename: file });
  }
  assert.ok(specs.size, "No local simulation specs");
  return specs;
}

// Reproduce the player's seed stream so expected work and lines come from the
// domain contract independently of the notebook, highlights and renderer.
function trace(spec, seed, preset = 0, changes = {}) {
  let state = seed >>> 0;
  const rng = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let bits = Math.imul(state ^ (state >>> 15), state | 1);
    bits ^= bits + Math.imul(bits ^ (bits >>> 7), bits | 61);
    return ((bits ^ (bits >>> 14)) >>> 0) / 4294967296;
  };
  const params = Object.fromEntries(spec.params.map(p => [p.key, p.value]));
  return spec.trace(structuredClone(spec.presets[preset]), { ...params, ...changes }, rng);
}

async function catalog(page, base, specs) {
  const index = new URL(course + "index.html", base).href;
  await page.goto(index);
  const links = await page.locator(".lab-list a").evaluateAll(as => as.map(a => [a.href, a.textContent.trim()]));
  assert.equal(links.length, specs.size, "Catalog link count");
  const registry = new Map(links);
  for (const { spec } of specs.values()) {
    assert.equal(registry.get(new URL(spec.id + "/index.html", index).href), spec.title, spec.id + " catalog entry");
  }
  const broken = await page.locator('a[href^="#"]').evaluateAll(as => as.filter(a =>
    !document.getElementById(decodeURIComponent(a.hash.slice(1)))).map(a => a.hash));
  assert.deepEqual(broken, [], "Broken course topic links");
  return index;
}

async function inspect(page, spec, frames, index) {
  const state = await page.evaluate(() => {
    const current = '[aria-current="step"]';
    const list = document.querySelector("#sp-list"), work = document.querySelector("#sp-work");
    return {
      count: document.querySelector("#sp-count").textContent,
      line: document.querySelector("#sp-line").textContent,
      code: [...list.children].flatMap((li, i) => li.matches(current) ? [i] : []),
      current: [...work.children].flatMap((li, i) => li.matches(current) ? [i] : []),
      notebook: [...work.children].map(li => li.textContent),
      scene: [...new Set([...document.querySelectorAll("#sp-plot :is(circle,polygon)[data-node]")].map(n => n.dataset.node))].sort(),
      previousDisabled: document.querySelector("#sp-prev").disabled,
      nextDisabled: document.querySelector("#sp-next").disabled
    };
  });
  const expected = frames[index];
  assert.equal(state.count, `Step ${index + 1} of ${frames.length}`);
  assert.equal(state.line, "Line " + (expected.line + 1));
  assert.deepEqual(state.code, [expected.line], "Incorrect highlighted code");
  assert.deepEqual(state.current, [index], "Incorrect highlighted notebook entry");
  assert.deepEqual(state.notebook, Array.from(frames.slice(0, index + 1), f => f.work), "Cumulative notebook");
  assert.deepEqual(state.scene, Array.from(expected.nodes, n => n.id).sort(), "Rendered node IDs");
  assert.equal(state.previousDisabled, index === 0);
  assert.equal(state.nextDisabled, index === frames.length - 1);
  assert.ok(spec.code[expected.line]);
}

// Take actual Step actions in one browser round trip for longer traces.
async function advance(page, count) {
  await page.locator("#sp-next").evaluate((button, n) => {
    for (let i = 0; i < n; i++) {
      if (button.disabled) throw Error("Step disabled before expected frame");
      button.click();
    }
  }, count);
}

async function geometry(page) {
  return page.locator("#sp-plot :is(circle,polygon)[data-node]").evaluateAll(nodes => nodes.map(n =>
    [n.dataset.node, n.getAttribute("points") ?? [n.getAttribute("cx"), n.getAttribute("cy")].join(",")].join("=")).sort());
}

async function layout(page, narrow) {
  const rects = await page.evaluate(() => {
    const box = css => document.querySelector(css).getBoundingClientRect().toJSON();
    return { graph: box(".sp-graph"), paper: box(".sp-paper"), code: box(".sp-code"),
      width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth };
  });
  const { graph, paper, code } = rects;
  assert.ok(rects.scroll <= rects.width + 1, `Page scroll width ${rects.scroll} exceeds viewport ${rects.width}`);
  assert.ok(graph.width > 0 && code.width > 0 && paper.height > 0);
  if (narrow) assert.ok(graph.bottom <= paper.top + 1, "Mobile notebook should follow the scene");
  else assert.ok(graph.right <= Math.min(paper.left, code.left) + 1, "Desktop scene should be left of both panels");
  assert.ok(paper.bottom <= code.top + 1, "Notebook should be above the code");
}

async function orbit(page, pointer) {
  const svg = page.locator("#sp-plot svg");
  await svg.scrollIntoViewIfNeeded();
  const count = await page.locator("#sp-count").textContent();
  const before = await geometry(page);
  assert.ok(before.length, "Orbit needs projected geometry");
  if (pointer) {
    const { x, y, width, height } = await svg.boundingBox();
    await page.mouse.move(x + 4, y + 4);
    await page.mouse.down();
    await page.mouse.move(x + width / 4, y + height / 5, { steps: 4 });
    await page.mouse.up();
  } else {
    await svg.press("ArrowRight");
  }
  assert.notDeepEqual(await geometry(page), before, "Orbit did not move projected scene geometry");
  assert.equal(await page.locator("#sp-count").textContent(), count, "Orbit changed step");
  await svg.press("Home");
  assert.deepEqual(await geometry(page), before, "Home did not restore projection");
}

function firstDifference(a, b) {
  // Ignore a seed field or input widget value. Compare the trace delivered to the learner.
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (JSON.stringify(a[i]) !== JSON.stringify(b[i])) return i;
  }
  return a.length === b.length ? -1 : 0;
}

async function setInput(input, value) {
  await input.fill(String(value));
  await input.press("Tab");
}

async function inspectSceneData(page, frame) {
  await page.locator("#sp-details summary").click();
  const rows = page.locator("#sp-data li");
  await rows.first().waitFor({ state: "attached" });
  const lines = await rows.allTextContents();
  for (const n of frame.nodes) {
    const coords = `(x ${n.x}, y ${n.y}, z ${n.z})`;
    assert.ok(lines.some(s => s.startsWith(n.label) && s.includes(coords) &&
      (n.value === undefined || s.includes(" · value " + n.value)) && s.endsWith(" · active") === !!n.active),
    "Scene data for " + n.id);
  }
  const labels = new Map(frame.nodes.map(n => [n.id, n.label]));
  for (const e of frame.edges || []) {
    assert.ok(lines.includes(labels.get(e.from) + (e.directed ? " → " : " ↔ ") + labels.get(e.to) +
      (e.active ? " · active" : "")), "Scene edge " + e.from + " to " + e.to);
  }
  await page.locator("#sp-details summary").click();
}

async function verifyChange(page, spec, frames, changed, index) {
  assert.ok(index >= 0, "Expected a changed trace");
  await inspect(page, spec, changed, 0);
  if (index) await advance(page, index);
  await inspect(page, spec, changed, index);
  // Scene values and positions can change even when the notebook string is identical.
  if (frames[index]?.work === changed[index].work && frames.length === changed.length) {
    await inspectSceneData(page, changed[index]);
  }
}

async function checkInputs(page, spec, seed, frames) {
  const preset = page.locator("#sp-preset");
  const original = await preset.inputValue();
  let changedSeed, changed, index;
  // Discrete generators can legitimately draw the same small input twice.
  for (let attempt = 0; attempt < 16; attempt++) {
    await page.getByRole("button", { name: "Randomize", exact: true }).click();
    const nextSeed = Number(await page.locator("#sp-seed").inputValue());
    assert.notEqual(nextSeed, changedSeed ?? seed, "Randomize did not reseed");
    changedSeed = nextSeed;
    assert.equal(await preset.inputValue(), original, "Randomize switched presets");
    changed = trace(spec, changedSeed);
    index = firstDifference(frames, changed);
    if (index >= 0) break;
  }
  await verifyChange(page, spec, frames, changed, index);
  await setInput(page.locator("#sp-seed"), seed);
  await inspect(page, spec, frames, 0);
  if (index === 0 && frames[0].work === changed[0].work) await inspectSceneData(page, frames[0]);
  const replayStep = Math.max(1, index);
  await advance(page, replayStep);
  await inspect(page, spec, frames, replayStep);
  if (index > 0 && frames[index].work === changed[index].work) await inspectSceneData(page, frames[index]);

  for (const [i, p] of spec.params.entries()) {
    const values = p.options ?? [p.min, p.max];
    for (const value of values) {
      if (value === p.value) continue;
      const altered = trace(spec, seed, 0, { [p.key]: value });
      const difference = firstDifference(frames, altered);
      if (difference < 0) continue;
      const control = page.locator("#sp-params :is(input,select)").nth(i);
      if (p.options) await control.selectOption(value);
      else await setInput(control, value);
      await verifyChange(page, spec, frames, altered, difference);
      return;
    }
  }
  assert.fail("No control changed the default preset trace for " + spec.id);
}

async function playback(page, spec, frames) {
  assert.ok(frames.length >= 3, "Run/pause needs at least three steps");
  const run = page.locator("#sp-run"), speed = page.locator("#sp-speed");
  await speed.selectOption({ label: "0.5×" });
  await run.press("Enter");
  assert.match(await run.innerText(), /Pause/);
  await page.clock.runFor(700);
  await inspect(page, spec, frames, 0);
  await speed.selectOption({ label: "4×" });
  await page.clock.runFor(310);
  await inspect(page, spec, frames, 1);
  await run.press("Enter");
  assert.match(await run.innerText(), /Run/);
  await page.clock.runFor(1300);
  await inspect(page, spec, frames, 1);
  await page.locator("#sp-replay").press("Enter");
  await inspect(page, spec, frames, 0);
  assert.match(await run.innerText(), /Pause/);
  await page.clock.runFor(310);
  await run.press("Enter");
  await inspect(page, spec, frames, 1);
}

async function route(page, index, entry, fileMode, detailed) {
  const { spec, file } = entry;
  const url = new URL(spec.id + "/index.html", index).href;
  await page.setViewportSize(desktop);
  await page.goto(url);
  assert.ok((await page.title()).includes(spec.title), "Document title");
  assert.equal(await page.locator("h1").innerText(), spec.title);
  assert.equal(await page.locator(".catalog-link").evaluate(a => a.href), index, "Return link");
  const source = new URL("domains/" + file, index).href;
  assert.equal(await page.locator(".sp-source").evaluate(a => a.href), source, "Source link");
  assert.ok(await page.locator("script[src]").evaluateAll((scripts, url) => scripts.some(s => s.src === url), source));
  const preset = page.getByRole("combobox", { name: /^Data preset/ });
  assert.ok(spec.presets.length >= 3, "Too few presets");
  assert.deepEqual(await preset.locator("option").allTextContents(), Array.from(spec.presets, p => p.name));
  assert.deepEqual(await page.locator("#sp-list code").allTextContents(), Array.from(spec.code));
  const controls = page.locator("#sp-params :is(input,select)");
  assert.equal(await controls.count(), spec.params.length, "Parameter count");
  for (const [i, p] of spec.params.entries()) {
    const control = controls.nth(i);
    assert.equal(await control.evaluate(el => el.labels[0].firstChild.textContent.trim()), p.label);
    assert.equal(await control.inputValue(), String(p.value));
    if (p.options) assert.deepEqual(await control.locator("option").allTextContents(), Array.from(p.options));
    else for (const attr of ["min", "max", "step"]) assert.equal(await control.getAttribute(attr), String(p[attr]));
  }
  for (const name of ["Randomize", "Run", "Step", "Previous", "Replay", "Reset view"]) {
    assert.ok(await page.getByRole("button", { name, exact: true }).isVisible(), name + " control");
  }
  assert.ok(await page.getByRole("combobox", { name: /^Speed/ }).isVisible());
  await layout(page, false);
  const seed = Number(await page.getByLabel("Seed", { exact: true }).inputValue());
  const frames = trace(spec, seed);
  await inspect(page, spec, frames, 0);
  await page.locator("#sp-next").press("Enter");
  await inspect(page, spec, frames, 1);
  await page.locator("#sp-prev").press("Enter");
  await inspect(page, spec, frames, 0);
  if (fileMode) {
    await orbit(page, false);
    await checkInputs(page, spec, seed, frames);
  } else {
    if (detailed) {
      await orbit(page, true);
      await playback(page, spec, frames);
      for (let i = 1; i < spec.presets.length; i++) {
        await preset.selectOption({ index: i });
        await inspect(page, spec, trace(spec, seed, i), 0);
      }
      await preset.selectOption({ index: 0 });
    }
    // Exercise the end boundary once per page, without waiting for animation timers.
    await advance(page, frames.length - 1);
    await inspect(page, spec, frames, frames.length - 1);
    assert.ok(await page.locator("#sp-run").isDisabled(), "Run enabled at final step");
    await page.setViewportSize(mobile);
    await layout(page, true);
  }
}

async function main() {
  const [, , rootArg, httpArg] = process.argv;
  assert.ok(rootArg && process.argv.length <= 4, "Usage: node browser-check.cjs SITE_ROOT [LOCAL_HTTP_URL]");
  const root = await fs.realpath(rootArg);
  const specs = await readSpecs(root);
  const fileBase = pathToFileURL(root + path.sep);
  const supplied = httpArg && new URL(httpArg.endsWith("/") ? httpArg : httpArg + "/");
  if (supplied) assert.ok(supplied.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(supplied.hostname),
    "Expected a loopback HTTP site root");
  let server, browser;
  try {
    if (!supplied) server = await serve(root);
    const httpBase = supplied || new URL(`http://127.0.0.1:${server.address().port}/`);
    browser = await chromium.launch(process.env.EDGE_EXECUTABLE
      ? { executablePath: process.env.EDGE_EXECUTABLE } : { channel: "msedge" });
    const failures = [];
    for (const base of [fileBase, httpBase]) {
      const context = await browser.newContext({ viewport: desktop });
      const page = await context.newPage();
      page.setDefaultTimeout(5000);
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {
        if (message.type() === "error" && !message.text().startsWith("Failed to load resource")) {
          errors.push(message.text());
        }
      });
      page.on("requestfailed", req => {
        if (["script", "stylesheet"].includes(req.resourceType())) errors.push(req.url() + " " + req.failure()?.errorText);
      });
      page.on("response", res => {
        if (res.status() >= 400 && ["script", "stylesheet"].includes(res.request().resourceType())) {
          errors.push(res.status() + " " + res.url());
        }
      });
      await page.clock.install({ time: new Date("2026-01-01T00:00:00Z") });
      await page.clock.pauseAt(new Date("2026-01-01T01:00:00Z"));
      const index = await catalog(page, base, specs);
      assert.deepEqual(errors, [], index);
      const topics = new Set();
      for (const entry of specs.values()) {
        const label = base.protocol + " " + entry.spec.id;
        errors.length = 0;
        try {
          await route(page, index, entry, base.protocol === "file:", !topics.has(entry.spec.topic));
          topics.add(entry.spec.topic);
          assert.deepEqual(errors, [], label + " browser errors");
          console.log("PASS " + label);
        } catch (error) {
          const reason = label + " — " + error.message + (errors.length ? "\n" + errors.join("\n") : "");
          failures.push(reason);
          console.error("FAIL " + reason);
        }
      }
      if (base.protocol === "http:") {
        await page.goto(new URL("projects/index.html", base).href);
        const hrefs = await page.locator("a[href]").evaluateAll(as => as.map(a => a.href));
        assert.ok(hrefs.includes(index), "Projects has no link to the local course directory");
      }
      await context.close();
    }
    assert.equal(failures.length, 0, failures.length + " failed route checks");
    console.log(`Checked ${specs.size} catalog pages over file and HTTP.`);
  } finally {
    try { await browser?.close(); }
    finally { if (server) await new Promise(resolve => server.close(resolve)); }
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
