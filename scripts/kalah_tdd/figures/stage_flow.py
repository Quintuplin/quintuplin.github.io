"""Figure F5 (#88): a design's stages from facts.stages as a flowchart and a stage table. Each stage is checked against
its block of the merged steps, so the figure cannot drift from the step list it draws."""

import re
from html import escape, unescape

from .. import parts
from . import flow

# The steps header of each stage kind. A stage with a when event runs as "if <event>, " and its kind's header.
KIND = {"S": "once:", "L": "repeat per {unit} until none is open:", "F": "throughout:",
        "starts": "for up to 3 starts, keep the best:", "H": "the harness does:"}
# A when event as the steps say it, and the label of the edge into its first stage.
WHEN = {"hidden_failure": ("hidden failure", "on fail")}
PREFIX = {"S": "Once: ", "starts": "Up to 3 starts: "}
LANE = {"F": "Throughout", "H": "Harness"}
SPAN = re.compile(r'<span class="(hd|st)">(.*?)</span>', re.S)
STEP = re.compile(r"(\d+)\. |with (.+?) step (\d+)\. ")
COLUMNS = ("Stage", "Runs as", "Steps", "Details", "Note")
# study.css breaks td and th anywhere, which beside the long Note split the short columns mid-word.
KEEP = ' style="overflow-wrap:normal"'
# study.css `.diagram svg.flow` min-width, which test 15 reads back.
FLOW_MIN_WIDTH = 640


def stages(slug, facts, pre):
    """[(stage, header, step lines)] for slug's facts stages, each checked against the next lines of the merged steps
    pre. Stages in a row with one header, such as several once stages, share its block."""
    blocks = []
    for kind, line in SPAN.findall(pre):
        if kind == "hd" or not blocks:
            blocks.append((unescape(line) if kind == "hd" else "", []))
        if kind == "st":
            blocks[-1][1].append(line)
    out, b, i = [], 0, 0
    for stage in facts[slug]["stages"]:
        # Advance only past a block a stage has used, so an empty block reaches the header check and is refused.
        if b < len(blocks) and 0 < i == len(blocks[b][1]):
            b, i = b + 1, 0
        if b == len(blocks):
            raise ValueError(f"{slug}: stage {stage['id']} has no steps left to match")
        header, lines = blocks[b]
        k = len(stage["steps"]) + sum(map(len, stage.get("with", {}).values()))
        out.append(checked(slug, facts, stage, header, lines[i:i + k]))
        i += k
    if (b, i) != (len(blocks) - 1, len(blocks[-1][1])):
        raise ValueError(f"{slug}: the steps from {blocks[b][0]!r} on are in no facts stage")
    return out


def checked(slug, facts, stage, header, lines):
    where, when = f"{slug}: stage {stage['id']}", stage.get("when")
    if stage["kind"] not in KIND or (when and when not in WHEN):
        raise ValueError(f"{where} has unknown kind {stage['kind']!r} or event {when!r}")
    want = (f"if {WHEN[when][0]}, " if when else "") + KIND[stage["kind"]].format(unit=stage.get("unit"))
    if header != want:
        raise ValueError(f"{where} runs as {want!r} but its steps header is {header!r}")
    got, borrowed = [], {}
    for line in map(unescape, lines):
        m = STEP.match(line)
        if not m:
            raise ValueError(f"{where} has step line {line!r} of no known form")
        if m[1]:
            got.append(int(m[1]))
        else:
            borrowed.setdefault(m[2], []).append(int(m[3]))
    unknown = [k for k in stage.get("with", {}) if k not in facts]
    if unknown:
        raise ValueError(f"{where} takes steps with unknown designs {unknown}")
    with_ = {facts[k]["method"]: ns for k, ns in stage.get("with", {}).items()}
    if (got, borrowed) != (stage["steps"], with_):
        raise ValueError(f"{where} lists steps {stage['steps']} with {with_}, its header holds {got} with {borrowed}")
    return stage, header, lines


def numbers(ns):
    """[1, 3, 4, 5] as "1, 3 to 5" and [2, 8] or [4, 5] as "2 and 8" or "4 and 5"."""
    runs = []
    for n in ns:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    items = [s for r in runs for s in ([f"{r[0]} to {r[-1]}"] if len(r) > 2 else map(str, r))]
    if len(items) > 1 and " " not in items[-1]:
        return ", ".join(items[:-1]) + " and " + items[-1]
    return ", ".join(items)


def steps(ns):
    return f"step {ns[0]}" if len(ns) == 1 else f"steps {numbers(ns)}"


def label(stage):
    """"Once: step 1", "Steps 2 to 7" or "With held-out steps 2 and 8". A when stage's lane names its event."""
    said = [steps(stage["steps"])] if stage["steps"] else []
    said += [f"with {k} {steps(ns)}" for k, ns in stage.get("with", {}).items()]
    text = ("" if stage.get("when") else PREFIX.get(stage["kind"], "")) + ", ".join(said)
    return text[:1].upper() + text[1:]


def note(stage):
    """The short facts a node shows, such as "Commit cap 60". The stage table holds the rest."""
    said = "; ".join(f"{key.replace('_', ' ')} {stage[key]}" for key in ("commit_cap", "returns") if key in stage)
    return said[:1].upper() + said[1:]


def details(stage):
    said = [f"{key.replace('_', ' ')} {stage[key]}" for key in ("unit", "returns", "when", "commit_cap") if key in stage]
    return "; ".join(said + [f"with {k} {steps(ns)}" for k, ns in stage.get("with", {}).items()]) or "none"


def chart(checked):
    """F5's nodes, edges and loops. Throughout stages stand first in their own lane with no edges. The rest form one
    chain in explicit columns, so each row break has one wrap edge, and each L stage loops on itself."""
    rules = [s for s, _, _ in checked if s["kind"] == "F"]
    chain = [s for s, _, _ in checked if s["kind"] != "F"]
    lane = lambda s: f"When {WHEN[s['when']][0]}" if s.get("when") else LANE.get(s["kind"], "Agent")
    nodes = [flow.node(s["id"], label(s), lane(s), col=k, note=note(s)) for group in (rules, chain) for k, s in enumerate(group)]
    edges = [flow.edge(a["id"], b["id"], WHEN[b["when"]][1] if b.get("when") and not a.get("when") else "")
             for a, b in zip(chain, chain[1:])]
    return nodes, edges, [flow.loop(s["id"], s["unit"]) for s in chain if s["kind"] == "L"]


def sized(svg, hold=False):
    """The chart capped at its drawn size, and held there when narrower than study.css's flow min-width or when hold.
    Scaled to the column, a one column chart drew 42px to 51px labels."""
    width = int(re.match(r'<svg [^>]*viewBox="0 0 (\d+) ', svg).group(1))
    style = f"max-width:{width}px" + (f";min-width:{width}px" if hold or width < FLOW_MIN_WIDTH else "")
    return svg.replace("<svg ", f'<svg style="{style}" ', 1)


def figure(n, slug, facts, pre):
    """Figure n, the stage flow, then h3#stages with the stage table its Data link targets."""
    found = stages(slug, facts, pre)
    nodes, edges, loops = chart(found)
    title = f"Stage flow of {facts[slug]['method']}"
    lanes = list(dict.fromkeys(nd.lane for nd in nodes))
    desc = (f"{len(nodes)} stages in run order across the lanes {', '.join(lanes)}."
            + (" Each loop repeats its stage per unit." if loops else ""))
    caption = (f"{len(nodes)} stages from the run facts, each checked against its block of the steps above. "
               f"Details and notes are in the stage table. Tag: {parts.tag('recomputed')}.")
    fig = parts.figure(n, "fig-" + n.replace(".", "-"), title, sized(flow.svg("f5", title, desc, nodes, edges, loops)), caption,
                       "#stages", flow.text_version(title, nodes, edges, loops))
    rows = "".join(f'<tr><th scope="row"{KEEP}>{escape(label(s))}</th><td{KEEP}>{escape(header)}</td><td>{"<br>".join(lines)}</td>'
                   f'<td{KEEP}>{escape(details(s))}</td><td>{escape(s.get("note", "none"))}</td></tr>' for s, header, lines in found)
    head = "".join(f'<th scope="col"{KEEP}>{c}</th>' for c in COLUMNS)
    return (f'{fig}\n<h3 id="stages">Stages</h3>\n<p>Each stage as the run facts list it. Runs as and Note are quoted '
            f'verbatim and Steps repeats the steps above. Tag: {parts.tag("verified")}.</p>\n'
            f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
