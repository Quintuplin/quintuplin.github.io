"""The landing page (#62): the showcase summary with one Awards section, the report Headline under it and a contents
list of every page."""

import re
from html import escape, unescape

from .. import pagemap, parts
from ..links import rewrite, unique_ids, url
from ..snapshot import ID, REPORT, SHOWCASE, run_doc, section, view

TAG = re.compile(r"Tag: (recomputed|verified|unchecked)\.")
CAPTIONED = re.compile(r'<figure id="[^"]+">.*?</figure>', re.S)
READ_ON = ("experimental-design", "methodology", "results/survey")


def body(page, snap, idx):
    report, showcase = snap.files[REPORT], view(snap.files[SHOWCASE], "summary")
    on = lambda html, doc: rewrite(html, doc, page.slug, idx)
    cut = lambda html, start, stop: html[html.index(start):html.index(stop, html.index(start))]
    summary = ShowcaseParts(on(showcase, SHOWCASE))
    head = section(report, "kalah-tdd-experiment")
    awards = section(report, "awards")
    known = [
        summary.awards(on(awards, REPORT)),
        summary.designs(on(cut(section(report, "methods"), "<h2", '<h3 id="classic-greedy-tdd"'), REPORT)),
        headline(page, on(cut(head, '<h2 id="headline"', '<h3 id="awards"'), REPORT)),
        summary.about_data(),
        summary.terms(),
    ]
    extra, last = summary.rest(), contents(page)
    first = intro(snap, on(cut(head, "<p>", '<h2 id="headline"'), REPORT), summary, [*known, extra, last])
    if extra:
        # Any id the page sets yields, so the #contents links keep their target.
        extra, = unique_ids([extra], reserved=ID.findall("".join([first, *known, last])))
    return [tags(f) for f in (first, *known, extra, last) if f]


def tags(html):
    """The report's "Tag: kind." sentences as claim tags."""
    return TAG.sub(lambda m: parts.tag(m.group(1)), html)


def intro(snap, paragraphs, summary, rest):
    """The study question and the showcase winner and KPIs, then the run paragraph that defines the claim tags and
    the doc version of every run the page names."""
    question, runs = re.findall(r"<p>.*?</p>", paragraphs, re.S)
    named = named_runs(snap, "".join([question, summary.winner, runs, *rest]))
    docs = ", ".join(f"{run} {run_doc(snap, run)}" for run in named)
    first, second, third = (f'<a href="{url(s)}">{escape(pagemap.BY_SLUG[s].title)}</a>' for s in READ_ON)
    read_on = f"{first}, {second} and {third}"
    return (f'<h2 id="kalah-tdd-experiment">The study</h2>\n{question}\n{summary.winner}\n{runs}\n'
            f"<p>The methods text on these pages is from methods doc {snap.doc}. The runs this page names were built "
            f"under these doc versions, by short sha256: {docs}.</p>\n"
            f'<p>Read on with {read_on}, or pick any of the <a href="#contents">{len(pagemap.PAGES)} parts</a>.</p>')


def named_runs(snap, html):
    """Each snapshot run the text of html names, in first-mention order. tcp-1 inside tcp-1-list2 is no mention."""
    keys = "|".join(map(re.escape, sorted(snap.facts["runs"], key=len, reverse=True)))
    found = re.findall(rf"(?<![\w/-])({keys})(?![\w/-])", re.sub(r"<[^>]+>", " ", html))
    return list(dict.fromkeys(found))


class ShowcaseParts:
    """The showcase summary cut at its h2 headings. Its eyebrow, h1 and lede repeat the page header, so they go."""

    def __init__(self, html):
        start = html.index('<div class="winner">')
        self.winner = html[start:html.index("<h2>", start)]
        self.parts = dict(re.findall(r"<h2>(.*?)</h2>(.*?)(?=<h2>|$)", html[start:], re.S))

    def awards(self, report):
        """One Awards section: the report scoring rule, the showcase cards, then the report places in a fold."""
        rule, places = re.search(r'<h3 id="awards">Awards</h3>\s*(<p>.*?</p>)\s*(.*)', report, re.S).groups()
        return (f'<h2 id="awards">Awards</h2>\n{rule}\n{self.parts.pop("Awards")}\n'
                f"<details><summary>Award places as the report states them</summary>\n{places}\n</details>")

    def designs(self, report):
        """The report methods intro over the showcase design cards, which link each design's page."""
        intro = report.split("</h2>", 1)[1].strip()
        return (f'<h2 id="methods">The designs</h2>\n{intro}\n<p>Here each card gives a design\'s headline scores. '
                f"Its page holds the full method card and class diagram.</p>\n{self.parts.pop('The designs')}")

    def about_data(self):
        """The showcase notes. Their full report link becomes the contents of these pages."""
        notes = self.parts.pop("About the data").replace(f'href="{url("")}"', 'href="#contents"')
        return f'<h2 id="about-the-data">About the data</h2>\n{notes}'

    def terms(self):
        return (f'<h2 id="terms">Terms</h2>\n{self.parts.pop("Terms")}\n'
                f'<p>The <a href="{url("glossary")}">glossary</a> defines every term the study pages use.</p>')

    def rest(self):
        """Any showcase section the calls above did not take, so none drops."""
        slug = lambda title: re.sub(r"[^a-z0-9]+", "-", unescape(re.sub(r"<[^>]+>", "", title)).lower()).strip("-")
        return "\n".join(f'<h2 id="{slug(title)}">{title}</h2>\n{html}' for title, html in self.parts.items())


def headline(page, html):
    """The report Headline with its two figures framed and numbered."""
    numbers = parts.numbers(page.slug)
    return CAPTIONED.sub(lambda m: parts.source_figure(next(numbers), m.group(0)), html)


def contents(page):
    """Every page by sidebar part, numbered as the header numbers it, with its blurb."""
    cards = []
    for part in pagemap.PARTS:
        pages = [p for p in pagemap.PAGES if p.part == part]
        items = "".join(f'<li><a href="{url(p.slug)}"{current(p, page)}>{escape(p.title)}</a> '
                        f'<span class="blurb">{escape(p.blurb)}</span></li>' for p in pages)
        cards.append(f'<div class="design"><h3>{part}</h3><ol start="{pagemap.number(pages[0].slug)}">{items}</ol></div>')
    return (f'<h2 id="contents">Contents</h2>\n<p>All {len(pagemap.PAGES)} parts in reading order, grouped as the '
            f'sidebar groups them. Part numbers match the header of each page.</p>\n<div class="grid contents">{"".join(cards)}</div>')


def current(p, page):
    return ' aria-current="page"' if p == page else ""
