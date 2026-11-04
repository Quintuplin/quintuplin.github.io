"""The four results pages (#89): each report results section verbatim, its heading as h2 with its id kept, report
figures numbered by part and free tables in a region named by the section title. Contrasts opens with a Holm p
headline read from the contrast cells (#90)."""

import re
from html import escape, unescape
from typing import NamedTuple

from .. import links, parts, snapshot
from ..figures import dots, flow

CONTRASTS = "results/contrasts"
# The rep-1 adjusted mutation chart is a report Headline figure, so it sits on the landing page.
REP1_MUTATION = "rep-1-mutation"
OPEN = re.compile(r"\s*<([a-z][a-z0-9]*)\b([^>]*)>")
TITLE = re.compile(r"<h([23]) id=\"([^\"]+)\">(.*?)</h\1>")
# Each contrast section: its run, how many planned contrasts its cells hold and the outcome of a cell that names none.
CONTRAST_RUNS = {"planned-contrasts-rep-1": ("rep-1", 2, "adjusted mutation"),
                 "planned-contrasts-rep-2": ("rep-2", 6, None)}
# Classic greedy TDD is the baseline of every contrast it is in, so it is named second.
BASELINE = "Classic greedy TDD"
OUTCOMES = ("adjusted mutation", "M")  # series 1 and 2 of the headline
ALPHA = 0.05
CLAUSE = re.compile(r"(?:(M|adjusted mutation) )?against (.+?): U (\d+), Holm p ([\d.]+)")
# A method's table row or entry, and its name, replicates and planned contrast cell in either form.
BLOCK = re.compile(r'<tr>.*?</tr>|<div class="entry">.*?</div>', re.S)
METHOD = re.compile(r'data-th="Method">([^<]*)<|<p class="sub"><b>([^<]*)</b>')
REPLICATES = re.compile(r'data-th="Replicates">(\d+)<|Replicates: (\d+)\.')
PLANNED = re.compile(r'data-th="Planned contrast">([^<]*)<|<b>Planned contrast:</b> ([^<]*)</p>')
TEST_ORDER = "results/test-order"
Q20 = re.compile(r"APFD-I on the calls basis was ([\d.]+) for (\w+), ([\d.]+) for (\w+), ([\d.]+) for (\w+), ([\d.]+) "
                 r"for (\w+) and ([\d.]+) for (\w+)\. APFDc-H was ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+) and ([\d.]+) "
                 r"in the same order\.")
# A tcp-1 stage kind's lane and its steps header, as G9's stage flow names them.
LANE = {"F": "Throughout", "L": "Agent"}
RUNS_AS = {"F": "throughout:", "L": "repeat per {unit} until none is open:"}
# Columns of short numbers and ids, held on one line so a phone width does not split them mid-token.
SHORT = frozenset({"Run", "U", "Holm p", "Order", "APFD-I", "APFDc-H", "Clause", "Risk", "Usage", "Candidate", "Estimate",
                   "Stage", "Steps"})


class Contrast(NamedTuple):
    run: str
    outcome: str
    method: str
    against: str
    u: int
    p: str


def close(html, tag, at):
    """The end of the element whose start tag ends at at, counting nested elements of the same tag."""
    depth = 1
    for m in re.compile(rf"<(/?){tag}\b[^>]*>").finditer(html, at):
        depth += -1 if m.group(1) else 1
        if not depth:
            return m.end()
    return -1


def kind(block):
    """p, figure, tables or entries, or None for a block the page does not know."""
    m = OPEN.match(block)
    tag, attrs = m.groups()
    if tag in ("p", "figure") and (tag == "figure" or not attrs):
        return tag
    if tag == "div" and attrs == ' class="shaped"':
        inner = block[m.end():-len("</div>")]
        kids = re.sub(r'<table class="cols">.*?</table>', "", inner, flags=re.S)
        if inner != kids and not kids.strip():
            return "tables"
        if not re.sub(r'<div class="entry">(?:<p\b[^>]*>.*?</p>)+</div>', "", inner, flags=re.S).strip() and inner:
            return "entries"
    return None


def split(id, html):
    """(kind, block) for each top-level element after the section heading. Refuses text or an element it cannot place."""
    head = TITLE.match(html)
    if not head or head.group(2) != id:
        raise ValueError(f"section {id} does not open with its h2 or h3")
    at, out = head.end(), []
    while html[at:].strip():
        m = OPEN.match(html, at)
        end = close(html, m.group(1), m.end()) if m else -1
        block = html[at:end].strip() if end != -1 else html[at:].strip()
        if end == -1 or not (k := kind(block)):
            raise ValueError(f"section {id} holds an unrecognised block {block[:60]!r}")
        out.append((k, block))
        at = end
    return out


def own(html, id):
    """The report section of this heading up to its first nested heading with an id."""
    sec = snapshot.section(html, id)
    nested = snapshot.HEADING.search(sec, 1)
    return sec[:nested.start()] if nested else sec


def section(snap, idx, slug, id, numbers, extra=lambda numbers: ""):
    """The report section id on page slug: its heading as h2, its links pointed at the study pages, figures numbered,
    then the HTML of extra(numbers), built after the section's figures so its own figures number after theirs."""
    html = links.rewrite(own(snap.files[snapshot.REPORT], id), snapshot.REPORT, slug, idx)
    title = TITLE.match(html).group(3)
    framed = {"p": str, "entries": str, "figure": lambda b: parts.source_figure(next(numbers), b),
              "tables": lambda b: parts.table(b.removeprefix('<div class="shaped">').removesuffix("</div>"), title)}
    body = "".join(framed[k](b) for k, b in split(id, html))
    return f'<section aria-labelledby="{id}"><h2 id="{id}">{title}</h2>{body}{extra(numbers)}</section>'


def lead(snap, idx):
    href = links.target(f"#{REP1_MUTATION}", snapshot.REPORT, CONTRASTS, idx)
    return (f'<p>Adjusted mutation per replicate in rep-1 is a headline figure, so it is on the '
            f'<a href="{escape(href)}">study landing page</a>. This page holds the other planned contrast figures.</p>')


def found(regex, text):
    m = regex.search(text)
    return unescape(next(g for g in m.groups() if g is not None)) if m else None


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def cap(text):
    return text[:1].upper() + text[1:]


def cells(sec, run, default):
    """({(outcome, method, against): (U, Holm p)}, {method: replicates}) from a section's rows and entries."""
    out, reps = {}, {}
    for block in BLOCK.findall(sec):
        if not (method := found(METHOD, block)):
            continue
        if n := found(REPLICATES, block):
            reps[method] = int(n)
        for clause in filter(None, (found(PLANNED, block) or "").split("; ")):
            m = CLAUSE.fullmatch(clause)
            if not m or not (m[1] or default):
                raise ValueError(f"{run}: {method} has a planned contrast cell {clause!r} of no known form")
            out[(m[1] or default, method, m[2])] = (int(m[3]), m[4])
    return out, reps


def holm(report):
    """Every planned contrast with the U of its first side and its Holm p. Both sides' cells must agree, as
    U sums to the product of the replicates, and the Holm p must be in the section lead."""
    out = []
    for id, (run, want, default) in CONTRAST_RUNS.items():
        sec = own(report, id)
        lead = plain(re.search(r"<p>(.*?)</p>", sec, re.S).group(1))
        sides, reps = cells(sec, run, default)
        done, pairs = set(), []
        for outcome, a, b in sides:
            if (outcome, a, b) in done:
                continue
            first, base = (b, a) if a == BASELINE else (a, b)
            where = f"{run} {outcome} contrast {first} against {base}"
            if {(outcome, first, base), (outcome, base, first)} - sides.keys():
                raise ValueError(f"{where} lacks the cell of one side")
            (u, p), (u2, p2) = sides[(outcome, first, base)], sides[(outcome, base, first)]
            if p != p2 or u + u2 != reps.get(first, 0) * reps.get(base, 0):
                raise ValueError(f"{where}: its sides give U {u} and {u2}, Holm p {p} and {p2}")
            if not re.search(rf"Holm p {re.escape(p)}(?!\d)", lead):
                raise ValueError(f"{where}: Holm p {p} is not in the {run} lead")
            done |= {(outcome, first, base), (outcome, base, first)}
            pairs.append(Contrast(run, outcome, first, base, u, p))
        if len(pairs) != want:
            said = "; ".join(f"{c.outcome} {c.method} against {c.against}" for c in pairs)
            raise ValueError(f"{run} gives {len(pairs)} planned contrasts, expected {want}: {said}")
        order = list(dict.fromkeys(c.outcome for c in pairs))
        out += sorted(pairs, key=lambda c: order.index(c.outcome))
    return out


def table(columns, rows, label, short=SHORT):
    """A plain table of text cells in a labelled scroll region. Cells of the short columns never wrap."""
    keep = [' class="nowrap"' if c in short else "" for c in columns]
    head = "".join(f'<th scope="col"{k}>{escape(c)}</th>' for c, k in zip(columns, keep))
    body = "".join("<tr>" + "".join(f"<td{k}>{escape(str(v))}</td>" for v, k in zip(row, keep)) + "</tr>" for row in rows)
    return parts.table(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>", label)


def contrast_holm(report, n):
    """The headline section: Figure n of each contrast's Holm p, then h3#contrast-holm with its table."""
    rows, title = holm(report), "Holm p of each planned contrast"
    marks = [dots.Mark(f"{c.run}: {c.method} against {c.against}", float(c.p),
                       f"{c.run} {c.outcome}, {c.method} against {c.against}: U {c.u}, Holm p {c.p}",
                       OUTCOMES.index(c.outcome), float(c.p) >= ALPHA) for c in rows]
    svg = dots.svg(f"{title}, one row per pair of methods", "Holm p", tuple(map(cap, OUTCOMES)), marks, (0, 1),
                   (0, 0.2, 0.4, 0.6, 0.8, 1), [dots.Ref(ALPHA, f"Holm p {ALPHA}")])
    caption = (f"The {len(rows)} planned contrasts of rep-1 and rep-2, read from the contrast cells in the sections below. "
               "Both sides of each contrast agree and each Holm p is in its section lead. Filled marks fall below the "
               f"dashed line at {ALPHA} and hollow marks do not. Tag: {parts.tag('recomputed')}.")
    fig = parts.figure(n, "fig-" + n.replace(".", "-"), title, svg, caption, "#contrast-holm", [m.title for m in marks])
    runs = list(dict.fromkeys(c.run for c in rows))
    said = " and ".join(f"{run} hold {sum(c.run == run for c in rows)}" for run in runs)
    return (f'<section aria-labelledby="holm"><h2 id="holm">Holm p across the planned contrasts</h2>'
            f"<p>The contrast cells of {said} planned contrasts, each an exact Mann-Whitney U test with Holm "
            f"correction. Figure {n} shows where each Holm p falls against {ALPHA}.</p>{fig}"
            f'<h3 id="contrast-holm">Planned contrasts with U and Holm p</h3>'
            f"<p>U is that of the method named first. Tag: {parts.tag('recomputed')}.</p>"
            + table(("Run", "Outcome", "Contrast", "U", "Holm p"),
                    [(c.run, cap(c.outcome), f"{c.method} against {c.against}", c.u, c.p) for c in rows],
                    "Planned contrasts with U and Holm p") + "</section>")


def q20(report):
    """{order: (APFD-I, APFDc-H)} as the Q20 answer states them."""
    answer = re.search(r'<div class="answer" id="q20">(.*?)</div>', report, re.S)
    m = answer and Q20.search(plain(answer.group(1)))
    if not m:
        raise ValueError("Q20 no longer states APFD-I and APFDc-H per order in the known form")
    g = m.groups()
    return {g[2 * i + 1]: (g[2 * i], g[10 + i]) for i in range(5)}


def tcp_orders(facts):
    """{order: its arm or None} for each tcp-1 list order. Every arm's order must be listed and run by no other arm,
    and every order may name only list candidates."""
    tcp = facts["runs"]["tcp-1"]["tcp"]
    known = {c["id"] for c in tcp["list"]["candidates"]}
    for name, order in tcp["orders"].items():
        if unknown := [c for c in order if c not in known]:
            raise ValueError(f"tcp-1 order {name} names candidates {unknown} that are not on the list")
    arms = {}
    for arm, m in facts["runs"]["tcp-1"]["methods"].items():
        if m["order"] not in tcp["orders"]:
            raise ValueError(f"tcp-1 arm {arm} runs order {m['order']}, which the list does not give")
        if other := arms.get(m["order"]):
            raise ValueError(f"tcp-1 arms {other} and {arm} both run order {m['order']}")
        arms[m["order"]] = arm
    return {name: arms.get(name) for name in tcp["orders"]}


def tcp_stages(facts):
    """The stages every tcp-1 arm shares. Each facts.stages tcp design and each arm must list the same stages and steps."""
    methods = facts["runs"]["tcp-1"]["methods"]
    first = next(iter(methods.values()))
    lists = {k: v["stages"] for k, v in facts["stages"].items() if k.startswith("tcp-")}
    lists |= {arm: m["stages"] for arm, m in methods.items()}
    if differ := [k for k, v in lists.items() if v != first["stages"]] + [a for a, m in methods.items()
                                                                          if m["steps"] != first["steps"]]:
        raise ValueError(f"tcp-1 stages or steps differ in {differ}")
    return first["stages"]


def ol(items):
    return "<ol>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ol>"


def sized(svg):
    """The flow held at its drawn width, so a one column chart does not scale up to study.css's flow min-width."""
    width = re.match(r'<svg [^>]*viewBox="0 0 (\d+) ', svg).group(1)
    return svg.replace("<svg ", f'<svg style="max-width:{width}px;min-width:{width}px" ', 1)


def tcp_results(report, facts, slug, idx, n):
    """The Q20 link, Figure n of APFD-I and APFDc-H per order against random, then h3#tcp-results with its table."""
    values = q20(report)
    if set(values) != {m["order"] for m in facts["runs"]["tcp-1"]["methods"].values()}:
        raise ValueError(f"Q20 orders {list(values)} are not the tcp-1 arm orders")
    names, rand = ("APFD-I", "APFDc-H"), values["random"]
    marks = [dots.Mark(order, float(v[i]), f"{order}: {name} {v[i]}", i, float(v[i]) <= float(rand[i]))
             for order, v in values.items() if order != "random" for i, name in enumerate(names)]
    title = "APFD-I and APFDc-H by test-list order"
    svg = dots.svg(f"{title}, one row per order with random as dashed lines", "Hidden-pass curve area", names, marks,
                   (0.4, 0.7), (0.4, 0.5, 0.6, 0.7), [dots.Ref(float(v), f"Random {name} {v}") for name, v in zip(names, rand)])
    caption = (f"Each order ran once, so the values are descriptive. Hollow marks are at or below random. "
               f"Tag: {parts.tag('recomputed')}, from Q20.")
    href = escape(links.target("#q20", snapshot.REPORT, slug, idx))
    return (f'<p>Figure {n} plots the APFD-I and APFDc-H values that <a href="{href}">Q20</a> reports for each order.</p>'
            + parts.figure(n, "fig-" + n.replace(".", "-"), title, svg, caption, "#tcp-results", [m.title for m in marks])
            + f'<h3 id="tcp-results">APFD-I and APFDc-H per order</h3><p>Tag: {parts.tag("recomputed")}, from Q20.</p>'
            + table(("Order", *names), [(o, *v) for o, v in values.items()], "APFD-I and APFDc-H per order"))


def tcp_design(snap, n):
    """The h2#tcp-design section: settings, list phase, clauses, candidates, orders, arm steps and Figure n."""
    facts = snap.facts
    tcp, arm = facts["runs"]["tcp-1"]["tcp"], next(iter(facts["runs"]["tcp-1"]["methods"].values()))
    arms, stages = tcp_orders(facts), tcp_stages(facts)
    settings = [("Seed", tcp["seed"]), ("Lister", tcp["lister"]), ("List run", tcp["list_tag"]), ("List sha", tcp["sha"][:8])]
    settings += [(f"Methods doc, {r}", snapshot.run_doc(snap, r)) for r in ("tcp-1", tcp["list_tag"], "tcp-1-list2")]
    span = lambda ns: f"{ns[0]} and {ns[1]}" if len(ns) == 2 else ", ".join(map(str, ns))
    nodes = [flow.node(s["id"], f"Steps {span(s['steps'])}", LANE[s["kind"]], 0,
                       f"Returns {s['returns']}" if "returns" in s else "") for s in stages]
    loops = [flow.loop(s["id"], s["unit"]) for s in stages if s["kind"] == "L"]
    title = "Stage flow of a tcp-1 arm"
    svg = sized(flow.svg("f9", title, f"{len(nodes)} stages: list rules throughout, then one loop per candidate.",
                         nodes, (), loops))
    caption = f"Every arm and tcp design lists these stages. Details are in the stage table. Tag: {parts.tag('verified')}."
    fig = parts.figure(n, "fig-" + n.replace(".", "-"), title, svg, caption, "#tcp-stages", flow.text_version(title, nodes, (), loops))
    stage_rows = [(s["id"], RUNS_AS[s["kind"]].format(unit=s.get("unit")), span(s["steps"]),
                   "; ".join(f"{k} {s[k]}" for k in ("unit", "returns") if k in s) or "none", s.get("note", "none"))
                  for s in stages]
    return (f'<section aria-labelledby="tcp-design"><h2 id="tcp-design">Design of run tcp-1</h2>'
            f"<p>The settings, list and orders of run tcp-1 as its run facts give them. Tag: {parts.tag('verified')}.</p>"
            f'<h3 id="tcp-settings">Settings</h3>' + table(("Setting", "Value"), settings, "Settings of run tcp-1")
            + f'<h3 id="tcp-list-phase">List phase steps</h3><p>The lister of run {tcp["list_tag"]} followed these steps.</p>'
            + ol(facts["runs"][tcp["list_tag"]]["list_phase"])
            + '<h3 id="tcp-clauses">Clauses</h3>'
            + table(("Clause", "Risk", "Usage"), [(c["id"], c["risk"], c["usage"]) for c in tcp["list"]["clauses"]], "Clauses")
            + '<h3 id="tcp-candidates">Candidates</h3>'
            + table(("Candidate", "Checks", "Relies", "Estimate"),
                    [(c["id"], ", ".join(c["checks"]), ", ".join(c["relies"]) or "none", c["estimate"])
                     for c in tcp["list"]["candidates"]], "Candidates")
            + '<h3 id="tcp-orders">Orders</h3>'
            + table(("Order", "Arm", "Candidates in order"),
                    [(o, arms[o] or "not run", ", ".join(c)) for o, c in tcp["orders"].items()], "Orders")
            + '<h3 id="tcp-arm-steps">Arm steps</h3><p>Every arm followed these steps.</p>' + ol(arm["steps"])
            + fig + '<h3 id="tcp-stages">Stages</h3>'
            + table(("Stage", "Runs as", "Steps", "Details", "Note"), stage_rows, "Stages of a tcp-1 arm") + "</section>")


def body(page, snap, idx):
    numbers, report = parts.numbers(page.slug), snap.files[snapshot.REPORT]
    if page.slug == TEST_ORDER:
        if len(page.anchors) != 1:
            raise ValueError(f"{page.slug} lists report sections {list(page.anchors)}; the Q20 figures follow exactly one")
        sec = section(snap, idx, page.slug, page.anchors[0], numbers,
                      lambda n: tcp_results(report, snap.facts, page.slug, idx, next(n)))
        return [sec, tcp_design(snap, next(numbers))]
    out = [lead(snap, idx), contrast_holm(report, next(numbers))] if page.slug == CONTRASTS else []
    return out + [section(snap, idx, page.slug, id, numbers) for id in page.anchors]
