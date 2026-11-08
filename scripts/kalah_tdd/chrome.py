"""Page chrome shared by every study page: document shell, header, pagers and the contents sidebar."""

import re
from html import escape

from . import pagemap
from .links import BASE, url
from .snapshot import ID_ATTR, named_runs


def part_id(part):
    return "part-" + re.sub(r"[^a-z0-9]+", "-", part.lower()).strip("-")


# Ids the chrome itself uses, which page bodies must not take.
IDS = ("main", "toc", *map(part_id, pagemap.PARTS))
# Mono 600 is for the .medal labels.
FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600"
         "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")
# Copied verbatim from the other standalone pages; scripts/check_site.sh checks its links.
SITE_BAR = """<nav class="site-bar" aria-label="Site">
  <a href="/">Home</a>
  <a href="/about">About</a>
  <a href="/cv">Resume</a>
  <a href="/projects" aria-current="page">Projects</a>
  <a class="ext" href="https://www.linkedin.com/in/jack-fraser-3a137ba3/">LinkedIn</a>
  <a href="https://github.com/quintuplin">GitHub</a>
</nav>
<style>
/* Static link bar back to the main site, styled like its nav. */
.site-bar { flex: none; display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 22px; padding-bottom: 8px; margin-bottom: 8px;
  border-bottom: 1px solid var(--rule, var(--border, var(--line))); font: 600 16px/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
.site-bar a { padding-block: 2px; color: var(--muted); text-decoration: none; }
.site-bar a:hover, .site-bar a:focus-visible { color: var(--text, var(--ink)); text-decoration: underline; }
.site-bar a[aria-current] { color: var(--accent, var(--focus)); }
.site-bar .ext { margin-left: auto; }
@media (max-width: 600px) { .site-bar .ext { margin-left: 0; } }
</style>"""
# The render.py opener: the closed contents disclosure opens on wide screens, and a followed link opens its folds.
# It centres the current page in the rail by scrolling the rail alone, as scrollIntoView would also move the page.
OPENER = ('<script>(() => { const contents = document.getElementById("toc"), wide = matchMedia("(min-width: 900px)"); '
          'const sync = () => { contents.open = wide.matches; }; sync(); wide.addEventListener("change", sync); '
          'const current = contents.querySelector("[aria-current]"); if (current) contents.scrollTop += '
          'current.getBoundingClientRect().top - contents.getBoundingClientRect().top - contents.clientHeight / 2 + current.offsetHeight / 2; '
          'const reveal = (hash) => { for (let node = hash && document.getElementById(decodeURIComponent(hash.slice(1))); '
          'node; node = node.parentElement) if (node.tagName === "DETAILS") node.open = true; }; '
          'const load = () => reveal(location.hash); if (document.readyState === "loading") '
          'addEventListener("DOMContentLoaded", load); else load(); addEventListener("hashchange", load); '
          'document.addEventListener("click", (event) => { const link = event.target.closest(\'a[href^="#"]\'); '
          'if (link) reveal(link.hash); }); '
          'const widths = new WeakMap(), fit = (region) => { const width = region.clientWidth; '
          'if (widths.get(region) === width) return; widths.set(region, width); '
          'const svg = region.querySelector("svg.flow"), readable = [...svg.querySelectorAll("text")]'
          '.every(t => parseFloat(getComputedStyle(t).fontSize) >= 12); '
          'region.dataset.flow = svg.viewBox.baseVal.width <= width && readable ? "svg" : "compact"; }; '
          'const observer = new ResizeObserver(entries => entries.forEach(e => fit(e.target))); '
          'document.querySelectorAll(".diagram[data-flow]").forEach(region => { fit(region); observer.observe(region); }); '
          '})();</script>')
SUBHEAD = re.compile(r'<h([23])\b[^>]*' + ID_ATTR + r'([^"]+)"[^>]*>(.*?)</h\1>', re.S)


def shell(page, snap, body, stub):
    """The whole document for one page around its main body."""
    stub_meta = '<meta name="kalah-tdd-stub">\n' if stub else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="generator" content="scripts/build_kalah_tdd_study.py from Quintuplin/tdd-experiment {snap.sha}">
{stub_meta}<title>{escape(page.title)} · Kalah TDD study</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{BASE}study.css">
</head>
<body>
<div class="backdrop" aria-hidden="true"></div>
<div class="sheet">
<a class="skip" href="#main">Skip to content</a>
{SITE_BAR}
<div class="study">
{header(page, snap, body)}
{pager(page, "top")}
{sidebar(page, body)}
<main id="main">
{body}
</main>
{pager(page, "bottom")}
</div>
</div>
{OPENER}
</body>
</html>
"""


def header(page, snap, body):
    n = pagemap.number(page.slug)
    # The runs the body names, or the snapshot's own run where it names none.
    runs = named_runs(snap, body) or [snap.run]
    said = runs[0] if len(runs) == 1 else f"{', '.join(runs[:-1])} and {runs[-1]}"
    return f"""<header class="study-head">
<p class="eyebrow">Kalah TDD study · Part {n} of {len(pagemap.PAGES)} · {page.part}</p>
<h1>{escape(page.title)}</h1>
<p class="lede">{escape(page.blurb)}</p>
<p class="prov">Source run{"s" * (len(runs) > 1)} {said} at tdd-experiment <code>{snap.sha[:7]}</code></p>
</header>"""


def pager(page, where):
    prev, nxt = pagemap.neighbours(page.slug)
    card = lambda rel, label, p: (f'<a rel="{rel}" href="{url(p.slug)}"><span>{label}</span> <b>{escape(p.title)}</b></a>\n'
                                  if p else "")
    return (f'<nav class="pager" aria-label="Previous and next page, {where}">\n{card("prev", "Previous", prev)}'
            f'<a class="pager-home" href="{url("", "contents")}"><span>Study</span> <b>Contents</b></a>\n'
            f'{card("next", "Next", nxt)}</nav>')


def sidebar(page, body):
    """Every page by part, with the current page marked and its h2 and h3 headings nested under it."""
    parts = []
    for part in pagemap.PARTS:
        items = "".join(item(p, page, body) for p in pagemap.PAGES if p.part == part)
        # The label names each list, so a screen reader announces the part on entering it.
        parts.append(f'<p class="part" id="{part_id(part)}">{part}</p>\n<ol aria-labelledby="{part_id(part)}">\n{items}</ol>\n')
    return (f'<details class="toc" id="toc"><summary>Contents</summary>\n<nav aria-label="Study contents">\n'
            f'{"".join(parts)}</nav>\n</details>')


def item(p, page, body):
    if p != page:
        return f'<li><a href="{url(p.slug)}">{escape(p.nav)}</a></li>\n'
    return f'<li><a href="{url(p.slug)}" aria-current="page">{escape(p.nav)}</a>{headings(p, body)}</li>\n'


def headings(page, body):
    """Nested list of the body's h2 headings, each with its h3 headings."""
    tree = []
    for level, id, text in SUBHEAD.findall(body):
        link = f'<a href="{url(page.slug, id)}">{re.sub(r"<[^>]+>", "", text).strip()}</a>'
        if level == "2" or not tree:
            tree.append([link, []])
        else:
            tree[-1][1].append(f"<li>{link}</li>")
    inner = lambda subs: f"<ol>{''.join(subs)}</ol>" if subs else ""
    return f"<ol>{''.join(f'<li>{link}{inner(subs)}</li>' for link, subs in tree)}</ol>" if tree else ""
