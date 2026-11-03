"""Experimental design and approach (#63): the study question, the task, the harness pipeline, every run and arm,
the replicate protocol and the study's stage and course context."""

import re
from html import escape

from .. import links, parts, snapshot
from ..figures import design

INTRO = re.compile(r'<h1 id="kalah-tdd-experiment">.*?</h1>(.*?)<h2', re.S)
PARA = re.compile(r"<p>.*?</p>", re.S)
SLUG = "experimental-design"
# The start clone count a run's multi-start method page records.
STARTS = re.compile(r"from (\d+) start clones")


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


def spec(snap, after):
    """docs/SPEC.md as the task section: level 1 as its lead, levels 2 and 3 as h3 and h4.
    after maps a section id to HTML that ends that section, refused when no section has the id."""
    out, ids = [], set()
    for section in snap.facts["analysis"]["spec"]:
        level, id = section["level"], None
        if level > 1:
            id = "spec-" + re.sub(r"[^a-z0-9]+", "-", section["title"].lower()).strip("-")
            out.append(f'<h{level + 1} id="{id}">{escape(section["title"])}</h{level + 1}>')
            ids.add(id)
        out.append(spec_text(section["text"]) + after.get(id, ""))
    if missing := set(after) - ids:
        raise ValueError(f"docs/SPEC.md has no section {sorted(missing)}")
    return "".join(out)


def heads(names):
    """Column heads that never break mid-word: one-word heads stay on one line, longer ones wrap only at spaces."""
    return "".join(f'<th scope="col" class="{"words" if " " in h else "nowrap"}">{h}</th>' for h in names)


def variants():
    """The four variants as play(io, clockwise, sevenfive) selects them, read from the play() doc comment."""
    cells = [(f"<code>{str(cw).lower()}</code>", f"<code>{str(sf).lower()}</code>", 7 if sf else 6, 5 if sf else 4,
              "clockwise" if cw else "anti-clockwise") for sf in (False, True) for cw in (False, True)]
    rows = "".join("<tr>" + "".join(f'<td class="nowrap">{c}</td>' for c in row) + "</tr>" for row in cells)
    head = ("clockwise", "sevenfive", "Houses per player", "Seeds per house", "Sowing")
    table = f'<table id="variants"><thead><tr>{heads(head)}</tr></thead><tbody>{rows}</tbody></table>'
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
    if "list_tag" in tcp:
        return f"Builds the {tcp['list_tag']} list in {len(run['methods'])} orders."
    if "rates" in tcp:
        return f"Rates the {tcp['rates']} test list again with lister {tcp['lister']}, seed {tcp['seed']}."
    if "lister" in tcp:
        made = next((r["tcp"]["list"] for r in facts["runs"].values() if r.get("tcp", {}).get("list_tag") == name), None)
        size = f" of {len(made['clauses'])} clauses and {len(made['candidates'])} candidates" if made else ""
        return f"Writes the test list{size} with lister {tcp['lister']}, seed {tcp['seed']}."
    if name.endswith(design.REBUILD):
        ids = " ".join(sorted(slug.rsplit("-", 1)[-1] for slug in run["methods"]))
        return (f'Rebuilds {ids} of {name.removesuffix(design.REBUILD)} at a later harness. '
                f'<a href="{links.url("methodology/analysis")}">Analysis and validity</a> covers why.')
    return ""


def shared(runs):
    """The sentence of what every run shares: model, effort and the cycles and starts caps. Refused when one differs,
    as its column would then belong in the runs table."""
    values = {(r["model"], r["effort"], r["caps"]["cycles"], r["caps"]["starts"]) for r in runs.values()}
    if len(values) != 1:
        raise ValueError(f"runs differ in model, effort or the cycles or starts cap: {sorted(values)}")
    (model, effort, cycles, starts), = values
    return (f"Every run used model {escape(model)} at {escape(effort)} effort with caps of {cycles} cycles per call "
            f"and {starts} starts.")


def listed(items):
    """One or more items as "a", "a and b" or "a, b and c"."""
    return " and ".join(filter(None, (", ".join(items[:-1]), items[-1])))


def run_clones(snap, name, run, slugs):
    """A run's builds and clones: the start clones its own method pages record, else the starts cap as a bound."""
    n = len(run["methods"])
    found = [STARTS.search(snap.files.get(f"runs/{name}/methods/{slug}.html", "")) for slug in slugs]
    if all(found):
        return f"{name} makes {n} builds in {n + sum(int(m.group(1)) for m in found)} clones {parts.tag('verified')}"
    return f"{name} makes {n} builds in up to {n + len(slugs) * run['caps']['starts']} clones {parts.tag('recomputed')}"


def builds(snap):
    """What a build is, the clones beyond builds per run and the build and rebuild totals."""
    every = design.runs(snap.facts)
    clones = [run_clones(snap, name, run, slugs) for name, run in every.items() if (slugs := design.multi_starts(run))]
    if not clones:
        raise ValueError("no multi-start run, so the start clones sentence has nothing to state")
    rebuilds = sum(len(run["methods"]) for name, run in every.items() if name.endswith(design.REBUILD))
    total = sum(len(run["methods"]) for run in every.values()) - rebuilds
    return ("<p>A build is one final clone of a method or arm. Start clones and rebuilds are not builds. Multi-start "
            "TDD runs each start in a clone of its own, up to the starts cap, so " + listed(clones)
            + f". The runs make {total} builds, the counts in Figure 2.2, and {rebuilds} rebuilds "
            f"{parts.tag('recomputed')}. Figure 2.2 rings the rebuilt replicates.</p>")


def runs_table(snap):
    """The runs table, its cells unbroken so it scrolls in its region, then each run's note in a list."""
    head = ("Run", "Kind", "Builds", "Arms", "Waves", "Iterations cap", "Methods doc", "Harness commit")
    rows, notes = [], []
    for name, run in design.runs(snap.facts).items():
        commit = run.get("harness", {}).get("commit")
        arms = len({design.arm(slug, e) for slug, e in run["methods"].items()})
        n = len(run["methods"])
        cells = [design.RUNS[name], f"{n} rebuilds" if name.endswith(design.REBUILD) else n, arms, waves(run),
                 run["caps"]["iterations"], snapshot.run_doc(snap, name), commit[:7] if commit else "not recorded"]
        rows.append(f'<tr><th scope="row" class="nowrap">{escape(name)}</th>'
                    + "".join(f'<td class="nowrap">{escape(str(c))}</td>' for c in cells) + "</tr>")
        if text := note(name, run, snap.facts):
            notes.append(f"<li><b>{escape(name)}</b>. {text}</li>")
    table = f'<table id="runs-table"><thead><tr>{heads(head)}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    return parts.table(table, "Every run with its builds, iterations cap and versions") + f"<ul>{''.join(notes)}</ul>"


def collect_table(snap):
    rows = "".join(f'<tr><td class="nowrap"><code>{mode}</code></td><td>{k}</td>'
                   f'<td class="nowrap"><code>{escape(s["name"])}</code></td>'
                   f'<td>{"yes" if s["skippable"] else "no"}</td></tr>'
                   for mode, steps in snap.facts["pipeline"]["collect"].items() for k, s in enumerate(steps, 1))
    head = ("Mode", "Order", "Step", "Skipped on failed fetchBack")
    table = f'<table id="collect-steps"><thead><tr>{heads(head)}</tr></thead><tbody>{rows}</tbody></table>'
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
        '<h2 id="task">Task and variants</h2>'
        f"<p>The agent builds the course's Kalah assignment. The brief below is docs/SPEC.md at tdd-experiment {sha} "
        f"{parts.tag('verified')}.</p>"
        + spec(snap, {"spec-variants": f"<p>The four variants that <code>play()</code> selects "
                                       f"{parts.tag('verified')}.</p>" + variants()}),
        '<h2 id="pipeline">Harness pipeline</h2>'
        "<p>Every run goes through the same harness. Agents do the building, reviewing and rating. Harness scripts do the "
        "rest.</p>"
        + parts.figure(next(n), "pipeline-flow", "Harness pipeline of one run", pipe_svg,
                       f"The step order follows the harness sources at tdd-experiment {sha} {parts.tag('verified')}. "
                       "One step has no source check. render.py draws the report again once the ratings land "
                       f"{parts.tag('unchecked')}.",
                       None, pipe_text)
        + "<p>collect.sh runs collectOne for each clone and collectList for a list-only run. A step marked yes is "
          f"skipped when fetchBack fails {parts.tag('recomputed')}.</p>" + collect_table(snap),
        '<h2 id="runs-and-arms">Runs and arms</h2>'
        "<p>An arm is a design or a test-list order. A run builds one or more arms under fixed caps.</p>"
        + parts.figure(next(n), "arms-map", "Builds per arm and run", arms_svg,
                       "Each mark's area grows with its build count. The ring marks the rep-2 replicates rebuilt at a "
                       f"later harness. Counts come from facts.json {parts.tag('recomputed')}.", None, arms_text)
        + builds(snap)
        + f"<p>Every run of the study {parts.tag('recomputed')}. {shared(snap.facts['runs'])} Methods doc is the short "
          f"sha256 of the methods doc each run was built under. The methods text quoted on the study pages is doc "
          f"{snap.doc}.</p>" + runs_table(snap),
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
