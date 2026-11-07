"""The glossary and supporting data pages (#70): each report section of the page with every block kept, report h3 as
h2 and h4 as h3, every table in a labelled scroll region and every fold open. The glossary gives each row an id, a
measures link after each measured row and ends with the showcase short forms, each linked to its full entry."""

import re
from collections import Counter
from html import escape

from .. import links, pagemap, parts, snapshot
from ..blocks import elements, plain
from . import measures

ANCHORS = {a for p in pagemap.PAGES for a in p.anchors}
HEADING = re.compile(r'<h[1-6]\b[^>]*' + snapshot.ID_ATTR + r'([^"]+)"')
TITLE = re.compile(r'<h([2-4]) id="([^"]+)">(.*?)</h\1>', re.S)
FOLD = re.compile(r'<details( id="[^"]+")?>(<summary>[^<]*</summary>)(<div class="shaped">.*</div>)</details>', re.S)
ENTRY, COLS = ("div", ' class="entry"'), ("table", ' class="cols"')
# A report h3 heads a page section under the page h1, so it becomes h2, and an h4 becomes h3.
LEVEL = {"2": 2, "3": 2, "4": 3}
SLOT = re.compile("\0(\\d+)\0")
DATA = ("data", "data/contrasts", "data/methods", "data/ratings", "data/runs")
MEASURES = "methodology/measures"
# Glossary rows whose metric measures defines with its formula, each with the metric whose dfn the link goes to.
MEASURED = {"Awards and E": "E", "APFD-I": "APFD-I", "Kendall distance": "Kendall distance", "M and M_io": "M",
            "CQP and CQP accepted": "CQP"}
# Each showcase short form and the glossary row that defines it in full, by subject where no row has its name.
SHORT_FORMS = {"Functional mark": "Functional mark /15", "E": "Awards and E", "Cost to completion": "Cost to completion",
               "M": "M and M_io", "M_io": "M and M_io", "Alignment": "Awards and E",
               "C": "Relative spread and consistency score C", "PMD": "PMD and strict PMD compliance",
               "Weighted tokens": "Weighted tokens", "APFDc-H": "APFDc-H", "CQP": "CQP and CQP accepted",
               "Adjusted mutation": "Adjusted mutation score", "Planned contrast": "Planned contrast",
               "U": "Planned contrast", "Holm": "Planned contrast"}
VIEWS = ("summary", *(d[0] for d in pagemap.DESIGNS))
ROW = re.compile(r'<div class="entry"><p class="sub"><b>(.*?)</b>')
TERMS = re.compile(r'<dl class="terms">(.*?)</dl>', re.S)
PAIR = re.compile(r"<dt>(.*?)</dt><dd>(.*?)</dd>", re.S)
# The report gathers these under Scope and terms. On the site each has the page of its subject.
SCOPE = (f'<p>The other scope sections have pages of their own. <a href="{links.url("methodology/analysis", "limits")}">'
         f'Limits</a> is on Analysis and validity. <a href="{links.url("experimental-design", "study-stage")}">Study '
         f'stage</a> and <a href="{links.url("experimental-design", "course-context")}">Course context</a> are on '
         "Experimental design.</p>")
# One site sentence above the report text, as the page title alone does not say what its tables hold.
LEADS = {
    "data/contrasts": "<p>The planned contrasts, the consistency table and every replicate build of runs rep-1 and rep-2.</p>",
    "data/methods": (f'<p>One row per method of run full-1. Each column heading links to its definition, and '
                     f'<a href="{links.url(MEASURES, "columns")}">Columns</a> on the measures page lists all 32 '
                     "columns.</p>"),
    "data/ratings": ("<p>How far a second lister agreed on the test list of run tcp-1-list, and how far the three blind "
                     "raters agreed in runs full-1, rep-1 and rep-2.</p>"),
    "data/runs": ("<p>The run records of full-1, rep-1 and rep-2: their settings, cap hits, failed collection steps and "
                  "unattributed agents.</p>"),
}


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


def frame(id, html, entry=lambda block: block):
    """The page html of one section's blocks, with entry applied to each entry. A table's region is labelled by its
    headings, numbered when they hold several, as a wide report table comes in column slices."""
    chain, tables, out = [], [], []
    for k, block in split(id, html):
        if k == "heading":
            level, hid, text = TITLE.fullmatch(block).groups()
            chain = [c for c in chain if c[0] < level] + [(level, plain(text, ""))]
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


def section(page, snap, idx, id, extra=lambda: "", entry=lambda block: block):
    """One report section with its links pointed at the study pages, as a labelled page section ending in extra(),
    which runs after every entry has passed through entry."""
    html = links.rewrite(cut(snap.files[snapshot.REPORT], id), snapshot.REPORT, page.slug, idx)
    inner = frame(id, html, entry)
    return f'<section aria-labelledby="{id}">{inner}{extra()}</section>'


def lead(page):
    """The five data pages, each with its blurb."""
    current = ' aria-current="page"'
    items = "".join(f'<li><a href="{links.url(s)}"{current * (s == page.slug)}>{escape(pagemap.BY_SLUG[s].nav)}</a>. '
                    f"{escape(pagemap.BY_SLUG[s].blurb)}</li>" for s in DATA)
    return f"<p>The supporting data takes five pages.</p><ul>{items}</ul>"


def measured_link(name):
    href = links.url(MEASURES, measures.slug(MEASURED[name]))
    return f'<p class="sub">Its formula and inputs are on <a href="{href}">Measures</a>.</p>'


def column_links(html):
    """Each column heading linked to its card on measures. ValueError names a heading no family card holds."""
    known = {n for _, _, names in measures.FAMILIES + (measures.TEST_ORDER,) for n in names}

    def head(m):
        if (name := plain(m[2], "")) not in known:
            raise ValueError(f"data/methods column {name!r} has no card on {MEASURES}")
        return f'<th{m[1]}><a href="{links.url(MEASURES, measures.slug(name))}">{m[2]}</a></th>'
    return re.sub(r'<th([^>]*scope="col"[^>]*)>(.*?)</th>', head, html)


def term_id(name):
    return "term-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def short_forms(showcase, names):
    """The showcase term list, which every view holds alike, with each term linked to the glossary row in SHORT_FORMS.
    The dt and dd stay as the showcase has them, as a link in a second dd would break the dl.terms grid."""
    lists = {v: TERMS.findall(snapshot.view(showcase, v)) for v in VIEWS}
    for v, found in lists.items():
        if len(found) != 1:
            raise ValueError(f"showcase view {v} holds {len(found)} term lists, not 1")
        if found != lists[VIEWS[0]]:
            raise ValueError(f"showcase view {v} has terms that differ from view {VIEWS[0]}")
    terms, rows = lists[VIEWS[0]][0], []
    pairs = PAIR.findall(terms)
    if "".join(f"<dt>{t}</dt><dd>{d}</dd>" for t, d in pairs) != terms:
        raise ValueError(f"the showcase term list holds more than dt and dd pairs: {terms[:60]!r}")
    for dt, dd in pairs:
        if (term := plain(dt, "")) not in SHORT_FORMS:
            raise ValueError(f"showcase term {term!r} has no glossary row in SHORT_FORMS")
        if (row := SHORT_FORMS[term]) not in names:
            raise ValueError(f"glossary row {row!r}, the full entry of showcase term {term!r}, is missing")
        rows.append(f'<dt><a href="#{term_id(row)}">{dt}</a></dt><dd>{dd}</dd>')
    return (f'<h3 id="showcase-terms">Short forms</h3><p>The summary and design pages use these short forms. Each term '
            f'links to its full entry above.</p><dl class="terms">{"".join(rows)}</dl>')


def glossary(page, snap, idx):
    """The glossary rows, each with an id and the measured ones with a link to measures, then the short forms."""
    names = []

    def entry(block):
        m = ROW.match(block)
        if not m:
            raise ValueError(f"section glossary holds a row of no known form {block[:60]!r}")
        names.append(name := plain(m.group(1), ""))
        inner = block[len('<div class="entry">'):-len("</div>")]
        if name in MEASURED:
            # The link closes the row's card, so it reads as the row's; a div keeps the row's text whole for coverage.
            inner = f"<div>{inner}</div>{measured_link(name)}"
        return f'<div class="entry" id="{term_id(name)}">{inner}</div>'

    def after():
        if missing := [n for n in MEASURED if n not in names]:
            raise ValueError(f"glossary rows {', '.join(missing)} are missing; each links to measures")
        return short_forms(snap.files[snapshot.SHOWCASE], names)

    return section(page, snap, idx, "glossary", after, entry)


def body(page, snap, idx):
    if page.slug == "glossary":
        return [section(page, snap, idx, "scope-and-terms", lambda: SCOPE), glossary(page, snap, idx)]
    extras = {"supporting-data": lambda: lead(page)}
    out = [LEADS[page.slug]] if page.slug in LEADS else []
    sections = [section(page, snap, idx, a, extras.get(a, lambda: "")) for a in page.anchors]
    return out + (list(map(column_links, sections)) if page.slug == "data/methods" else sections)
