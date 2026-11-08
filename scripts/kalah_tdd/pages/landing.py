"""The landing page (#62): the showcase summary with one Awards section, the report Headline under it and a contents
list of every page."""

import re
from html import escape, unescape

from .. import pagemap, parts
from ..links import rewrite, unique_ids, url
from ..snapshot import ID, REPORT, SHOWCASE, named_runs, run_doc, section, view

TAG = re.compile(r"Tag: (recomputed|verified|unchecked)\.")
CAPTIONED = re.compile(r'<figure id="[^"]+">.*?</figure>', re.S)
READ_ON = ("experimental-design", "methodology", "results/survey")
AWARD_RULES = {
    "Best overall": ("Lowest plain sum of each method's ranks on M, E and alignment, ties sharing their average rank. Cheapest and consistency never count.",
                     "Lowest sum of ranks on M, E and alignment. Ties use average ranks. Badges do not contribute."),
    "Most cost effective": ("Lowest M, the cost to completion times 1 minus APFDc-H, among methods with a functional mark of 15/15. M_io leaves output tokens out.",
                            "Lowest M among builds scoring 15/15. M_io recomputes the curve without output-token costs."),
    "Fewest errors": ("Lowest E, the distinct PMD findings plus adjusted surviving mutants, hidden failures and unseen failures.",
                      "Lowest additive count of PMD findings, adjusted surviving mutants and hidden and unseen failures."),
    "Best CQP/PMD alignment": ("The blind CQP rating agrees with PMD on every principle and PMD reports no issue.",
                               "CQP agrees with PMD on all eight principles and PMD reports no issue."),
    "Cheapest": ("Lowest cost to completion. A bronze badge that never counts toward best overall.",
                 "Lowest cost to completion. A bronze badge that does not contribute to best overall."),
    "Most consistent design": (
        "Lowest consistency score C. A bronze badge that never counts toward best overall. Exploratory. C covers only the 7 replicated methods of runs rep-1 and rep-2, pooling every replicate, n per method Functions first, classes later 5, Noun-verb map 5, Anchor Engineering 5, Classic greedy TDD 10, Held-out TDD 5, Coarse-to-fine TDD 5, Most informative next test 5. The raw costs mix CLI builds 2.1.308 and 2.1.309. The drift test of Classic greedy TDD between rep-1 and rep-2 gives M p 0.310. The test of its variance across methods gives p 0.464, so no method is shown to be more consistent than another.",
        "Lowest observed C among seven replicated designs. Exploratory. The global spread test did not detect a difference (p 0.464)."),
}


def award_places(card, title):
    entries = re.findall(r"<li\b[^>]*>.*?</li>", card, re.S)
    medals = [re.search(r'data-(?:medal|k)="(gold|silver|bronze)"', e).group(1) for e in entries]
    badge = title in ("Cheapest", "Most consistent design")
    if badge and any(medal != "bronze" for medal in medals):
        raise ValueError(f"{title}: badge medal needs review")
    def place(m):
        attrs, body = m.groups()
        medal = re.search(r'data-(?:medal|k)="(gold|silver|bronze)"', m.group()).group(1)
        label = "Bronze badge" if badge else "Joint third · Bronze" if medal == "bronze" and medals.count(medal) > 1 else medal.title()
        body, n = re.subn(r">(Gold|Silver|Bronze)</span>", f">{label}</span>", body, count=1)
        if n != 1 or "value=" in attrs:
            raise ValueError(f"{title}: award place markup needs review")
        rank = "" if badge else f' value="{("gold", "silver", "bronze").index(medal) + 1}"'
        return f"<li{attrs}{rank}>{body}</li>"
    card = re.sub(r"<li\b([^>]*)>(.*?)</li>", place, card, flags=re.S)
    return card.replace("<ol>", "<ul>").replace("</ol>", "</ul>") if badge else card


def award_cards(html):
    def card(m):
        block = m.group()
        title = re.search(r"<(h3|b)>(.*?)</\1>", block).group(2)
        old, new = AWARD_RULES[title]
        para = re.search(r"<p\b[^>]*>(.*?)</p>", block, re.S)
        if unescape(para.group(1)) != old:
            raise ValueError(f"{title}: award description needs review")
        detail = (f' <a href="{url("results/consistency", "rep-consistency")}">Scope and limits</a>.' if title == "Most consistent design" else
                  f' <a href="{url("methodology/analysis", "limits")}">Agreement limits</a>.' if title == "Best CQP/PMD alignment" else "")
        block = block[:para.start(1)] + escape(new) + detail + block[para.end(1):]
        return award_places(block, title)
    return re.sub(r'<(article|div) class="award">.*?</\1>', card, html, flags=re.S)


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


class ShowcaseParts:
    """The showcase summary cut at its h2 headings. Its eyebrow, h1 and lede repeat the page header, so they go."""

    def __init__(self, html):
        start = html.index('<div class="winner">')
        self.winner = html[start:html.index("<h2>", start)]
        self.parts = dict(re.findall(r"<h2>(.*?)</h2>(.*?)(?=<h2>|$)", html[start:], re.S))

    def awards(self, report):
        """One Awards section: the report scoring rule, the showcase cards, then the report places in a fold."""
        rule, places = re.search(r'<h3 id="awards">Awards</h3>\s*(<p>.*?</p>)\s*(.*)', report, re.S).groups()
        old = "Each award ranks the survey methods of one run, lower first, and ties share a place."
        if rule.count(old) != 1:
            raise ValueError("award population statement needs review")
        rule = rule.replace(old, "The first five awards rank the 11 full-1 survey builds, lower first, with ties sharing a place. "
                            "The consistency badge covers seven replicated designs in rep-1 and rep-2. The full-1 survey ended 2026-10-16.")
        return (f'<h2 id="awards">Awards</h2>\n{rule}\n{award_cards(self.parts.pop("Awards"))}\n'
                f"<details><summary>Award places as the report states them</summary>\n{award_cards(places)}\n</details>")

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
