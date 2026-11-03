"""The four results pages (#89): each report results section verbatim, its heading as h2 with its id kept, report
figures numbered by part and free tables in a region named by the section title."""

import re
from html import escape

from .. import links, parts, snapshot

CONTRASTS = "results/contrasts"
# The rep-1 adjusted mutation chart is a report Headline figure, so it sits on the landing page.
REP1_MUTATION = "rep-1-mutation"
OPEN = re.compile(r"\s*<([a-z][a-z0-9]*)\b([^>]*)>")
TITLE = re.compile(r"<h([23]) id=\"([^\"]+)\">(.*?)</h\1>")


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


def body(page, snap, idx):
    numbers = parts.numbers(page.slug)
    out = [lead(snap, idx)] if page.slug == CONTRASTS else []
    return out + [section(snap, idx, page.slug, id, numbers) for id in page.anchors]
