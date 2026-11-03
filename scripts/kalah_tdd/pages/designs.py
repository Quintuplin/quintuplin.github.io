"""The 12 design pages (#87): the showcase view and the method page merged into one page in paper order, which is
how it builds code, results, verdict, then the method page evidence. A merge keeps the superset of both sources and
refuses to drop text."""

import re
from html import unescape

from .. import links, pagemap, parts
from ..figures import class_diagram
from ..snapshot import REPORT, SHOWCASE, section, view

A02 = "designs/a02-reference"

VIEW = re.compile(r'<nav class="bar"><a href="#summary">All designs</a></nav>(?P<chip><p><span class="chip">[^<]*</span></p>)'
                  r'<h1>(?P<name>[^<]*)</h1><p class="lede">(?P<lede>[^<]*)</p>(?P<lead>.*?)'
                  r'<section id="steps"><h2>How it builds code</h2>(?P<intro><p class="muted">[^<]*</p>)'
                  r'(?P<steps><pre class="steps">.*?</pre>)</section>(?P<kpis>(?:<section id="(?:survey|replicates)">.*?</section>)*)'
                  r'<h2>Verdict</h2><p>(?P<verdict>[^<]*)</p><h2>Terms</h2><dl class="terms">.*</dl>', re.S)
HEAD = re.compile(r'<h1 id="[^"]+">[^<]*</h1>\s*<p><a href="\.\./report\.html">Back to the study page</a></p>\s*(<p>[^<]*</p>)')
HOW = re.compile(r'<h2 id="how-it-works">How it works</h2>\s*<p>(?P<family>[^<]*)</p>\s*(?P<code><pre><code>.*?</code></pre>)\s*'
                 r'(?P<kinds><p>[^<]*</p>)', re.S)
CONCLUSION = re.compile(r'<h2 id="conclusion">Conclusion</h2>\s*<p>([^<]*)</p>')
# Column definitions live once on measures and the glossary, so the fold is dropped for a pointer.
COLUMNS = re.compile(r'<h2 id="columns">Columns</h2>\s*<details><summary>Column definitions[^<]*</summary>.*</details>', re.S)
# Method page sections kept in source order, after the merged ones.
EVIDENCE = ("score-card", "builds", "related-methods", "records")
SPAN = re.compile(r'<span class="(hd|st)">(.*?)</span>', re.S)
# A method pre line: a stage header, a numbered step or a step borrowed with "with", which the showcase shows as "also:".
LINE = re.compile(r'(?P<hd>\S.*:)|  (?:(?P<n>\d+)\. |(?P<with>with ))&quot;(?P<st>.*)&quot;')
TAG = re.compile(r"Tag: (recomputed|verified|unchecked)\.(?=</p>)")
# A report design section: the card line, its class diagram, an optional key-value table and the method page link.
CARD = re.compile(r'<h3 id="(?P<id>[^"]+)">(?P<name>[^<]*)</h3>\s*<p>(?P<card>[^<]*)</p>\s*(?P<figure><figure class="diagram">.*?</figure>)'
                  r'\s*(?P<kv><div class="shaped"><table class="kv">.*?</table></div>)?\s*'
                  r'(?P<link><p><a class="record-link" href="methods/[^"]+\.html">Method page</a></p>)?', re.S)
REFERENCE = re.compile(r'<h3 id="reference">Reference</h3>\s*(?P<rest><p>[^<]*</p>\s*<details><summary>Reference</summary>.*</details>)', re.S)
LABEL = re.compile(r"<(h[1-6]|summary)\b[^>]*>(.*?)</\1>|<table\b.*?</table>", re.S)


def body(page, snap, idx):
    fragments, report = (reference(page, snap, idx), None) if page.slug == A02 else design(page, snap, idx)
    fragments = class_diagram.frame_all(wrap_tables(fragments), page.slug, report)
    return [TAG.sub(lambda m: f"Tag: {parts.tag(m.group(1))}.", f) for f in fragments]


def design(page, snap, idx):
    slug, here = page.slug.removeprefix("designs/"), page.slug
    doc = f"{links.METHODS}{slug}.html"
    shown = showcase(page, view(snap.files[SHOWCASE], slug))
    head, sections = method_sections(slug, snap.files[doc])
    how, end = HOW.fullmatch(sections["how-it-works"]), CONCLUSION.fullmatch(sections["conclusion"])
    intro = HEAD.fullmatch(head)
    if not (how and end and intro and COLUMNS.fullmatch(sections["columns"])):
        raise ValueError(f"{slug}: the method page has an unexpected shape")
    heading = next(d[1] for d in pagemap.DESIGNS if d[0] == slug)
    card = report_card(slug, section(snap.files[REPORT], heading), require_link=True)
    if unescape(card["name"]) != page.title:
        raise ValueError(f"{slug}: the report card name {card['name']!r} differs from the page map")
    # Each part is rewritten against its own source before a union, so a kept link points where its source meant.
    lead = links.rewrite(shown["chip"] + shown["lead"], SHOWCASE, here, idx) + "\n" + links.rewrite(intro.group(1), doc, here, idx)
    family = union(slug, links.rewrite(card["card"], REPORT, here, idx), links.rewrite(how["family"], doc, here, idx))
    steps = (f'<section id="steps"><h2 id="how-it-works">How it builds code</h2>\n{shown["intro"]}\n<p>{family}</p>\n'
             f'{merge_steps(slug, shown["steps"], how["code"])}\n{how["kinds"]}</section>')
    verdict = f'<h2 id="conclusion">Verdict</h2>\n<p>{union(slug, shown["verdict"], end.group(1))}</p>'
    summary = links.rewrite(f'<h2 id="{card["id"]}">Report summary</h2>\n{card["figure"]}\n{card["kv"] or ""}', REPORT, here, idx)
    fragments = [lead, steps, links.rewrite(shown["kpis"], SHOWCASE, here, idx), verdict, summary,
                 *(links.rewrite(sections[s], doc, here, idx) for s in EVIDENCE), pointer()]
    return fragments, fragments.index(summary)


def report_card(slug, html, require_link):
    """The report's design section. Its method page link is dropped, as this page holds the method page."""
    m = CARD.fullmatch(html.strip())
    if not m or bool(m["link"]) != require_link:
        raise ValueError(f"{slug}: the report design section has an unexpected shape")
    return m


def reference(page, snap, idx):
    """The A02 reference page: the report's A02 card and its Reference section, each under its own h2."""
    card_id, ref_id = page.anchors
    report = snap.files[REPORT]
    card = report_card("a02-reference", section(report, card_id), require_link=False)
    ref = REFERENCE.fullmatch(section(report, ref_id).strip())
    if not ref:
        raise ValueError("a02-reference: the report Reference section has an unexpected shape")
    return [links.rewrite(f'<h2 id="{card["id"]}">{card["name"]}</h2>\n<p>{card["card"]}</p>\n{card["figure"]}\n{card["kv"]}',
                          REPORT, page.slug, idx),
            links.rewrite(f'<h2 id="{ref_id}">Reference</h2>\n{ref["rest"]}', REPORT, page.slug, idx)]


def wrap_tables(fragments):
    """Each table in a named scroll region, labelled by the latest heading or summary before it. A label used twice
    on the page names the nearest enclosing heading that tells the tables apart, or else counts them."""
    found, label, enclosing = [], "", []
    for m in (m for fragment in fragments for m in LABEL.finditer(fragment)):
        if m.group(1):
            label = " ".join(unescape(re.sub(r"<[^>]+>", "", m.group(2))).split())
            if m.group(1) != "summary":
                level = int(m.group(1)[1])
                enclosing = [h for h in enclosing if h[0] < level] + [(level, label)]
        elif m.group(0).count("<table") > 1:
            raise ValueError(f"a nested table under {label!r} cannot be wrapped")
        else:
            found.append((label, [h for _, h in reversed(enclosing)]))
    labels = [base for base, _ in found]
    for base in {b for b in labels if labels.count(b) > 1}:
        qualify(labels, found, [k for k, (b, _) in enumerate(found) if b == base], 0)
    names = iter(labels)
    return [LABEL.sub(lambda m: m.group(0) if m.group(1) else parts.table(m.group(0), next(names)), f) for f in fragments]


def qualify(labels, found, same, depth):
    """Suffix labels[k] for k in same with the depth-th enclosing heading where those differ, else "table i of n"."""
    keys = [found[k][1][depth] if depth < len(found[k][1]) else None for k in same]
    if len(same) == 1:
        return
    if not any(keys):
        for i, k in enumerate(same, 1):
            labels[k] += f", table {i} of {len(same)}"
    elif len(set(keys)) == 1:
        qualify(labels, found, same, depth + 1)
    else:
        for key in dict.fromkeys(keys):
            group = [k for k, kk in zip(same, keys) if kk == key]
            for k in group:
                labels[k] += f", {key}" if key else ""
            qualify(labels, found, group, depth + 1)


def showcase(page, html):
    """The showcase view's parts. Its h1, lede and back link repeat the chrome header and pager, so they are dropped
    only when they match the page map."""
    m = VIEW.fullmatch(html)
    if not m:
        raise ValueError(f"{page.slug}: the showcase view has an unexpected shape")
    if (unescape(m["name"]), unescape(m["lede"])) != (page.title, page.blurb):
        raise ValueError(f"{page.slug}: showcase header {m['name']!r}, {m['lede']!r} differs from the page map")
    return m


def method_sections(slug, html):
    """(the text before the first h2, {h2 id: section}) of the method page main."""
    main = re.search(r"<main\b[^>]*>(.*?)</main>", html, re.S).group(1).strip()
    cuts = [m.start() for m in re.finditer(r'<h2 id="', main)]
    sections = {re.match(r'<h2 id="([^"]+)"', main[a:]).group(1): main[a:b].strip() for a, b in zip(cuts, cuts[1:] + [len(main)])}
    if set(sections) != {"how-it-works", "conclusion", "columns", *EVIDENCE}:
        raise ValueError(f"{slug}: method page sections {sorted(sections)}")
    return main[:cuts[0]].strip(), sections


def norm(text):
    return " ".join(unescape(text).split())


def merge_steps(slug, pre, code):
    """The showcase pre.steps with the method page's step numbers. Refused when a line differs in kind or text."""
    inner = pre.removeprefix('<pre class="steps">').removesuffix("</pre>")
    shown = SPAN.findall(inner)
    if "".join(f'<span class="{k}">{t}</span>' for k, t in shown) != inner:
        raise ValueError(f"{slug}: the showcase steps hold text outside a step line")
    lines = code.removeprefix("<pre><code>").removesuffix("</code></pre>").split("\n")
    out = []
    for k, ((kind, text), line) in enumerate(zip(shown, lines), 1):
        m = LINE.fullmatch(line)
        if not m:
            raise ValueError(f"{slug}: method step line {line!r} has no known form")
        want = m["hd"] or ("also: " if m["with"] else "") + m["st"]
        if kind != ("hd" if m["hd"] else "st") or norm(text) != norm(want):
            raise ValueError(f"{slug}: showcase step line {k} {norm(text)!r} does not match method line {norm(line)!r}")
        out.append(f'<span class="{kind}">{m["n"] + ". " if m["n"] else ""}{text}</span>')
    if len(shown) != len(lines):
        extra = (shown[len(lines):] or [("", line) for line in lines[len(shown):]])[0][1]
        raise ValueError(f"{slug}: step line {norm(extra)!r} is in only one of the showcase and the method page")
    return f'<pre class="steps">{"".join(out)}</pre>'


def union(slug, a, b):
    """Whichever of a and b holds the other, whitespace aside. Refused when neither does, as a merge would lose text."""
    if norm(a) in norm(b):
        return b
    if norm(b) in norm(a):
        return a
    raise ValueError(f"{slug}: neither text holds the other: {norm(a)[:60]!r} and {norm(b)[:60]!r}")


def pointer():
    """Terms and column definitions are defined once for the study, so this page links them."""
    to = lambda slug: f'<a href="{links.url(slug)}">{pagemap.BY_SLUG[slug].title}</a>'
    return (f'<h2 id="columns">Terms and columns</h2>\n<p>See {to("methodology/measures")} and the {to("glossary")} '
            "for the terms and table columns this page uses.</p>")
