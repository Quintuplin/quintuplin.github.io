"""Experimental design and approach (#63): the study question, the task, the harness pipeline, every run and arm,
the replicate protocol and the study's stage and course context."""

import re
from html import escape

from .. import links, parts, snapshot
from ..figures import design

INTRO = re.compile(r'<h1 id="kalah-tdd-experiment">.*?</h1>(.*?)<h2', re.S)
PARA = re.compile(r"<p>.*?</p>", re.S)
SLUG = "experimental-design"


def inline(text):
    """Escaped text with `code` spans."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(text, quote=False))


def spec_text(text):
    """The docs/SPEC.md subset: paragraphs, "- " lists and ``` fences with inline code."""
    out, blocks = [], re.split(r"(```\w*\n.*?\n\s*```)", text, flags=re.S)
    for block in blocks:
        if block.startswith("```"):
            code = block.split("\n", 1)[1].rsplit("\n", 1)[0]
            out.append(f"<pre><code>{escape(code, quote=False)}</code></pre>")
            continue
        for para in filter(None, (p.strip() for p in block.split("\n\n"))):
            lines = para.splitlines()
            if all(line.startswith("- ") for line in lines):
                out.append("<ul>" + "".join(f"<li>{inline(line[2:])}</li>" for line in lines) + "</ul>")
            else:
                out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def spec(snap):
    """docs/SPEC.md as the task section: level 1 as its lead, levels 2 and 3 as h3 and h4."""
    out = []
    for section in snap.facts["analysis"]["spec"]:
        level = section["level"]
        if level > 1:
            id = "spec-" + re.sub(r"[^a-z0-9]+", "-", section["title"].lower()).strip("-")
            out.append(f'<h{level + 1} id="{id}">{escape(section["title"])}</h{level + 1}>')
        out.append(spec_text(section["text"]))
    return "".join(out)


def variants():
    """The four variants as play(io, clockwise, sevenfive) selects them, read from the play() doc comment."""
    rows = "".join(f"<tr><td><code>{str(cw).lower()}</code></td><td><code>{str(sf).lower()}</code></td>"
                   f"<td>{7 if sf else 6}</td><td>{5 if sf else 4}</td><td>{'clockwise' if cw else 'anti-clockwise'}</td></tr>"
                   for sf in (False, True) for cw in (False, True))
    table = ('<table id="variants"><thead><tr><th scope="col">clockwise</th><th scope="col">sevenfive</th>'
             '<th scope="col">Houses per player</th><th scope="col">Seeds per house</th><th scope="col">Sowing</th></tr>'
             f"</thead><tbody>{rows}</tbody></table>")
    return parts.table(table, "Kalah variants")


def waves(run):
    sizes = [len(w) for w in run.get("waves", ())]
    if not sizes:
        return "one batch" if run["methods"] else "none"
    if len(set(sizes)) == 1:
        return f"{len(sizes)} wave{'s' if len(sizes) != 1 else ''} of {sizes[0]}"
    return f"{len(sizes)} waves of " + ", ".join(map(str, sizes))


def note(name, run, facts):
    """What a run adds beyond its row: the test list it writes or rates, or the replicates it rebuilds."""
    tcp = run.get("tcp", {})
    if "lister" in tcp and "rates" in tcp:
        return f"Rates the {tcp['rates']} test list again with lister {tcp['lister']}, seed {tcp['seed']}."
    if "lister" in tcp:
        made = next((r["tcp"]["list"] for r in facts["runs"].values() if r.get("tcp", {}).get("list_tag") == name), None)
        size = f" of {len(made['clauses'])} clauses and {len(made['candidates'])} candidates" if made else ""
        return f"Writes the test list{size} with lister {tcp['lister']}, seed {tcp['seed']}."
    if "list_tag" in tcp:
        return f"Builds the {tcp['list_tag']} list in {len(run['methods'])} orders."
    if name.endswith(design.REBUILD):
        ids = " ".join(sorted(slug.rsplit("-", 1)[-1] for slug in run["methods"]))
        return (f'Rebuilds {ids} of {name.removesuffix(design.REBUILD)} at a later harness. '
                f'<a href="{links.url("methodology/analysis")}">Analysis and validity</a> covers why.')
    return ""


def runs_table(snap):
    head = ("Run", "Kind", "Builds", "Arms", "Waves", "Iterations cap", "Cycles cap", "Starts cap", "Model", "Effort",
            "Methods doc", "Harness commit", "Notes")
    rows = []
    for name, run in design.runs(snap.facts).items():
        caps, commit = run["caps"], run.get("harness", {}).get("commit")
        arms = len({design.arm(slug, e) for slug, e in run["methods"].items()})
        cells = [design.RUNS[name], len(run["methods"]), arms, waves(run), caps["iterations"], caps["cycles"],
                 caps["starts"], run["model"], run["effort"], snapshot.run_doc(snap, name),
                 commit[:7] if commit else "not recorded"]
        rows.append(f'<tr><th scope="row">{escape(name)}</th>' + "".join(f"<td>{escape(str(c))}</td>" for c in cells)
                    + f"<td>{note(name, run, snap.facts)}</td></tr>")
    table = ('<table id="runs-table"><thead><tr>' + "".join(f'<th scope="col">{h}</th>' for h in head)
             + f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    return parts.table(table, "Every run with its caps and versions")


def collect_table(snap):
    rows = "".join(f'<tr><td><code>{mode}</code></td><td>{k}</td><td><code>{escape(s["name"])}</code></td>'
                   f'<td>{"yes" if s["skippable"] else "no"}</td></tr>'
                   for mode, steps in snap.facts["pipeline"]["collect"].items() for k, s in enumerate(steps, 1))
    table = ('<table id="collect-steps"><thead><tr><th scope="col">Mode</th><th scope="col">Order</th>'
             '<th scope="col">Step</th><th scope="col">Skipped after a failed fetchBack</th></tr></thead>'
             f"<tbody>{rows}</tbody></table>")
    return parts.table(table, "collect.sh steps")


def question(snap):
    first, second = PARA.findall(INTRO.search(snap.files[snapshot.REPORT]).group(1))
    return f'<h2 id="study-question">Study question</h2><blockquote>{first}</blockquote>{second}'


def body(page, snap, idx):
    n = parts.numbers(SLUG)
    pipe_svg, pipe_text = design.pipeline(snap.facts)
    rep_svg, rep_text = design.replicate(snap.facts)
    arms_svg, arms_text = design.arms_map(snap.facts, parts.table)
    sha = snap.sha[:7]
    status = "".join(links.rewrite(snapshot.section(snap.files[snapshot.REPORT], id), snapshot.REPORT, SLUG, idx)
                     for id in ("study-stage", "course-context"))
    return [
        question(snap),
        '<h2 id="task">Task</h2>'
        f"<p>The agent builds the course's Kalah assignment. The brief below is docs/SPEC.md at tdd-experiment {sha} "
        f"{parts.tag('verified')}.</p>" + spec(snap)
        + f"<p>The four variants that <code>play()</code> selects {parts.tag('verified')}.</p>" + variants(),
        '<h2 id="pipeline">Harness pipeline</h2>'
        "<p>Every run goes through the same harness. Agents do the building, reviewing and rating. Harness scripts do the "
        "rest.</p>"
        + parts.figure(next(n), "pipeline-flow", "Harness pipeline of one run", pipe_svg,
                       f"The step order follows the harness sources at tdd-experiment {sha} {parts.tag('verified')}. "
                       f"That render.py draws the report again once the ratings land is {parts.tag('unchecked')}.",
                       None, pipe_text)
        + "<p>collect.sh runs collectOne for each clone and collectList for a list-only run. A step marked yes is "
          f"skipped when fetchBack fails {parts.tag('recomputed')}.</p>" + collect_table(snap),
        '<h2 id="runs-and-arms">Runs and arms</h2>'
        "<p>An arm is a design or a test-list order. A run builds one or more arms under fixed caps.</p>"
        + parts.figure(next(n), "arms-map", "Builds per arm and run", arms_svg,
                       "Each mark's area grows with its build count. The ring marks the rep-2 replicates rebuilt at a "
                       f"later harness. Counts come from facts.json {parts.tag('recomputed')}.", None, arms_text)
        + f"<p>Every run of the study {parts.tag('recomputed')}. Methods doc is the short sha256 of the methods doc each "
          f"run was built under. The methods text quoted on the study pages is doc {snap.doc}.</p>" + runs_table(snap),
        '<h2 id="replicate-protocol">Replicate protocol</h2>'
        "<p>rep-1 and rep-2 test planned contrasts between arms. Both follow one protocol, and the build refuses to run "
        "if their shapes differ.</p>"
        + parts.figure(next(n), "replicate-flow", "Replicate protocol of rep-1 and rep-2", rep_svg,
                       f"Arm, replicate, wave and cap counts come from facts.json {parts.tag('recomputed')}. The test "
                       f"and its correction follow contrast.py {parts.tag('verified')}. "
                       f'<a href="{links.url("results/contrasts")}">Planned contrasts</a> has the results.',
                       None, rep_text),
        '<h2 id="status">Study stage and course context</h2>'
        '<p>Both parts below come from the full-1 report that these study pages are built from. "This page" in them '
        "means that report.</p>" + status,
    ]
