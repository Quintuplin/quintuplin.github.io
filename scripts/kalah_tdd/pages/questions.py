"""The critical questions page (#69): the report questions section with its intro kept, Figure 10.1 framing its status
bar, the status table in a labelled region and every answer with its id, a status line and its claim tag."""

import re
from itertools import zip_longest
from typing import NamedTuple

from .. import links, parts, snapshot
from ..blocks import OPEN, close, plain

ID = "questions"
# The statuses the section intro defines.
STATUSES = ("answered", "partly answered", "pending run", "open")
# The blocks after the heading in order, then one answer per question.
LEAD = ("p", "qbar", "qlegend", "qtable")
TABLE = "Status of each question"
TITLE = re.compile(r'<h2 id="([^"]+)">(.*?)</h2>')
DIV = re.compile(r' class="(qbar|qlegend|qtable|answer)"(?= |$)')
TR = re.compile(r"<tr>(?:(?!</tr>).)*</tr>", re.S)
ROW = re.compile(r'<tr><td class="num">(Q\d+)</td><td class="q"><a href="#(q\d+)">(.*?)</a></td><td class="st">(.*?)</td></tr>',
                 re.S)
CHIP = re.compile(r'<span class="chip" data-k="([\w-]+)"><i></i>([^<]*)</span>')
AQ = re.compile(r'<div class="answer" id="([^"]+)"><p class="aq"><b>(Q\d+)</b> (.*?)</p>', re.S)
TAG = re.compile(r'<span class="tag">([^<]*)</span>')


class Row(NamedTuple):
    n: str  # Q1
    question: str  # HTML
    status: str
    kind: str  # the chip's data-k
    chip: str  # HTML


def kind(block):
    m = OPEN.match(block)
    tag, attrs = m.groups()
    if tag == "p" and not attrs:
        return "p"
    d = DIV.match(attrs) if tag == "div" else None
    return d.group(1) if d else None


def split(html):
    """(title, [(kind, block)]) after the section heading. Refuses text, an unknown element or one out of place."""
    head = TITLE.match(html)
    if not head or head.group(1) != ID:
        raise ValueError(f"section {ID} does not open with its h2")
    at, out = head.end(), []
    while html[at:].strip():
        m = OPEN.match(html, at)
        end = close(html, m.group(1), m.end()) if m else -1
        block = html[at:end].strip() if end != -1 else html[at:].strip()
        k = kind(block) if end != -1 else None
        if k != (LEAD[len(out)] if len(out) < len(LEAD) else "answer"):
            raise ValueError(f"section {ID} holds an unrecognised or misplaced block {block[:60]!r}")
        out.append((k, block))
        at = end
    if len(out) <= len(LEAD):
        raise ValueError(f"section {ID} lacks its {', '.join(LEAD[len(out):]) or 'answers'}")
    return head.group(2), out


def rows(qtable):
    """The status table rows. Each needs one chip of a known status, one chip kind per status."""
    out, kinds = [], {}
    for tr in TR.findall(qtable.split("<tbody>", 1)[-1]):
        m = ROW.fullmatch(tr)
        if not m or m[2] != m[1].lower():
            raise ValueError(f"section {ID} has a status row of no known form {plain(tr, ' ')[:60]!r}")
        n, _, question, cell = m.groups()
        chip = CHIP.fullmatch(cell)
        if not chip:
            raise ValueError(f"{n} has no status chip")
        k, status = chip.groups()
        if status not in STATUSES:
            raise ValueError(f"{n} has status {status!r}, not one of {', '.join(STATUSES)}")
        if kinds.setdefault(status, k) != k:
            raise ValueError(f"{n} draws {status} as {k}, other rows as {kinds[status]}")
        out.append(Row(n, question, status, k, cell))
    return out


def tally(rows):
    """{status: rows} in order of first use."""
    out = {}
    for r in rows:
        out.setdefault(r.status, []).append(r)
    return out


def counts(rows, qbar, qlegend):
    """Refuses a status bar or legend that does not draw the row counts. The two are kept as the report has them."""
    by = tally(rows)
    said = [f"{len(rs)} {s}" for s, rs in by.items()]
    said = " and ".join([", ".join(said[:-1]), said[-1]] if len(said) > 1 else said)
    bar = "".join(f'<span class="seg" data-k="{rs[0].kind}" style="flex:{len(rs)}" title="{s} {len(rs)}"></span>'
                  for s, rs in by.items())
    if qbar != f'<div class="qbar" role="img" aria-label="Questions by status: {said}">{bar}</div>':
        raise ValueError(f"section {ID}: the qbar does not draw the row counts {said}: {qbar[:80]!r}")
    if qlegend != '<div class="qlegend">' + "".join(f'{rs[0].chip}<b class="cnt">{len(rs)}</b>' for rs in by.values()) + "</div>":
        raise ValueError(f"section {ID}: the qlegend does not count the rows as {said}")


def figure(n, rows, bar):
    """Figure n: the report status bar and legend, with a text version naming each status's questions."""
    text = [f"{s[:1].upper()}{s[1:]}: {len(rs)} question{'s' * (len(rs) != 1)}, {', '.join(r.n for r in rs)}"
            for s, rs in tally(rows).items()]
    caption = (f"Each segment is one status, as wide as its number of questions. The counts match the status of every "
               f"row in the table below. Tag: {parts.tag('recomputed')}.")
    return parts.figure(n, "question-status", "Questions by status", bar, caption, "#question-table", text)


def answers(rows, blocks):
    """Each answer in table order with a status line after its question, refused unless its id, question and single
    claim tag agree with its row."""
    out = []
    for row, block in zip_longest(rows, blocks):
        want = row.n.lower() if row else None
        m = AQ.match(block) if block else None
        if not row or not m or m[1] != want:
            got = m[1] if m else "none" if block is None else repr(block[:40])
            raise ValueError(f"answer {len(out) + 1} is {got} where the table has {want or 'no row'}")
        if m[2] != row.n:
            raise ValueError(f"answer {want} is labelled {m[2]} where its row is {row.n}")
        if plain(m[3], " ") != plain(row.question, " "):
            raise ValueError(f"answer {want} asks {plain(m[3], ' ')!r} where its row asks {plain(row.question, ' ')!r}")
        tags, marked = TAG.findall(block), block.count('class="tag"')
        if len(tags) != 1 or marked != 1:
            raise ValueError(f"answer {want} holds {marked} tag spans, {len(tags)} of them plain parts.tag markup; "
                             f"it needs one of each")
        try:
            tag = parts.tag(tags[0])
        except ValueError as e:
            raise ValueError(f"answer {want}: {e}") from None
        # The tag markup comes from parts.tag, so every page draws claim tags alike.
        block = TAG.sub(tag, block)
        if want == "q3":
            if block.count("<p>Yes.</p>") != 1:
                raise ValueError("Q3 reference interpretation needs review")
            block = block.replace("<p>Yes.</p>", "<p>The reference passes the grader.</p>")
        if want == "q15":
            block = block.removesuffix("</div>") + ('<p>The Held-out TDD contrast spans a later rebuild. See '
                f'<a href="{links.url("results/contrasts", "planned-contrasts-rep-2")}">rep-2 planned contrasts</a> and '
                f'<a href="{links.url("methodology/analysis", "limits")}">limits</a>.</p></div>')
        out.append(f"{block[:m.end()]}<p>Status: {row.chip}</p>{block[m.end():]}")
    return out


def section(html, n):
    """The questions section with its links already pointed at the study pages, and Figure n of its status bar."""
    title, found = split(html)
    (_, intro), (_, qbar), (_, qlegend), (_, qtable) = found[:len(LEAD)]
    table = rows(qtable)
    counts(table, qbar, qlegend)
    return (f'<section aria-labelledby="{ID}"><h2 id="{ID}">{title}</h2>{intro}{figure(n, table, qbar + qlegend)}'
            f'<h3 id="question-table">{TABLE}</h3>{parts.table(qtable, TABLE)}<h3 id="answers">Answers</h3>'
            + "".join(answers(table, [b for _, b in found[len(LEAD):]])) + "</section>")


def body(page, snap, idx):
    html = links.rewrite(snapshot.section(snap.files[snapshot.REPORT], ID), snapshot.REPORT, page.slug, idx)
    return [section(html, next(parts.numbers(page.slug)))]
