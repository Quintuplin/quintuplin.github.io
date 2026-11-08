"""Page parts shared by the study page groups (#79): table scroll regions, claim tags, part figure numbers and figure frames."""

import itertools
import re
from html import escape, unescape

from . import pagemap
from .figures import flow

KINDS = ("recomputed", "verified", "unchecked")
# A captioned report figure: figcaption with its h3 first, then the plot, the legend and the table view.
SOURCE = re.compile(r'<figure id="([^"]+)"><figcaption>(<h3>(.*?)</h3>.*?</figcaption>)(<div class="plot">.*?</div>)'
                    r'(<div class="legend">.*?</div>)<details>(.*?)</details></figure>', re.S)


def numbers(slug):
    """Figure numbers "P.1", "P.2", ... where P is the page's part number."""
    return (f"{pagemap.number(slug)}.{k}" for k in itertools.count(1))


def table(html, label):
    """A table in a named, keyboard-scrollable region, so a wide table scrolls inside the column."""
    def cell(m):
        attrs, content = m.groups()
        value = unescape(re.sub(r"<[^>]+>", "", content)).strip()
        if re.fullmatch(r"[-+−]?\d[\d.,%/()[\] ±–−+eE-]*", value):
            attrs = re.sub(r'class="([^"]*)"', r'class="\1 number"', attrs) if 'class="' in attrs else attrs + ' class="number"'
        return f"<td{attrs}>{content}</td>"
    scope = lambda text, kind: re.sub(r'<th(?![^>]*\bscope=)(?=[\s>])', f'<th scope="{kind}"', text)
    html = re.sub(r"<thead\b.*?</thead>", lambda m: scope(m.group(), "col"), html, flags=re.S)
    html = re.sub(r"<td\b([^>]*)>(.*?)</td>", cell, scope(html, "row"), flags=re.S)
    return f'<div class="table-scroll" role="region" tabindex="0" aria-label="{escape(label)}">{html}</div>'


def tag(kind):
    """The claim tag of a finding, which names how it was checked."""
    if kind not in KINDS:
        raise ValueError(f"claim tag {kind!r} is not one of {', '.join(KINDS)}")
    return f'<span class="tag">{kind}</span>'


def foot(n, href):
    return f'<a href="{escape(href)}" aria-label="Data for Figure {n}">Data</a>'


def figure(n, id, title, svg, caption, data_href, text, level=3):
    """A study figure: number, title, the svg in a scroll region, then a caption, a Data link and a text version.
    caption and svg are HTML. text is flow.text_version HTML or a sequence of plain strings, one list item each.
    The title has no id, as chrome.headings would put it in the sidebar. data_href None links the text version,
    as in source_figure. level is the title heading, one below the enclosing heading; study.css styles h3 to h6."""
    if level not in range(3, 7):
        raise ValueError(f"figure title level {level!r} is not 3 to 6")
    if not isinstance(text, str):
        text = flow.details(title, "".join(f"<li>{escape(t)}</li>" for t in text))
    if not text.startswith("<details>"):
        raise ValueError(f"text is not a text version disclosure: {text[:60]!r}")
    text = f'<details id="{escape(id)}-data">' + text.removeprefix("<details>")
    data_href = data_href or f"#{id}-data"
    return (f'<figure id="{escape(id)}" aria-label="Figure {n}: {escape(title)}"><p class="fig-n">Figure {n}</p>'
            f'<h{level}>{escape(title)}</h{level}><div class="diagram" role="region" tabindex="0" aria-label="Figure {n} diagram">{svg}</div>'
            f'<figcaption><p>{caption}</p><div class="fig-foot">{foot(n, data_href)}</div>{text}</figcaption></figure>')


def source_figure(n, fig_html):
    """A captioned report figure numbered n, its legend in a foot beside a Data link to its table view.
    Every svg and table view stays as in the report."""
    m = SOURCE.fullmatch(fig_html.strip())
    if not m or fig_html.count("<figure") != 1 or fig_html.count("<details") != 1:
        raise ValueError(f"not a captioned report figure: {fig_html[:60]!r}")
    id, caption, title, plot, legend, details = m.groups()
    label = escape(unescape(re.sub(r"<[^>]+>", "", title)).strip())
    details = re.sub(r"<table\b.*?</table>", lambda m: table(m.group(), unescape(label)), details, flags=re.S)
    return (f'<figure id="{id}" aria-label="Figure {n}: {label}"><figcaption><p class="fig-n">Figure {n}</p>{caption}'
            f'{plot}<div class="fig-foot">{legend}{foot(n, "#" + id + "-data")}</div>'
            f'<details id="{id}-data">{details}</details></figure>')
