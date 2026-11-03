"""Figures of the experimental design page (#63): the harness pipeline, the runs and arms map and the replicate protocol.
Every count comes from facts.json. Node order follows the tdd-experiment harness headers at the snapshot sha."""

import math
from collections import Counter
from html import escape

from . import flow
from .. import pagemap

HARNESS, AGENTS = "Harness", "Agents"
NAMES = {slug: name for slug, _, name, _ in pagemap.DESIGNS}
# Each run of facts.json in study order with its kind; a run missing here fails the build.
RUNS = {"pilot-1": "Pilot", "pilot-2": "Pilot", "full-1": "Survey", "tcp-1-list": "Test list", "tcp-1": "Test-list order",
        "tcp-1-list2": "List reliability", "rep-1": "Planned contrasts", "rep-2": "Planned contrasts",
        "rep-2/rebuild": "Rebuild"}
REBUILD = "/rebuild"
# Arms map geometry, narrow enough for a phone column: label x, first mark column, column step, first label baseline,
# row step and the mark centre below its label.
WIDTH, LABEL_X, X0, STEP, Y0, ROW, MARK = 312, 8, 32, 50, 44, 40, 14


def runs(facts):
    """facts.json runs in study order, refused when RUNS and facts name different runs."""
    if set(RUNS) != set(facts["runs"]):
        raise ValueError(f"RUNS {sorted(RUNS)} and facts.json runs {sorted(facts['runs'])} differ")
    return {run: facts["runs"][run] for run in RUNS}


def arm(slug, entry):
    """A build's arm: the design it replicates or its test-list order."""
    return entry.get("of") or entry.get("arm") or slug


def arm_label(key, entry):
    if key in NAMES:
        return NAMES[key]
    if entry.get("order"):
        return f"Test-list order: {entry['order']}"
    raise ValueError(f"build arm {key!r} is no design and no test-list order")


def pipeline(facts):
    """(svg, text version) of the harness pipeline: batch.js phases, after.py, collect.sh, rating and render."""
    collect = facts["pipeline"]["collect"]
    nodes = [flow.node("args", "args.py", HARNESS, note="args.json with model, effort and caps"),
             flow.node("stages", "Method stages", AGENTS, note="batch.js, one clone per method"),
             flow.node("review", "Blind review", AGENTS, note="batch.js, one per method"),
             flow.node("measure", "Measure agent", AGENTS, note="MEASURE.md per method"),
             flow.node("after", "after.py", HARNESS, note="slugs.tsv and batch.json for collect"),
             flow.node("collect", "collect.sh", HARNESS,
                       note=f"{len(collect['collectOne'])} steps per clone, {len(collect['collectList'])} for a list run"),
             flow.node("rate", "Three blind raters", AGENTS, note="rate.js, eight cqp principles"),
             flow.node("render", "render.py", HARNESS, note="report page")]
    edges = [flow.edge("args", "stages", "per clone"), flow.edge("stages", "review"), flow.edge("review", "measure"),
             flow.edge("measure", "after"), flow.edge("after", "collect"), flow.edge("collect", "rate"),
             flow.edge("rate", "render")]
    loops = [flow.loop("stages", "unit")]
    title = "Harness pipeline of one run"
    desc = ("args.py writes the run's arguments. batch.js runs each method's stages in its own clone, then a blind review "
            "and a measure agent per method. after.py, collect.sh, three blind raters and render.py follow.")
    return flow.svg("pipe", title, desc, nodes, edges, loops), flow.text_version(title, nodes, edges, loops)


def replicate_shape(run):
    """(arms, replicates per arm, wave sizes, caps) of a replicate run."""
    arms = Counter(e["of"] for e in run["methods"].values())
    if len(set(arms.values())) != 1:
        raise ValueError(f"replicate arms differ in size: {dict(arms)}")
    caps = run["caps"]
    return len(arms), next(iter(arms.values())), tuple(map(len, run["waves"])), (caps["iterations"], caps["cycles"], caps["starts"])


def replicate(facts):
    """(svg, text version) of the replicate protocol of rep-1 and rep-2, refused when the two differ in shape."""
    shapes = {replicate_shape(facts["runs"][r]) for r in ("rep-1", "rep-2")}
    if len(shapes) != 1:
        raise ValueError(f"rep-1 and rep-2 differ in shape: {shapes}")
    (arms, reps, waves, caps), = shapes
    if len(set(waves)) != 1:
        raise ValueError(f"waves differ in size: {waves}")
    nodes = [flow.node("arms", "Pick arms", note=f"{arms} arms, {reps} replicates each"),
             flow.node("order", "Rotate launch order", note="replicate k rotated by k - 1"),
             flow.node("waves", "Cut into waves", note=f"{len(waves)} waves of {waves[0]}"),
             flow.node("build", "Build, review, measure", note="fresh clone, caps {} iterations, {} cycles, {} starts".format(*caps)),
             flow.node("collect", "collect.sh", note="every build after the batch"),
             flow.node("rate", "Three blind raters", note="one rating per final"),
             flow.node("mwu", "Exact Mann-Whitney U", note="per planned arm pair"),
             flow.node("holm", "Holm step-down", note="over each family of pairs")]
    edges = [flow.edge(a, b) for a, b in zip([n.id for n in nodes], [n.id for n in nodes][1:])]
    loops = [flow.loop("build", "wave", back_to="waves")]
    title = "Replicate protocol of rep-1 and rep-2"
    desc = (f"{arms} arms of {reps} replicates each launch in a rotated order, cut into {len(waves)} waves of {waves[0]} "
            "that build in turn. collect.sh, three blind raters, an exact Mann-Whitney U test per planned pair and a "
            "Holm step-down follow.")
    return flow.svg("rep", title, desc, nodes, edges, loops), flow.text_version(title, nodes, edges, loops)


def arms_grid(facts):
    """(build runs, [(arm label, {run: (builds, rebuilt)})]) with designs in report order, then test-list orders."""
    every = runs(facts)
    built = [r for r, run in every.items() if run["methods"] and REBUILD not in r]
    cells, entries = {}, {}
    for r in built:
        for slug, entry in every[r]["methods"].items():
            key = arm(slug, entry)
            entries.setdefault(key, entry)
            cells.setdefault(key, {}).setdefault(r, [0, 0])[0] += 1
    for r in (r for r in every if r.endswith(REBUILD)):
        for slug, entry in every[r]["methods"].items():
            cells[arm(slug, entry)][r.removesuffix(REBUILD)][1] += 1
    order = list(NAMES) + [k for k in cells if k not in NAMES]
    keys = sorted(cells, key=order.index)
    return built, [(arm_label(k, entries[k]), {r: tuple(c) for r, c in cells[k].items()}) for k in keys]


def cell(builds, rebuilt):
    return f"{builds} build{'s' if builds != 1 else ''}" + (f", {rebuilt} rebuilt" if rebuilt else "")


def arms_svg(built, rows):
    """A dot matrix of builds per arm and run, area by count, a ring on rebuilt replicates. Each arm's label sits above
    its row, so the columns start at the left edge and the map fits a phone column."""
    height = Y0 + (len(rows) - 1) * ROW + MARK + 12
    out = [f'<svg class="arms" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" role="img" '
           'aria-labelledby="arms-svg-title arms-svg-desc">',
           '<title id="arms-svg-title">Builds per arm and run</title>',
           f'<desc id="arms-svg-desc">One row per arm and one column per build run. Each mark\'s area grows with its '
           f'build count, which stands beside it. A ring marks rebuilt replicates.</desc>']
    out += [f'<text x="{X0 + i * STEP}" y="20" text-anchor="middle">{escape(r)}</text>' for i, r in enumerate(built)]
    for j, (label, counts) in enumerate(rows):
        y = Y0 + j * ROW
        out.append(f'<text class="lbl" x="{LABEL_X}" y="{y}">{escape(label)}</text>')
        y += MARK
        out.append(f'<line class="grid" x1="{LABEL_X}" x2="{WIDTH - 8}" y1="{y}" y2="{y}"/>')
        for i, r in enumerate(built):
            if r not in counts:
                continue
            (n, rebuilt), x = counts[r], X0 + i * STEP
            radius = round(3 + 2 * math.sqrt(n), 1)
            out.append(f'<circle class="mk s1" cx="{x}" cy="{y}" r="{radius}">'
                       f'<title>{escape(label)}, {escape(r)}: {cell(n, rebuilt)}</title></circle>')
            if rebuilt:
                radius += 3
                out.append(f'<circle class="mk ring s1" cx="{x}" cy="{y}" r="{radius}"/>')
            out.append(f'<text x="{x + radius + 4}" y="{y + 4}">{n}</text>')
    return "".join(out) + "</svg>"


def arms_table(built, rows):
    head = "".join(f'<th scope="col">{escape(r)}</th>' for r in built)
    body = "".join(f'<tr><th scope="row">{escape(label)}</th>'
                   + "".join(f"<td>{cell(*counts[r]) if r in counts else ''}</td>" for r in built) + "</tr>"
                   for label, counts in rows)
    return f'<table id="arms-table"><thead><tr><th scope="col">Arm</th>{head}</tr></thead><tbody>{body}</tbody></table>'


def arms_map(facts, table):
    """(svg, table view disclosure). table wraps the table HTML in its scroll region."""
    built, rows = arms_grid(facts)
    title = "Builds per arm and run"
    summary = f"Table view: {title}, {len(rows)} rows and {len(built) + 1} columns"
    view = f"<details><summary>{escape(summary)}</summary>{table(arms_table(built, rows), title)}</details>"
    return arms_svg(built, rows), view
