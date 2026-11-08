(() => {
  "use strict";

  const catalog = new Map();
  let dispose;

  function seeded(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state + 0x6d2b79f5) >>> 0;
      let bits = Math.imul(state ^ (state >>> 15), state | 1);
      bits ^= bits + Math.imul(bits ^ (bits >>> 7), bits | 61);
      return ((bits ^ (bits >>> 14)) >>> 0) / 4294967296;
    };
  }

  function element(tag, text) {
    const el = document.createElement(tag);
    el.textContent = text;
    return el;
  }

  function boot(id) {
    const entry = catalog.get(id);
    if (!entry) throw new Error("Unknown simulation: " + id);
    const { spec } = entry;
    dispose?.();
    const root = document.getElementById("sim");
    root.classList.add("sp-player");
    root.innerHTML = `
      <section class="sp-settings" aria-label="Simulation inputs">
        <label>Data preset<select id="sp-preset"></select></label>
        <div class="sp-seed"><label>Seed<input id="sp-seed" type="number" value="753" min="0" max="4294967295" step="1" required></label>
          <button id="sp-random" type="button">Randomize</button></div>
        <div id="sp-params"></div>
      </section>
      <div class="sp-console">
        <div class="sp-transport" role="group" aria-label="Playback">
          <button id="sp-run"><span aria-hidden="true">▶</span> Run</button>
          <button id="sp-prev">Previous</button><button id="sp-next">Step</button><button id="sp-replay">Replay</button>
          <label>Speed <select id="sp-speed"><option value="2">0.5×</option><option value="1" selected>1×</option><option value="0.5">2×</option><option value="0.25">4×</option></select></label>
          <div id="sp-count" role="status"></div>
        </div>
        <div class="sp-desk">
          <section class="sp-graph" aria-labelledby="sp-graph-heading">
            <div class="sp-graph-head"><h2 id="sp-graph-heading">3D view</h2>
              <div role="group" aria-label="Camera"><button id="sp-out" aria-label="Zoom out">−</button><button id="sp-in" aria-label="Zoom in">+</button><button id="sp-reset">Reset view</button></div>
            </div>
            <div id="sp-plot"></div>
            <div id="sp-info"></div>
            <details id="sp-details"><summary>Scene data</summary><div id="sp-data"></div></details>
          </section>
          <section class="sp-paper" aria-labelledby="sp-work-heading">
            <h2 id="sp-work-heading">Working notebook</h2>
            <div id="sp-sheets" tabindex="0" role="region" aria-label="Calculations through the current step"><ol id="sp-work"></ol></div>
          </section>
          <section class="sp-code" aria-labelledby="sp-code-heading">
            <div><h2 id="sp-code-heading">Algorithm pseudocode</h2><span id="sp-line"></span></div>
            <ol id="sp-list" tabindex="0" aria-label="Algorithm code"></ol>
          </section>
        </div>
      </div>`;
    const get = name => root.querySelector("#sp-" + name);
    const source = root.dataset.source || entry.source;
    if (source) {
      const link = element("a", "JavaScript source");
      link.href = source;
      link.className = "sp-source";
      get("list").after(link);
    }
    const preset = get("preset"), seed = get("seed"), speed = get("speed");
    const work = get("work"), sheets = get("sheets"), code = get("list");
    const run = get("run"), previous = get("prev"), next = get("next");
    const renderer = globalThis.SimsRenderer.create(get("plot"), get("info"));
    let frames, cursor, timer, activeLine;
    const params = {};
    preset.replaceChildren(...spec.presets.map((p, i) => new Option(p.name, String(i))));
    code.replaceChildren(...spec.code.map(s => {
      const row = document.createElement("li");
      row.append(element("code", s));
      return row;
    }));

    function pause() {
      clearInterval(timer);
      timer = undefined;
      run.innerHTML = '<span aria-hidden="true">▶</span> Run';
    }

    function describeScene() {
      const selected = frames[cursor];
      const names = new Map(selected.nodes.map(n => [n.id, n.label]));
      const lines = selected.nodes.map(n => globalThis.SimsRenderer.describe(n));
      for (const e of selected.edges || []) {
        lines.push(`${names.get(e.from)} ${e.directed ? "→" : "↔"} ${names.get(e.to)}${e.active ? " · active" : ""}`);
      }
      const list = document.createElement("ul");
      list.append(...lines.map(s => element("li", s)));
      get("data").replaceChildren(list);
    }

    function show(index) {
      cursor = index;
      const frame = frames[cursor], last = cursor === frames.length - 1;
      if (last) pause();
      previous.disabled = cursor === 0;
      next.disabled = run.disabled = last;
      get("count").textContent = `Step ${cursor + 1} of ${frames.length}`;
      get("line").textContent = `Line ${frame.line + 1}`;
      activeLine?.removeAttribute("aria-current");
      activeLine = code.children[frame.line];
      activeLine.setAttribute("aria-current", "step");
      const offset = activeLine.offsetTop;
      if (offset < code.scrollTop || offset + activeLine.offsetHeight > code.scrollTop + code.clientHeight) {
        code.scrollTop = offset - code.clientHeight / 2;
      }
      while (work.children.length > cursor + 1) work.lastChild.remove();
      const old = work.querySelector("[aria-current]");
      old?.removeAttribute("aria-current");
      while (work.children.length <= cursor) {
        const row = document.createElement("li");
        row.append(element("span", frames[work.children.length].work));
        work.append(row);
      }
      work.lastChild.setAttribute("aria-current", "step");
      work.lastChild.classList.toggle("sp-final", last);
      sheets.scrollTop = sheets.scrollHeight;
      renderer.show(frame);
      if (get("details").open) describeScene();
    }

    function rebuild() {
      pause();
      // Domain code can sort a preset or retain references. Each run owns its input and output.
      const data = structuredClone(spec.presets[Number(preset.value)]);
      frames = structuredClone(spec.trace(data, { ...params }, seeded(seed.valueAsNumber)));
      if (!frames.length) throw new Error(id + " produced an empty trace");
      renderer.fit(frames);
      work.replaceChildren();
      show(0);
    }

    for (const p of spec.params) {
      const label = element("label", p.label);
      const control = document.createElement(p.options ? "select" : "input");
      params[p.key] = p.value;
      if (p.options) {
        control.append(...p.options.map(s => new Option(s, s)));
      } else {
        Object.assign(control, { type: "number", min: p.min, max: p.max, step: p.step, required: true });
        control.title = `${p.min} to ${p.max}, in steps of ${p.step}`;
      }
      control.value = p.value;
      control.onchange = () => {
        if (!control.reportValidity()) return;
        params[p.key] = p.options ? control.value : control.valueAsNumber;
        rebuild();
      };
      label.append(control);
      get("params").append(label);
    }

    function play() {
      pause();
      if (cursor === frames.length - 1) return;
      run.innerHTML = '<span aria-hidden="true">Ⅱ</span> Pause';
      timer = setInterval(() => show(cursor + 1), 1200 * Number(speed.value));
    }
    preset.onchange = rebuild;
    seed.onchange = () => { if (seed.reportValidity()) rebuild(); };
    get("random").onclick = () => {
      const draw = crypto.getRandomValues(new Uint32Array(1))[0];
      seed.value = draw === seed.valueAsNumber ? (draw + 1) >>> 0 : draw;
      rebuild();
    };
    run.onclick = () => timer === undefined ? play() : pause();
    next.onclick = () => { pause(); show(cursor + 1); };
    previous.onclick = () => { pause(); show(cursor - 1); };
    get("replay").onclick = () => { show(0); play(); };
    speed.onchange = () => { if (timer !== undefined) play(); };
    get("in").onclick = () => renderer.zoom(1.2);
    get("out").onclick = () => renderer.zoom(1 / 1.2);
    get("reset").onclick = renderer.reset;
    get("details").ontoggle = () => { if (get("details").open) describeScene(); };
    dispose = () => { pause(); renderer.destroy(); };
    rebuild();
  }

  globalThis.Sims = {
    register(spec) {
      if (catalog.has(spec.id)) throw new Error("Duplicate simulation: " + spec.id);
      catalog.set(spec.id, { spec, source: globalThis.document?.currentScript?.src });
    },
    boot
  };
})();
