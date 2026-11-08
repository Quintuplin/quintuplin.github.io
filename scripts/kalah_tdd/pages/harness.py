"""The methodology page (#64): how each design runs, from stages.json, the run records, the review schema and collect.sh."""

import json
import re
from html import escape

from .. import links, pagemap, parts, snapshot
from ..figures import flow

KINDS = {"S": "once", "L": "repeat per unit", "F": "throughout", "starts": "for up to n starts", "H": "the harness does"}
# Notation sentence that defines each kind.
DEFINES = {"S": "Once means", "L": "Repeat per unit means", "F": "Throughout means", "starts": "For up to n starts means",
           "H": "The harness does means"}
DESIGN_PAGES = {slug for slug, *_ in pagemap.DESIGNS}
CHIP = ' <span class="chip">skippable</span>'


def inline(text):
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text, quote=False)))


def md(text, label):
    """Paragraphs and numbered lists of a methods doc section; the list gets aria-label label."""
    out = []
    for block in text.split("\n\n"):
        lines = block.splitlines()
        if all(re.match(r"\d+\. ", line) for line in lines):
            lis = "".join(f"<li>{inline(re.sub(r'^\d+\. ', '', line))}</li>" for line in lines)
            out.append(f'<ol aria-label="{escape(label)}">{lis}</ol>')
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def grid(caption, head, rows):
    """A captioned table that stacks into labelled cells on a narrow screen. Cells are HTML."""
    th = "".join(f'<th scope="col">{escape(h)}</th>' for h in head)
    body = "".join("<tr>" + "".join(f'<td data-th="{escape(h)}">{c}</td>' for h, c in zip(head, r)) + "</tr>" for r in rows)
    return parts.table(f'<table class="cols"><caption>{escape(caption)}</caption><thead><tr>{th}</tr></thead>'
                       f"<tbody>{body}</tbody></table>", caption)


def section(id, title, *html):
    return f'<section aria-labelledby="{id}"><h2 id="{id}">{escape(title)}</h2>{"".join(html)}</section>'


def p(text, kind=None):
    return f"<p>{text}{' ' + parts.tag(kind) if kind else ''}</p>"


def code(text):
    return f"<code>{escape(str(text))}</code>"


def joined(values):
    return ", ".join(map(str, values))


def methodology(snap, title):
    found = [s["text"] for s in snap.facts["analysis"]["methodologies"] if s["title"] == title]
    if not found:
        raise ValueError(f"methods doc has no section {title!r}")
    return found[0]


def families(snap):
    """Method name to family, from the methods doc Summary table."""
    lines = methodology(snap, "Summary").splitlines()[2:]
    return {cells[0]: cells[1] for line in lines if (cells := [c.strip() for c in line.strip("|").split("|")])}


def glossary(snap, term):
    """A report glossary definition, as HTML."""
    m = re.search(rf"<b>{re.escape(term)}</b>\. Tag: verified\.</p><p><b>Definition:</b> (.*?)</p>", snap.files[snapshot.REPORT])
    if not m:
        raise ValueError(f"report glossary has no verified term {term!r}")
    return m.group(1)


def design_cell(snap, d):
    name = escape(snap.facts["stages"][d]["method"])
    return f'<a href="{links.url("designs/" + d)}">{name}</a>' if d in DESIGN_PAGES else name


def value(v):
    """A stage field as run: a list as list items, else plain text."""
    if isinstance(v, list):
        return "<ul>" + "".join(f"<li>{escape(str(x))}</li>" for x in v) + "</ul>"
    return escape(str(v))


def notation(snap):
    """The kinds of stage, each defined by its notation sentence, then the rest of the notation."""
    f = snap.facts
    text = f["pipeline"]["notation"].removesuffix(" Tag: verified.")
    sentences = re.split(r"(?<=\.) (?=[A-Z])", text)
    count = {k: sum(1 for s in f["stages"].values() for st in s["stages"] if st["kind"] == k) for k in KINDS}
    terms, rest = [], []
    for s in (s.strip() for s in sentences):
        kind = next((k for k, start in DEFINES.items() if s.startswith(start)), None)
        if kind:
            terms.append(f"<dt>{kind}: {escape(KINDS[kind])}</dt><dd>{escape(s)} {count[kind]} "
                         f"stage{'s' if count[kind] != 1 else ''}.</dd>")
        else:
            rest.append(s)
    stages = sum(count.values())
    return section(
        "how-a-design-runs", "How a design runs",
        p(f"Each design runs as a list of stages in {code('harness/workflow/stages.json')}. A stage takes numbered "
          f"steps of its method from {code('tdd-methodologies.md')}, quoted through {code('args.json')}. "
          f"{len(f['stages'])} stage sets hold {stages} stages.", "recomputed"),
        f'<dl class="terms">{"".join(terms)}</dl>', p(escape(" ".join(rest)), "verified"))


def stage_rows(snap, d):
    out = []
    for st in snap.facts["stages"][d]["stages"]:
        rules = ([f"commit cap {st['commit_cap']}"] if "commit_cap" in st else []) + \
                ([f"if {st['when']}"] if "when" in st else []) + \
                [f"with {snap.facts['stages'][w]['method']} steps {joined(n)}" for w, n in st.get("with", {}).items()]
        out.append([design_cell(snap, d), escape(st["id"]), f"{st['kind']} ({escape(KINDS[st['kind']])})",
                    joined(st["steps"]) or "none", escape(st.get("unit", "none")), escape(st.get("returns", "none")),
                    escape("; ".join(rules) or "none")])
    return out


def stage_notes(snap, designs, family):
    """Stage notes sit under the table, as one long note would squeeze its other columns."""
    terms = "".join(f"<dt>{escape(snap.facts['stages'][d]['method'])} {escape(st['id'])}</dt><dd>{escape(st['note'])}</dd>"
                    for d in designs for st in snap.facts["stages"][d]["stages"] if "note" in st)
    return f'<dl class="terms" aria-label="Stage notes: {escape(family)}">{terms}</dl>' if terms else ""


def changes(snap):
    """Stage fields that a run recorded unlike stages.json, grouped by identical change: {(design, stage, field, value
    as JSON): ["run build", ...]}."""
    f, out = snap.facts, {}
    for run, r in f["runs"].items():
        for build, m in r["methods"].items():
            d = m.get("arm") or next(k for k, s in f["stages"].items() if s["method"] == m["method"])
            now = {st["id"]: st for st in f["stages"][d]["stages"]}
            for st in m["stages"]:
                if st["id"] not in now:
                    raise ValueError(f"{run} {build} ran stage {st['id']!r}, which stages.json {d} lacks")
                for field in sorted(set(st) | set(now[st["id"]])):
                    if st.get(field) != now[st["id"]].get(field):
                        out.setdefault((d, st["id"], field, json.dumps(st.get(field))), []).append(f"{run} {build}")
    return out


def stages(snap):
    fam, out = families(snap), []
    head = ["Design", "Stage", "Kind", "Steps", "Unit", "Returns", "Rules"]
    for family in dict.fromkeys(fam.values()):
        designs = [d for d, s in snap.facts["stages"].items() if fam[s["method"]] == family]
        slug = re.sub(r"\W+", "-", family.lower())
        out.append(f'<h3 id="stages-{slug}">{escape(family)}</h3>' +
                   grid(f"Stages: {family}", head, [r for d in designs for r in stage_rows(snap, d)]) +
                   stage_notes(snap, designs, family))
    found = changes(snap)
    rows = [[escape(joined(builds)), escape(snap.facts["stages"][d]["method"]), escape(stage), escape(field),
             value(json.loads(v))] for (d, stage, field, v), builds in found.items()]
    builds = len({b for bs in found.values() for b in bs})
    return section(
        "stages", "Stages",
        p("Each table lists one family's stage sets as stages.json holds them now. Rules name a commit cap, the event "
          "that starts a stage and the steps borrowed from another method. The stage notes follow each table.",
          "verified"), *out,
        '<h3 id="stage-changes">Stages as run</h3>',
        p(f"Each run records the stages it ran. {builds} builds recorded a stage field unlike stages.json. As run, "
          f"<i>with</i> holds the quoted step texts where stages.json holds step numbers.", "recomputed"),
        grid("Stages as run that differ from stages.json", ["Builds", "Design", "Stage", "Field", "As run"], rows))


def tcp_fields(run, tcp):
    dl = "".join(f"<dt>{escape(k)}</dt><dd>{code(v)}</dd>" for k, v in tcp.items() if k not in ("list", "orders"))
    return f'<p>{escape(run)} test list fields.</p><dl class="terms">{dl}</dl>'


def prompts(snap):
    runs, out = snap.facts["runs"], []
    for run, r in runs.items():
        if "list_phase" in r:
            lis = "".join(f"<li>{escape(s)}</li>" for s in r["list_phase"])
            out.append(f'<p>{escape(run)} ran the list phase in {len(r["list_phase"])} steps.</p>'
                       f'<ol aria-label="{escape(run)} list phase">{lis}</ol>')
        if "tcp" in r:
            out.append(tcp_fields(run, r["tcp"]))
    tcp = runs["tcp-1"]
    lst = tcp["tcp"]["list"]
    arms = [[escape(b), escape(m["arm"]), escape(m["prompt"]), escape(m["order"]), escape(m["blind"])]
            for b, m in tcp["methods"].items()]
    orders = [[escape(o), escape(joined(c))] for o, c in tcp["tcp"]["orders"].items()]
    clauses = [[escape(c["id"]), str(c["risk"]), str(c["usage"])] for c in lst["clauses"]]
    candidates = [[escape(c["id"]), escape(joined(c["checks"])), escape(joined(c["relies"])) or "none", str(c["estimate"])]
                  for c in lst["candidates"]]
    return section(
        "prompts", "Prompts and the shared test list",
        p("The test-list order arms share one prompt and one test list. The methods doc states how the list is "
          "written.", "verified"),
        md(methodology(snap, "Shared test list"), "Shared test list steps"), *out,
        p(f"tcp-1 built {len(arms)} arms on the list of tcp-1-list: {len(lst['clauses'])} clauses and "
          f"{len(lst['candidates'])} candidates.", "recomputed"),
        grid("tcp-1 arms", ["Build", "Arm", "Prompt", "Order", "Blind id"], arms),
        grid("Clauses in the tcp-1 list", ["Clause", "Risk", "Usage"], clauses),
        grid("Candidates in the tcp-1 list", ["Candidate", "Checks", "Relies", "Estimate"], candidates),
        grid("tcp-1 candidate orders", ["Order", "Candidates"], orders))


def runs(snap):
    f = snap.facts
    rows, versions = [], []
    for run, r in f["runs"].items():
        caps, doc = r["caps"], snapshot.run_doc(snap, run)
        waves = "; ".join(f"wave {k}: {joined(w)}" for k, w in enumerate(r.get("waves") or [], 1)) or "none"
        name = f'<a href="{links.url("methodology/analysis")}">{escape(run)}</a>' if r.get("harness_delta") else escape(run)
        rows.append([name, escape(r["tag"]), str(len(r["methods"])), escape(r["model"]), escape(r["effort"]),
                     f"iterations {caps['iterations']}, cycles {caps['cycles']}, starts {caps['starts']}", escape(waves),
                     code(doc) + (" (methods text on this site)" if doc == snap.doc else ""), escape(joined(f["dropped"][run]))])
        if h := r.get("harness"):
            delta = (r.get("harness_delta") or {}).get("sha256")
            versions.append([escape(run)] + [code(h[k]) for k in ("commit", "engine_sha256", "runner_tree")] +
                            [escape(h["claude_version"]), code(h["guard_base"]), code(delta) if delta else "none"])
    builds = sum(len(r["methods"]) for r in f["runs"].values())
    rebuilds = sum(len(r["methods"]) for name, r in f["runs"].items() if name.endswith("/rebuild"))
    return section(
        "runs", "Runs and harness versions",
        p(f"{builds} build entries in {len(f['runs'])} run records include {rebuilds} rebuild entries and exclude start clones. "
          f"Doc version is the short sha256 of the methods doc a run was "
          f"built under. Redacted keys name run record fields the snapshot leaves out.", "recomputed"),
        grid("Runs", ["Run", "Tag", "Builds", "Model", "Effort", "Caps", "Waves", "Doc version", "Redacted keys"], rows),
        p(f"{len(versions)} runs record the harness they ran. rep-2/rebuild rebuilt "
          f"{len(f['runs']['rep-2/rebuild']['methods'])} rep-2 replicates on a changed harness and records the sha256 "
          f"of the change.", "recomputed"),
        grid("Harness versions", ["Run", "Harness commit", "Engine sha256", "Runner tree", "Claude version", "Guard base",
                                  "Harness delta sha256"], versions))


def held_out(snap):
    notes = {st["id"]: st["note"] for st in snap.facts["stages"]["held-out"]["stages"] if st["id"] in ("s2", "s3")}
    return section(
        "held-out-split", "The held-out split",
        p(f'Held-out TDD as the methods doc states it. Its <a href="{links.url("designs/held-out")}">design page</a> '
          f"covers its builds.", "verified"),
        md(methodology(snap, "Held-out TDD"), "Held-out TDD steps"),
        p("The separate agent writes the cases in stage s2 and stage s3 splits them. Their notes follow.", "verified"),
        *(f"<blockquote><p><b>{escape(id)}</b>. {escape(note)}</p></blockquote>" for id, note in notes.items()))


def leaves(schema):
    """(item title, criterion title, item schema) for each scored item of the review schema."""
    out = []
    for crit in schema["properties"].values():
        subs = crit["properties"]
        out += [(crit["title"], crit["title"], crit)] if "score" in subs else \
            [(s["title"], crit["title"], s) for s in subs.values()]
    return out


def ranges(item):
    """The score and reason ranges an item's schema allows."""
    score, reason = item["properties"]["score"], item["properties"]["reason"]
    return [f"{score['minimum']} to {score['maximum']}", f"{reason['minLength']} to {reason['maxLength']} characters"]


def review(snap):
    schema = snap.facts["runs"]["full-1"]["review_schema"]
    same = len({json.dumps(r["review_schema"], sort_keys=True) for r in snap.facts["runs"].values()}) == 1
    crit = "".join(f"<dt>{escape(c['title'])}</dt><dd>{escape(c['description'])}</dd>" for c in schema["properties"].values())
    rows = [[escape(item), escape(c), *ranges(leaf)] for item, c, leaf in leaves(schema)]
    return section(
        "blind-review", "Blind review",
        p(f"<b>{escape(schema['title'])}</b>. {escape(schema['description'])}", "verified"),
        p(f"Every run records {'the same' if same else 'its own'} review schema, with {len(rows)} scored items.",
          "recomputed"),
        f'<dl class="terms">{crit}</dl>',
        grid("Blind review criteria", ["Item", "Criterion", "Score", "Reason"], rows),
        p(f"{glossary(snap, 'Blind review and blind rating')} The scores are on the "
          f'<a href="{links.url("data/ratings")}">ratings page</a>.', "verified"))


def dispositions(snap):
    """(design, channel, high flags, verdict) of each audit flag disposition in the report."""
    return re.findall(r"<b>([^<]+)</b>\. Channel: (\w+)\. High flags: (\d+)\. Verdict: ([^.]+)\.",
                      snapshot.section(snap.files[snapshot.REPORT], "audit-flag-dispositions"))


def collect(snap):
    steps = snap.facts["pipeline"]["collect"]
    lists = "".join(
        f'<p>{code(name)} runs {len(s)} steps in order.</p><ol class="collect" aria-label="{escape(name)} steps">' +
        "".join(f"<li>{code(x['name'])}{CHIP if x['skippable'] else ''}</li>" for x in s) +
        "</ol>" for name, s in steps.items())
    found = dispositions(snap)
    rows = [[escape(x) for x in d] for d in found]
    return section(
        "collect-audit", "Collect and audit",
        p(f"After the build stages {code('collect.sh')} collects each run. Its {code('branchStep')} records a step marked "
          f"skippable as skipped when {code('fetchBack')} failed, as the method branch may then be stale.",
          "verified"), lists,
        p(f"<b>Audit flag.</b> {glossary(snap, 'Audit flag')}", "verified"),
        grid("Audit flag dispositions summary", ["Design", "Channel", "High flags", "Verdict"], rows),
        p(f"{len(found)} rows judge {sum(int(d[2]) for d in found)} high flags. The evidence for each is in "
          f'<a href="{links.url("data", "audit-flag-dispositions")}">the audit flag dispositions</a>.', "recomputed"))


def intro():
    return (p(f"This part sets out how the harness runs each design, from the sources {code('harness/workflow/stages.json')}, "
              f"{code('args.json')}, {code('collect.sh')} and {code('tdd-methodologies.md')}, and the run records.") +
            p("Claims carry a tag. Recomputed means redone from source data. Verified means checked against a primary "
              "source. Unchecked means written or judged by an agent and not checked."))


def raters(snap):
    """How many blind raters score each final, as the report words it."""
    m = re.search(r"(\w+) blind raters scored each final", snap.files[snapshot.REPORT])
    if not m:
        raise ValueError("report does not say how many blind raters scored each final")
    return m.group(1).lower()


def roles(snap):
    """F8: the agents of a run by batch phase (Methods, Review, Measure), then collect and rating, with counts from the
    facts. Phases and their order follow the harness sources batch.js, collect.sh and rate.js."""
    f = snap.facts
    sets = [(d, st) for d, s in f["stages"].items() for st in s["stages"]]
    n = {k: sum(1 for _, st in sets if st["kind"] == k) for k in KINDS}
    units = sorted({st["unit"] for _, st in sets if st["kind"] == "L"})
    separate = [(f"{d} {st['id']}", st.get("when")) for d, st in sets
                if st.get("note", "").startswith("You are the separate agent")]
    always, when = [s for s, w in separate if not w], [(s, w) for s, w in separate if w]
    if len(always) != 1 or len(when) != 1:
        raise ValueError(f"expected one separate agent stage that always runs and one with a when: {separate}")
    caps = {r["caps"]["starts"] for r in f["runs"].values()}
    if len(caps) != 1:
        raise ValueError(f"runs differ in their starts cap: {sorted(caps)}")
    one = [s["name"] for s in f["pipeline"]["collect"]["collectOne"]]
    steps = lambda *names: ", ".join(str(one.index(x) + 1) for x in names)
    found = dispositions(snap)
    harness, method, other = "Harness and collect", "Method agent", "Other agents"
    nodes = [
        flow.node("clone", "Fresh clone and prompt", harness, 0,
                  f"{sum(len(r['methods']) for r in f['runs'].values())} entries / {len(f['runs'])} records"),
        flow.node("lister", "Test lister", other, 0, f"{sum('list_phase' in r for r in f['runs'].values())} list-only runs"),
        flow.node("throughout", "Throughout rule (F)", harness, 1, f"{n['F']} stages join every prompt"),
        flow.node("once", "Once stage (S)", method, 1, f"{n['S']} stages"),
        flow.node("writer", "Case writer", other, 2, f"{always[0]}, every build"),
        flow.node("harness", "Harness stage (H)", harness, 3, f"{n['H']} stage"),
        flow.node("repeat", "Repeat stage (L)", method, 3, f"{n['L']} stages, units {joined(units)}"),
        # An edge from once would cross the repeat wrap on the shared gap line, so the note names the input.
        flow.node("transfers", "Harness transfer agents", harness, 4,
                  f"Takes {stage_returning(snap, 'starts')} starts. Seed, winner and list by git"),
        flow.node("starts", "Starts stage", method, 5, f"{n['starts']} stage, parallel attempts"),
        flow.node("fresh", "Fresh case writer", other, 6, f"{when[0][0]} if {when[0][1]}"),
        flow.node("review", "Blind reviewer", other, 7, "Review phase, one per method"),
        flow.node("measure", "Measure agent", method, 8, "Measure phase, one per method"),
        flow.node("audit", "Audit and adherence", harness, 9, f"collectOne steps {steps('audit', 'adherence')} of {len(one)}"),
        flow.node("copy", "Review copy and report", harness, 10, f"collectOne steps {steps('review', 'report')}"),
        flow.node("raters", "Blind raters", other, 10, f"{raters(snap)} per final, after collect"),
        flow.node("report", "Study report", harness, 11,
                  f"{len(found)} disposition rows judge {sum(int(d[2]) for d in found)} high flags"),
    ]
    edges = [flow.edge("lister", "clone", "its list"), flow.edge("clone", "throughout"), flow.edge("throughout", "once"),
             flow.edge("once", "writer", "s2"), flow.edge("once", "repeat"), flow.edge("writer", "harness", "after s3"),
             flow.edge("harness", "repeat"), flow.edge("repeat", "fresh", "if hidden"), flow.edge("repeat", "review"),
             flow.edge("transfers", "starts", f"up to {caps.pop()}"), flow.edge("starts", "review"),
             flow.edge("fresh", "review"), flow.edge("review", "measure"), flow.edge("measure", "audit", "collect"),
             flow.edge("audit", "copy"), flow.edge("copy", "raters"), flow.edge("raters", "report")]
    return nodes, edges, [flow.loop("repeat", "unit")]


def stage_returning(snap, value):
    return next(st["id"] for st in snap.facts["stages"]["multi-start"]["stages"] if st.get("returns") == value)


def agent_roles(snap):
    title = "Agents of a run by phase, then collect and rating"
    nodes, edges, loops = roles(snap)
    svg = flow.svg("f8", title, "In the Methods phase a fresh clone takes throughout rules into each prompt. Method agents "
                   "run once, repeat and starts stages and the harness runs its own stage. Transfer agents seed parallel "
                   "starts by git. A separate agent writes held-out cases in s2 and fresh cases after a hidden failure. "
                   "The Review phase runs one blind reviewer per method and the Measure phase one measure agent. "
                   "Collect then audits, checks adherence, copies the review and renders the report. Blind raters score "
                   "each final after collect.", nodes, edges, loops)
    n = next(parts.numbers("methodology"))
    caption = (f"Stage counts are over all {len(snap.facts['stages'])} stage sets, so one design runs only some kinds. "
               f"{parts.tag('recomputed')} Phases and their order follow the harness sources batch.js, collect.sh and "
               f"rate.js. {parts.tag('verified')}")
    listers = [f"{r['tcp']['lister']}:list" for r in snap.facts["runs"].values() if "list_phase" in r]
    rows = [["Method agent", "Methods", code("<design>:<stage>"), "held-out:s1", "The build clone"],
            ["Separate agent", "Methods", code("<design>:<stage>"), "held-out:s2",
             "The cases and scratch folders, outside the clone the method agents read"],
            ["Harness transfer agents", "Methods", code("harness:<task>-<clone>"),
             "harness:seed-multi-start-1, harness:winner-multi-start",
             "Git fetch and merge between clones at low effort, to seed each start, take the winner and fetch the list"],
            ["Test lister", "Methods (list-only run)",code("<lister>:list"), escape(joined(listers)),
             "Its own clone, where it commits only CLAUSES.md and TESTLIST.md"],
            ["Blind reviewer", "Review", code("review:<blind id>"), "review:r01, review:r02",
             "git diff refs/tags/starter..HEAD of src/ and test/, under a blind id"],
            ["Measure agent", "Measure", code("<clone>:measure"), "rep-1-r01:measure, rep-1-r11:measure",
             "The clone root, where it writes MEASURE.md from LOG.md, git log, GAP.md and ATTEMPTS.md"],
            ["Blind raters", "Rate, after collect", code("rate:<item>:<rater>"), "none in the snapshot",
             "Each item of a rating round, scored on the eight cqp.html principles"]]
    return section(
        "agent-roles", "Agent roles",
        parts.figure(n, "f8", title, svg, caption, None, flow.text_version(title, nodes, edges, loops)),
        grid("Agent roles", ["Role", "Phase", "Label pattern", "Examples from run records", "Where it works"], rows),
        p("Examples are agent labels in the full-1 report and its method pages. Lister labels join each list-only run's "
          "lister field to :list.", "recomputed"),
        p("Where each role works paraphrases the stage notes, the review schema and the harness sources batch.js and "
          "rate.js.", "verified"),
        p(f"Transfer agents run fixed git commands. Ranking the starts is the method's own stage "
          f"{escape(stage_returning(snap, 'winner'))}.", "verified"))


def body(page, snap, idx):
    return [intro(), notation(snap), agent_roles(snap), stages(snap), prompts(snap), runs(snap), held_out(snap), review(snap), collect(snap)]
