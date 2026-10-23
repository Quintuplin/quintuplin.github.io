// Behaviour checks for the fridge simulation page (#26). Usage: node check_fridge.mjs <page>
import { readFileSync } from "node:fs";
import vm from "node:vm";

const noop2d = new Proxy({}, { get: () => () => {}, set: () => true });
const INIT = { ev: { value: "1" }, tilt: { value: "0" }, fill: { value: "60" }, tt: { value: "0" }, ot: { checked: true } };

// A select-like element stub. The first added option becomes the value, as in the DOM.
function element(init = {}) {
  return {
    value: "", checked: false, textContent: "", innerHTML: "", className: "", clientWidth: 600, clientHeight: 450,
    add(o) { if (this.value === "") this.value = o.value; },
    appendChild() {}, getContext: () => noop2d, ...init,
  };
}

const FridgeHarness = {
  // Runs the page's inline script in a stubbed context. get(expr) reads its script-scope bindings.
  loadPage(path) {
    const script = readFileSync(path, "utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
    const els = {};
    const document = {
      activeElement: null,
      getElementById: (id) => (els[id] ??= element(INIT[id])),
      createElement: () => element({ firstChild: element() }),
      documentElement: {},
    };
    const ctx = vm.createContext({
      document, window: {}, performance: { now: () => 0 },
      Option: function (text, value) { this.text = text; this.value = String(value); },
      getComputedStyle: () => ({ getPropertyValue: () => "" }),
      matchMedia: () => ({ addEventListener() {} }),
      MutationObserver: class { observe() {} },
      requestAnimationFrame: () => 0,
    });
    vm.runInContext(script, ctx);
    return { els, document, get: (expr) => vm.runInContext(expr, ctx) };
  },
};

const inside = (p, W, H) => p[0] >= 0 && p[0] <= W && p[1] >= 0 && p[1] <= H;

function fitsCanvas(page) {
  const sizes = [[342, 256], [783, 579], [1100, 700], [1180, 880], [400, 900], [1400, 300]];
  return sizes.filter(([W, H]) => {
    Object.assign(page.els.world, { clientWidth: W, clientHeight: H });
    page.get("draw()");
    const pts = page.get("[0, S.W].flatMap(x => [0, S.D].flatMap(y => [0, S.H].map(z => [x, y, z]))).concat(doorCorners(S.door_max)).map(proj)");
    return !pts.every((p) => inside(p, W, H));
  }).map(([W, H]) => `cabinet or open door clipped at ${W}x${H}`);
}

// Fires one wheel step and reports whether it was claimed and whether the view zoomed.
function wheel(page, ctrlKey, focused) {
  page.document.activeElement = focused ? page.els.world : null;
  const before = JSON.stringify(page.get("proj([0, 0, 0])"));
  let prevented = false;
  page.els.world.onwheel({ deltaY: -100, ctrlKey, preventDefault: () => { prevented = true; } });
  return { prevented, zoomed: JSON.stringify(page.get("proj([0, 0, 0])")) !== before };
}

function wheelPassesThrough(page) {
  const errors = [];
  const plain = wheel(page, false, false);
  if (plain.prevented || plain.zoomed) errors.push("plain wheel over the world view traps page scroll or zooms");
  for (const [name, ctrl, focus] of [["Ctrl", true, false], ["focused", false, true]]) {
    const r = wheel(page, ctrl, focus);
    if (!r.prevented || !r.zoomed) errors.push(`${name} wheel does not zoom the world view`);
  }
  return errors;
}

function defaultMultiCam(page) {
  const n = page.get("S.layouts[+document.getElementById('lay').value].cams.length");
  return n >= 2 ? [] : [`default config has ${n} camera`];
}

function timeZeroNotStarted(page) {
  const kv = page.els.kv.innerHTML;
  const colours = [...kv.matchAll(/color:([^;"]+)/g)].map((m) => m[1].trim());
  const errors = [];
  if (!/<b>phase<\/b><span>not started<\/span>/.test(kv)) errors.push("phase at time zero is not \"not started\"");
  if (!colours.length || colours.some((c) => c !== "var(--muted)")) errors.push(`ghosts at time zero use ${colours.join(", ")}`);
  return errors;
}

const CHECKS = { timeZeroNotStarted, defaultMultiCam, fitsCanvas, wheelPassesThrough };

function main(path) {
  let fail = 0;
  for (const [name, check] of Object.entries(CHECKS)) {
    const errors = check(FridgeHarness.loadPage(path));
    errors.forEach((e) => console.error(`FAIL: ${name}: ${e}`));
    fail ||= errors.length;
  }
  if (!fail) console.log("fridge check passed");
  process.exitCode = fail ? 1 : 0;
}

if (!process.argv[2]) throw new Error("usage: node check_fridge.mjs <page>");
main(process.argv[2]);
