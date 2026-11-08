(() => {
  "use strict";

  const ns = "http://www.w3.org/2000/svg";
  const home = { yaw: -0.42, pitch: 0.26, zoom: 1 };
  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));
  const colors = ["#85c8fa", "#bbadfc", "#70dac5", "#efa3c7", "#aecf81", "#f5ae84"];
  const solid = n => n.shape === "bar" || n.shape === "cell";

  function svg(tag, attrs = {}, text) {
    const el = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    if (text !== undefined) el.textContent = text;
    return el;
  }

  // Keep one world-space scale through the trace so a moving point stays in context.
  function bounds(frames) {
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    const xs = new Set(), zs = new Set();
    for (const frame of frames) {
      for (const node of frame.nodes) {
        if (solid(node)) { xs.add(node.x); zs.add(node.z); }
        if (node.shape === "bar") { lo[1] = Math.min(0, lo[1]); hi[1] = Math.max(0, hi[1]); }
        [node.x, node.y, node.z].forEach((v, i) => {
          lo[i] = Math.min(lo[i], v);
          hi[i] = Math.max(hi[i], v);
        });
      }
    }
    if (!Number.isFinite(lo[0])) return { center: [0, 0, 0], half: [1, 1, 1] };
    function spacing(coords) {
      const sorted = Array.from(coords).sort((a,b) => a-b);
      let gap = Infinity;
      for (let i = 1; i < sorted.length; i++) gap = Math.min(gap, sorted[i] - sorted[i-1]);
      return Number.isFinite(gap) ? gap : undefined;
    }
    const dx = spacing(xs), dz = spacing(zs);
    const tile = [(dx ?? dz ?? 1) * .38, (dz ?? dx ?? 1) * .38];
    if (xs.size) {
      lo[0] -= tile[0]; hi[0] += tile[0];
      lo[2] -= tile[1]; hi[2] += tile[1];
      lo[1] -= Math.min(...tile) * .28;
    }
    return {
      tile,
      center: lo.map((v, i) => (v + hi[i]) / 2),
      half: lo.map((v, i) => (hi[i] - v) / 2)
    };
  }

  function rotate(x, y, z, camera) {
    const { yaw, pitch } = camera;
    const depth = z * Math.cos(yaw) - x * Math.sin(yaw);
    return {
      x: x * Math.cos(yaw) + z * Math.sin(yaw),
      y: -y * Math.cos(pitch) + depth * Math.sin(pitch),
      z: y * Math.sin(pitch) + depth * Math.cos(pitch)
    };
  }

  function projection(box, camera, width, height) {
    const [hx, hy, hz] = box.half;
    const radius = Math.hypot(hx, hy, hz) || 1;
    function view(x, y, z) {
      const p = rotate(x, y, z, camera);
      const perspective = 1 / (1 - p.z / (4 * radius));
      return { x: p.x * perspective, y: p.y * perspective, z: p.z, perspective };
    }
    let mx = radius * 0.16, my = mx;
    for (const x of [-hx, hx]) for (const y of [-hy, hy]) for (const z of [-hz, hz]) {
      const p = view(x, y, z);
      mx = Math.max(mx, Math.abs(p.x));
      my = Math.max(my, Math.abs(p.y));
    }
    const scale = Math.min((width - 74) / (2 * mx), (height - 80) / (2 * my)) * camera.zoom;
    return (x, y, z) => {
      const p = view(x - box.center[0], y - box.center[1], z - box.center[2]);
      return { ...p, x: width / 2 + p.x * scale, y: height / 2 + p.y * scale };
    };
  }

  function describe(n) {
    const value = n.value === undefined ? "" : ` · value ${n.value}`;
    return `${n.label}${value}   (x ${n.x}, y ${n.y}, z ${n.z})${n.active ? " · active" : ""}`;
  }

  function cuboid(point, tile, project, color) {
    const n = point.node, [rx, rz] = tile;
    const base = n.shape === "bar" ? 0 : n.y - Math.min(rx, rz) * .28;
    const vertices = [];
    for (const y of [base, n.y]) {
      for (const [dx, dz] of [[-rx,-rz],[rx,-rz],[rx,rz],[-rx,rz]]) {
        vertices.push(project(n.x + dx, y, n.z + dz));
      }
    }
    const faces = [[0,1,2,3], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7], [4,5,6,7]];
    return faces.map((indices, side) => {
      const corners = indices.map(i => vertices[i]);
      const el = svg("polygon", {
        points: corners.map(p => `${p.x},${p.y}`).join(" "),
        fill: `color-mix(in srgb, ${color} ${[47,58,66,73,58,96][side]}%, #142536)`,
        class: n.active ? "sp-face active" : "sp-face", "data-node": n.id
      });
      return { el, z: corners.reduce((sum,p) => sum + p.z, 0) / 4 };
    });
  }

  function edgeShape(edge, a, b, reciprocal) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const length = Math.hypot(dx, dy);
    let path;
    if (edge.from === edge.to) {
      path = `M ${a.x - a.r} ${a.y} c -20 -32 27 -32 ${a.r * 2} -2`;
    } else {
      if (length < a.r + b.r + 2) return null;
      const nx = dx / length, ny = dy / length;
      const bend = reciprocal ? Math.min(15, length / 4) : 0;
      const cx = (a.x + b.x) / 2 - ny * bend, cy = (a.y + b.y) / 2 + nx * bend;
      const arm = Math.hypot(cx - a.x, cy - a.y);
      const x1 = a.x + (cx - a.x) * (a.r + 1) / arm;
      const y1 = a.y + (cy - a.y) * (a.r + 1) / arm;
      const x2 = b.x + (cx - b.x) * (b.r + 2) / arm;
      const y2 = b.y + (cy - b.y) * (b.r + 2) / arm;
      path = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
    }
    const attrs = { d: path, class: edge.active ? "sp-edge active" : "sp-edge" };
    if (edge.directed) attrs["marker-end"] = `url(#sp-arrow${edge.active ? "-active" : ""})`;
    return svg("path", attrs);
  }

  function labels(points, width, height, measure) {
    const group = svg("g", { class: "sp-labels", "aria-hidden": true });
    const occupied = points.map(p => [p.x - p.r, p.y - p.r, p.x + p.r, p.y + p.r]);
    occupied.push([3, height - 66, 70, height - 2]);
    const sorted = points.slice().sort((a, b) => Number(!!b.node.active) - Number(!!a.node.active) || b.z - a.z);
    for (const p of sorted) {
      const full = p.node.label;
      const short = full.length > 21 ? full.slice(0, 20) + "…" : full;
      const str = svg("text", { "data-node": p.node.id }, short);
      group.append(str);
      const w = (measure ? measure.measureText(short).width : short.length * 9) + 8;
      const gap = p.r + 3;
      const options = [[gap, -9], [-gap - w, -9], [-w / 2, -gap - 18], [-w / 2, gap]];
      const spot = options.map(([dx, dy]) => [p.x + dx, p.y + dy, p.x + dx + w, p.y + dy + 18])
        .find(([l,t,r,b]) => l >= 3 && r < width - 3 && t >= 3 && b < height - 3 &&
          occupied.every(([ol,ot,or,ob]) => r < ol || l > or || b < ot || t > ob));
      if (!spot) { str.remove(); continue; }
      occupied.push(spot);
      str.setAttribute("x", spot[0] + 3);
      str.setAttribute("y", spot[1] + 13);
    }
    return group;
  }

  function axisKey(camera, height) {
    const group = svg("g", { class: "sp-axis", transform: `translate(36 ${height - 33})` });
    [[1,0,0,"x"], [0,1,0,"y"], [0,0,1,"z"]].forEach(([x,y,z,name]) => {
      const p = rotate(x, y, z, camera);
      group.append(svg("line", { x2: p.x * 21, y2: p.y * 21 }),
        svg("text", { x: p.x * 28, y: p.y * 28 + 4 }, name));
    });
    return group;
  }

  function floorGrid(box, project) {
    const [x,y,z] = box.center, [hx,hy,hz] = box.half;
    const segments = [];
    function line(a, b) { segments.push(`M${a.x},${a.y} L${b.x},${b.y}`); }
    if (hx && hz) for (let i = -4; i <= 4; i++) {
      const cx = x + hx * i / 4, cz = z + hz * i / 4;
      line(project(cx,y-hy,z-hz), project(cx,y-hy,z+hz));
      line(project(x-hx,y-hy,cz), project(x+hx,y-hy,cz));
    }
    return svg("path", { class: "sp-floor", d: segments.join(" ") });
  }

  function create(host, info) {
    const scene = svg("svg", { class: "sp-world", role: "img", tabindex: 0,
      "aria-label": "3D graph. Arrow keys orbit. Plus and minus zoom. Home resets the view." });
    host.append(scene);
    const defs = svg("defs");
    for (const active of ["", "-active"]) {
      const marker = svg("marker", { id: "sp-arrow" + active, viewBox: "0 0 8 8", refX: 7,
        refY: 4, markerUnits: "userSpaceOnUse", markerWidth: 9, markerHeight: 9, orient: "auto" });
      marker.append(svg("path", { d: "M0 0 L8 4 L0 8 Z", class: "sp-arrow" + active }));
      defs.append(marker);
    }
    const camera = { ...home };
    let box, frame, drag, points = [];
    const hint = "Drag to orbit · Hover over a point to inspect";
    const measure = document.createElement("canvas").getContext("2d");
    if (measure) measure.font = "600 13px system-ui";
    function draw() {
      if (!frame) return;
      const width = Math.max(160, host.clientWidth), height = Math.max(160, host.clientHeight);
      scene.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const project = projection(box, camera, width, height);
      const byId = new Map();
      points = frame.nodes.map(node => {
        const p = project(node.x, node.y, node.z);
        const point = { ...p, r: (node.active ? 7 : 5.5) * p.perspective, node };
        byId.set(node.id, point);
        return point;
      }).sort((a, b) => a.z - b.z);
      const layers = [];
      const edges = frame.edges || [];
      const pairs = new Set(edges.filter(e => e.directed).map(e => JSON.stringify([e.from, e.to])));
      for (const e of edges) {
        const a = byId.get(e.from), b = byId.get(e.to);
        if (!a || !b) continue;
        const shape = edgeShape(e, a, b, e.directed && pairs.has(JSON.stringify([e.to, e.from])));
        if (shape) layers.push({ z: (a.z + b.z) / 2, el: shape });
      }
      for (const p of points) {
        const n = p.node, color = colors[((n.group || 0) % colors.length + colors.length) % colors.length];
        if (solid(n)) {
          layers.push(...cuboid(p, box.tile, project, color));
          continue;
        }
        const el = svg("circle", { cx: p.x, cy: p.y, r: p.r, fill: color,
          class: n.active ? "sp-dot active" : "sp-dot", "data-node": n.id });
        layers.push({ z: p.z, el });
      }
      scene.replaceChildren(defs, floorGrid(box, project), ...layers.sort((a,b) => a.z - b.z).map(v => v.el),
        axisKey(camera, height));
      scene.append(labels(points, width, height, measure));
      info.textContent = hint;
    }

    function zoom(factor) { camera.zoom = clamp(camera.zoom * factor, 0.35, 5); draw(); }
    function reset() { Object.assign(camera, home); draw(); }
    function orbit(dx, dy) {
      camera.yaw += dx;
      camera.pitch = clamp(camera.pitch + dy, -1.45, 1.45);
      draw();
    }
    scene.addEventListener("keydown", e => {
      switch (e.key) {
        case "ArrowLeft": orbit(-0.15, 0); break;
        case "ArrowRight": orbit(0.15, 0); break;
        case "ArrowUp": orbit(0, 0.15); break;
        case "ArrowDown": orbit(0, -0.15); break;
        case "+": case "=": zoom(1.2); break;
        case "-": zoom(1 / 1.2); break;
        case "Home": reset(); break;
        default: return;
      }
      e.preventDefault();
    });
    scene.addEventListener("pointerdown", e => {
      if (!e.isPrimary || e.button !== 0 || e.target.closest(".sp-labels")) return;
      drag = [e.clientX, e.clientY];
      scene.setPointerCapture(e.pointerId);
    });
    scene.addEventListener("pointermove", e => {
      if (drag) {
        orbit((e.clientX - drag[0]) * 0.009, (e.clientY - drag[1]) * 0.009);
        drag = [e.clientX, e.clientY];
        return;
      }
      const rect = scene.getBoundingClientRect();
      const hit = e.target.getAttribute("data-node");
      const p = points.find(p => p.node.id === hit) ||
        points.findLast(p => Math.hypot(p.x - e.clientX + rect.left, p.y - e.clientY + rect.top) <= p.r + 5);
      info.textContent = p ? describe(p.node) : hint;
    });
    scene.addEventListener("lostpointercapture", () => { drag = null; });
    scene.addEventListener("pointerleave", () => { info.textContent = hint; });
    const observer = new ResizeObserver(draw);
    observer.observe(host);
    return {
      fit(frames) { box = bounds(frames); Object.assign(camera, home); },
      show(next) { frame = next; draw(); },
      zoom, reset, destroy() { observer.disconnect(); }
    };
  }

  globalThis.SimsRenderer = { create, describe };
})();
