"""The glossary and supporting data pages (#70): each report section of the page with every block kept, report h3 as
h2 and h4 as h3, every table in a labelled scroll region and every fold open."""

import re
from collections import Counter
from html import escape, unescape

from .. import links, pagemap, parts, snapshot

ANCHORS = {a for p in pagemap.PAGES for a in p.anchors}
HEADING = re.compile(r'<h[1-6]\b[^>]*' + snapshot.ID_ATTR + r'([^"]+)"')
OPEN = re.compile(r"\s*<([a-z][a-z0-9]*)\b([^>]*)>")
TITLE = re.compile(r'<h([2-4]) id="([^"]+)">(.*?)</h\1>', re.S)
FOLD = re.compile(r'<details( id="[^"]+")?>(<summary>[^<]*</summary>)(<div class="shaped">.*</div>)</details>', re.S)
ENTRY, COLS = ("div", ' class="entry"'), ("table", ' class="cols"')
# A report h3 heads a page section under the page h1, so it becomes h2, and an h4 becomes h3.
LEVEL = {"2": 2, "3": 2, "4": 3}
SLOT = re.compile("\0(\\d+)\0")
DATA = ("data", "data/contrasts", "data/methods", "data/ratings", "data/runs")
MEASURES = "methodology/measures"
# One site sentence above the report text, as the page title alone does not say what its tables hold.
LEADS = {
    "data/contrasts": "<p>The planned contrasts, the consistency table and every replicate build of runs rep-1 and rep-2.</p>",
    "data/methods": (f'<p>One row per method of run full-1. <a href="{links.url(MEASURES, "columns")}">Columns</a> '
                     "on the measures page defines each of the 32 columns.</p>"),
    "data/ratings": ("<p>How far a second lister agreed on the test list of run tcp-1-list, and how far the three blind "
                     "raters agreed in runs full-1, rep-1 and rep-2.</p>"),
    "data/runs": ("<p>The run records of full-1, rep-1 and rep-2: their settings, cap hits, failed collection steps and "
                  "unattributed agents.</p>"),
}


def close(html, tag, at):
    """The end of the element whose start tag ends at at, counting nested elements of the same tag."""
    depth = 1
    for m in re.compile(rf"<(/?){tag}\b[^>]*>").finditer(html, at):
        depth += -1 if m.group(1) else 1
        if not depth:
            return m.end()
    return -1


def elements(id, html):
    """(tag, attrs, block) of each top-level element in order. Refuses text outside them."""
    at, out = 0, []
    while html[at:].strip():
        m = OPEN.match(html, at)
        end = close(html, m.group(1), m.end()) if m else -1
        if end == -1:
            raise ValueError(f"section {id} holds an unrecognised block {html[at:].strip()[:60]!r}")
        out.append((m.group(1), m.group(2), html[at:end].strip()))
        at = end
    return out


def shaped(id, block):
    """(ENTRY or COLS, its children) of a div.shaped, which holds entries or table column slices alone."""
    kids = elements(id, block[len('<div class="shaped">'):-len("</div>")])
    kinds = {(t, a) for t, a, _ in kids}
    if len(kinds) != 1 or not kinds <= {ENTRY, COLS}:
        odd = next((b for t, a, b in kids if (t, a) not in (ENTRY, COLS)), block)
        raise ValueError(f"section {id} holds an unrecognised block {odd[:60]!r} in a shaped list")
    return kinds.pop(), [b for _, _, b in kids]


def kind(id, tag, attrs, block):
    if TITLE.fullmatch(block):
        return "heading"
    if tag in ("p", "ul") and not attrs:
        return tag
    if (tag, attrs) == ("div", ' class="shaped"'):
        return "shaped"
    if tag == "details" and FOLD.fullmatch(block):
        return "fold"
    raise ValueError(f"section {id} holds an unrecognised block {block[:60]!r}")


def split(id, html):
    """[(kind, block)] of a report section: heading, p, ul, shaped or fold. ValueError names the section and block."""
    out = [(kind(id, *e), e[2]) for e in elements(id, html)]
    for k, block in out:
        if k in ("shaped", "fold"):
            shaped(id, block if k == "shaped" else FOLD.fullmatch(block).group(3))
    return out


def cut(html, id):
    """The report section of this heading, ended early at a heading that a page takes over."""
    sec = snapshot.section(html, id)
    return sec[:next((m.start() for m in HEADING.finditer(sec, 1) if m.group(1) in ANCHORS), len(sec))].strip()


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", html)).split())


def frame(id, html, entry=lambda block: block):
    """The page html of one section's blocks, with entry applied to each entry. A table's region is labelled by its
    headings, numbered when they hold several, as a wide report table comes in column slices."""
    chain, tables, out = [], [], []
    for k, block in split(id, html):
        if k == "heading":
            level, hid, text = TITLE.fullmatch(block).groups()
            chain = [c for c in chain if c[0] < level] + [(level, plain(text))]
            block = f'<h{LEVEL[level]} id="{hid}">{text}</h{LEVEL[level]}>'
        elif k in ("shaped", "fold"):
            attrs, summary, inner = FOLD.fullmatch(block).groups() if k == "fold" else ("", "", block)
            what, kids = shaped(id, inner)
            if what == ENTRY:
                kids = map(entry, kids)
            else:
                tables += [(", ".join(t for _, t in chain), t) for t in kids]
                kids = (f"\0{i}\0" for i in range(len(tables) - len(kids), len(tables)))
            inner = '<div class="shaped">' + "".join(kids) + "</div>"
            block = inner if k == "shaped" else f"<details{attrs or ''} open>{summary}{inner}</details>"
        out.append(block)
    total, seen, labels = Counter(b for b, _ in tables), Counter(), []
    for base, _ in tables:
        seen[base] += 1
        labels.append(base if total[base] == 1 else f"{base}, part {seen[base]} of {total[base]}")
    return SLOT.sub(lambda m: parts.table(tables[int(m[1])][1], labels[int(m[1])]), "".join(out))


def section(page, snap, idx, id, extra="", entry=lambda block: block):
    """One report section with its links pointed at the study pages, as a labelled page section with extra last."""
    html = links.rewrite(cut(snap.files[snapshot.REPORT], id), snapshot.REPORT, page.slug, idx)
    return f'<section aria-labelledby="{id}">{frame(id, html, entry)}{extra}</section>'


def lead(page):
    """The five data pages, each with its blurb."""
    current = ' aria-current="page"'
    items = "".join(f'<li><a href="{links.url(s)}"{current * (s == page.slug)}>{escape(pagemap.BY_SLUG[s].nav)}</a>. '
                    f"{escape(pagemap.BY_SLUG[s].blurb)}</li>" for s in DATA)
    return f"<p>The supporting data takes five pages.</p><ul>{items}</ul>"


def body(page, snap, idx):
    extras = {"supporting-data": lead(page)}
    out = [LEADS[page.slug]] if page.slug in LEADS else []
    return out + [section(page, snap, idx, a, extras.get(a, "")) for a in page.anchors]
