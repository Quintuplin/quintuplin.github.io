"""The four results pages (#89): each report results section verbatim, its heading as h2 with its id kept, report
figures numbered by part and free tables in a region named by the section title. Contrasts opens with a Holm p
headline read from the contrast cells (#90)."""

import re
from html import escape, unescape
from typing import NamedTuple

from .. import links, parts, snapshot
from ..figures import dots

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


def section(snap, idx, slug, id, numbers):
    """The report section id on page slug: its heading as h2, its links pointed at the study pages, figures numbered."""
    html = links.rewrite(own(snap.files[snapshot.REPORT], id), snapshot.REPORT, slug, idx)
    title = TITLE.match(html).group(3)
    framed = {"p": str, "entries": str, "figure": lambda b: parts.source_figure(next(numbers), b),
              "tables": lambda b: parts.table(b.removeprefix('<div class="shaped">').removesuffix("</div>"), title)}
    body = "".join(framed[k](b) for k, b in split(id, html))
    return f'<section aria-labelledby="{id}"><h2 id="{id}">{title}</h2>{body}</section>'


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
            if f"Holm p {p}" not in lead:
                raise ValueError(f"{where}: Holm p {p} is not in the {run} lead")
            done |= {(outcome, first, base), (outcome, base, first)}
            pairs.append(Contrast(run, outcome, first, base, u, p))
        if len(pairs) != want:
            raise ValueError(f"{run} gives {len(pairs)} planned contrasts, expected {want}")
        order = list(dict.fromkeys(c.outcome for c in pairs))
        out += sorted(pairs, key=lambda c: order.index(c.outcome))
    return out


def table(columns, rows, label):
    """A plain table of text cells in a labelled scroll region."""
    head = "".join(f'<th scope="col">{escape(c)}</th>' for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
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


def body(page, snap, idx):
    numbers = parts.numbers(page.slug)
    out = [lead(snap, idx), contrast_holm(snap.files[snapshot.REPORT], next(numbers))] if page.slug == CONTRASTS else []
    return out + [section(snap, idx, page.slug, id, numbers) for id in page.anchors]
