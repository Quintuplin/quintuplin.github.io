"""Inline SVG flowcharts for the Kalah TDD study pages (#57).

Nodes sit on a grid: one band per lane, one column per step, left to right, wrapping after COLS columns. Colours come only from the
study.css svg.flow classes, so both themes and forced colours apply. Each chart has a matching text version.
"""
import re
from html import escape
from typing import NamedTuple, Optional

NODE_W, GAP, MARGIN, PAD, LINE, CHARS = 168, 56, 16, 12, 16, 22
LANE_HEAD, LOOP_ROOM, LOOP_DROP, COLS, ROW_GAP = 22, 52, 18, 4, 16  # COLS * NODE_W plus gaps fits an 872px column
PREFIX = re.compile(r"[A-Za-z][\w-]*\Z")


class Node(NamedTuple):
    id: str
    label: str
    lane: str = ""
    col: Optional[int] = None  # nodes sharing a col stand in one column; None takes the next column
    note: str = ""


class Edge(NamedTuple):
    src: str
    dst: str
    label: str = ""


class Loop(NamedTuple):
    node: str
    unit: str
    back_to: str = ""  # empty loops back into node itself, as an L stage does


node, edge, loop = Node, Edge, Loop


def cells(nodes):
    """The lanes in first-seen order and each node's (lane index, column)."""
    lanes = list(dict.fromkeys(n.lane for n in nodes))
    cell, col = {}, -1
    for n in nodes:
        col = col + 1 if n.col is None else n.col
        cell[n.id] = (lanes.index(n.lane), col)
    return lanes, cell


def check(nodes, edges, loops):
    ids = [n.id for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate node ids in {ids}")
    for ref in [e.src for e in edges] + [e.dst for e in edges] + [l.node for l in loops] + [l.back_to for l in loops if l.back_to]:
        if ref not in ids:
            raise ValueError(f"unknown node {ref!r}")
    _, cell = cells(nodes)
    if len(set(cell.values())) != len(cell):
        raise ValueError(f"two nodes share a lane and column in {cell}")
    check_routes(cell, edges, loops)


def check_routes(cell, edges, loops):
    """Refuse an edge or loop whose drawn route would run backward or through another node."""
    taken = set(cell.values())
    for e in edges:
        (sl, sc), (dl, dc) = cell[e.src], cell[e.dst]
        if sc > dc or e.src == e.dst:
            raise ValueError(f"edge {e.src} -> {e.dst} runs backward; draw it as a loop")
        if sc == dc:
            between = {(lane, sc) for lane in range(min(sl, dl) + 1, max(sl, dl))}
        else:  # an edge into a later row runs only through gaps
            between = {(sl, c) for c in range(sc + 1, dc)} if sc // COLS == dc // COLS else set()
        if taken & between:
            raise ValueError(f"edge {e.src} -> {e.dst} crosses the node at {sorted(taken & between)}")
    for lp in loops:
        (sl, sc), (dl, dc) = cell[lp.node], cell[lp.back_to or lp.node]
        if sc // COLS != dc // COLS or dl > sl:
            raise ValueError(f"loop on {lp.node} must go back within its row to its own lane or one above")
        # It rises from the loop node's lane to the target, up the target's column.
        if crossed := taken & {(lane, dc) for lane in range(dl + 1, sl + 1)} - {(sl, sc)}:
            raise ValueError(f"loop on {lp.node} crosses the node at {sorted(crossed)}")


def wrap(text):
    """Greedy word wrap to CHARS; a longer word keeps its own line."""
    lines = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= CHARS:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def layout(nodes):
    """Top-left corner of each node, the node height, the lane bands, the y of the gap below each node's row and the
    canvas size. Columns past COLS wrap into a new row of every lane below the last, so the chart stays column wide."""
    lanes, cell = cells(nodes)
    named = any(lanes)
    height = 2 * PAD + LINE * max(len(wrap(n.label)) + len(wrap(n.note)) for n in nodes)
    band = (LANE_HEAD if named else 0) + height + LOOP_ROOM
    block = len(lanes) * band + ROW_GAP
    last = max(col for _, col in cell.values())
    at = {i: (MARGIN + col % COLS * (NODE_W + GAP), MARGIN + col // COLS * block + lane * band + (LANE_HEAD if named else 0))
          for i, (lane, col) in cell.items()}
    # Midway between the last lane band of a row and the first band of the next.
    below = {i: MARGIN + (col // COLS + 1) * block - ROW_GAP // 2 - 10 for i, (_, col) in cell.items()}
    cols, rows = min(last + 1, COLS), last // COLS + 1
    bands = [(lane, MARGIN + r * block + i * band) for r in range(rows) for i, lane in enumerate(lanes)] if named else []
    return at, height, band, bands, below, (2 * MARGIN + cols * NODE_W + (cols - 1) * GAP, MARGIN + rows * block - ROW_GAP)


def text(x, y, lines, cls="", anchor="middle"):
    attr = f' class="{cls}"' if cls else ""
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else LINE}">{escape(s)}</tspan>' for i, s in enumerate(lines))
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}"{attr}>{spans}</text>'


def gaps(x):
    """The x of the gaps left and right of the node column at x, where wrapped edges run."""
    last = MARGIN + (COLS - 1) * (NODE_W + GAP)
    return x - (GAP // 2 if x > MARGIN else MARGIN // 2), x + NODE_W + (GAP // 2 if x < last else MARGIN // 2)


def edge_path(a, b, h, below=None):
    """Straight within a lane, vertical within a column, else an elbow that turns in the gap before the target, so it
    only crosses columns in its source lane, which check_routes keeps clear. An edge into a later row leaves through the gap right of its source, runs along the gap below its row (y below) and enters from the left."""
    (sx, sy), (dx, dy) = a, b
    if below is not None:
        right, left = gaps(sx)[1], gaps(dx)[0]
        return f"M{sx + NODE_W},{sy + h // 2}H{right}V{below}H{left}V{dy + h // 2}H{dx}", ((right + left) // 2, below - 5)
    if sx == dx:
        top = dy > sy
        cx = sx + NODE_W // 2
        return f"M{cx},{sy + h if top else sy}V{dy if top else dy + h}", (cx + 4, (sy + dy + h) // 2)
    ex, ey, tx, ty = sx + NODE_W, sy + h // 2, dx, dy + h // 2
    mx = ex if ey == ty else gaps(dx)[0]
    path = f"M{ex},{ey}H{tx}" if ey == ty else f"M{ex},{ey}H{mx}V{ty}H{tx}"
    return path, ((mx + tx) // 2, ty - 5)


def svg(prefix, title, desc, nodes, edges=(), loops=()):
    """The flowchart as an inline SVG string. prefix starts every id, so several charts can share a page."""
    if not PREFIX.match(prefix):
        raise ValueError(f"id prefix {prefix!r} is not a plain id")
    check(nodes, edges, loops)
    at, h, band, bands, below, (width, height) = layout(nodes)
    arrow = f"url(#{prefix}-arrow)"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="flow" viewBox="0 0 {width} {height}" role="img" '
           f'aria-labelledby="{prefix}-title {prefix}-desc">',
           f'<title id="{prefix}-title">{escape(title)}</title><desc id="{prefix}-desc">{escape(desc)}</desc>',
           f'<defs><marker id="{prefix}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
           f'orient="auto"><path class="head" d="M0,0L10,5L0,10z"/></marker></defs>']
    for lane, y in bands:
        out.append(f'<rect class="lane" x="0" y="{y - MARGIN // 2}" width="{width}" height="{band - 4}" rx="6"/>')
        # Wrapped edges run down the left margin, so the lane name starts at the node edge.
        out.append(text(MARGIN, y + 6, [lane], "note", "start"))
    for n in nodes:
        x, y = at[n.id]
        label, note = wrap(n.label), wrap(n.note)
        out.append(f'<rect class="node" x="{x}" y="{y}" width="{NODE_W}" height="{h}" rx="6"/>')
        # Centre the label and note block in the shared node height.
        top = y + (h - LINE * (len(label) + len(note))) // 2 + 12
        out.append(text(x + NODE_W // 2, top, label))
        if note:
            out.append(text(x + NODE_W // 2, top + LINE * len(label), note, "note"))
    for e in edges:
        path, (lx, ly) = edge_path(at[e.src], at[e.dst], h, below[e.src] if below[e.src] != below[e.dst] else None)
        out.append(f'<path class="edge" d="{path}" marker-end="{arrow}"/>')
        if e.label:
            out.append(text(lx, ly, [e.label], "note"))
    for lp in loops:
        (sx, sy), (dx, dy) = at[lp.node], at[lp.back_to or lp.node]
        x0, x1, low = sx + NODE_W * 7 // 10, dx + NODE_W * 3 // 10, sy + h + LOOP_DROP
        out.append(f'<path class="loop" d="M{x0},{sy + h}V{low}H{x1}V{dy + h}" marker-end="{arrow}"/>')
        out.append(text((x0 + x1) // 2, low + 14, [f"repeat per {lp.unit}"], "note"))
    return "".join(out) + "</svg>"


def text_version(nodes, edges=(), loops=()):
    """A "Text version" disclosure: one list item per node in the given order, naming its edges and loops."""
    check(nodes, edges, loops)
    label = {n.id: n.label for n in nodes}
    items = []
    for n in nodes:
        parts = [n.label + "."] + ([n.note + "."] if n.note else []) + ([f"Lane: {n.lane}."] if n.lane else [])
        nexts = [label[e.dst] + (f" ({e.label})" if e.label else "") for e in edges if e.src == n.id]
        if nexts:
            parts.append("Next: " + "; ".join(nexts) + ".")
        parts += [f"Loop: repeat per {lp.unit}, back to {label[lp.back_to or lp.node]}." for lp in loops if lp.node == n.id]
        items.append(f"<li>{escape(' '.join(parts))}</li>")
    return f"<details><summary>Text version</summary><ol>{''.join(items)}</ol></details>"
