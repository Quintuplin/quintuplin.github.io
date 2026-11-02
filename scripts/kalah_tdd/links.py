"""Old report and showcase links pointed at the study pages, and ids kept unique where fragments share a page."""

import itertools
import re

from . import pagemap
from .snapshot import REPORT, SHOWCASE

BASE = "/studies/kalah-tdd-study/"
METHODS = "runs/full-1/methods/"
# The showcase's link to the full report, which the study pages replace.
ARTIFACT = "https://claude.ai/artifact/5g7jbNAxSnZPjQ2nLEJ15a"
KEEP = ("/", "https://", "http://", "mailto:")
HREF = re.compile(r'href="([^"]*)"')
ID = re.compile(r'(?<![\w-])id="([^"]+)"')
OLD = re.compile(r"(?:(\.\./report|methods/[\w-]+|[\w-]+)\.html)?(?:#(.+))?")


def url(slug, frag=""):
    return BASE + (f"{slug}/" if slug else "") + (f"#{frag}" if frag else "")


def index(snap):
    """{source file: {id: (page slug, fragment)}} for every id in the snapshot pages."""
    homes = {a: p.slug for p in pagemap.PAGES for a in p.anchors}
    out = {REPORT: placed(snap.files[REPORT], "h[1-3]", lambda id: homes.get(id)),
           SHOWCASE: placed(snap.files[SHOWCASE], "main", lambda id: "" if id == "summary" else f"designs/{id}")}
    for slug, *_ in pagemap.DESIGNS:
        out[f"{METHODS}{slug}.html"] = {i: (f"designs/{slug}", i) for i in ID.findall(snap.files[f"{METHODS}{slug}.html"])}
    return out


def placed(html, opener, home):
    """Each id goes to the page of the opener element (report heading or showcase view) before it.
    A showcase view's own id names the whole page, so it carries no fragment."""
    out, here = {}, ""
    for m in re.finditer(rf'<({opener})?\b[^>]*(?<![\w-])id="([^"]+)"', html):
        id = m.group(2)
        if m.group(1):
            here = home(id)
            if here is None:
                raise ValueError(f"report heading {id} has no page in pagemap.PAGES")
        out.setdefault(id, (here, "" if m.group(1) == "main" else id))
    return out


def page_of(src):
    return f"designs/{src[len(METHODS):-len('.html')]}" if src.startswith(METHODS) else pagemap.PAGES[0].slug


def target(href, doc, here, idx):
    if href == ARTIFACT:
        return url("")
    if href.startswith(KEEP):
        return href
    m = OLD.fullmatch(href)
    name, frag = m.groups() if m and href else ("?", None)
    src = doc if name is None else REPORT if name == "../report" else f"{METHODS}{name.removeprefix('methods/')}.html"
    if src not in idx or (frag is not None and frag not in idx[src]):
        raise ValueError(f"{doc} links {href!r}, which no study page holds")
    slug, frag = idx[src][frag] if frag is not None else (page_of(src), "")
    return f"#{frag}" if slug == here and frag else url(slug, frag)


def rewrite(html, doc, here, idx):
    """html from snapshot file doc, placed on page here, with every old link pointed at its study page."""
    return HREF.sub(lambda m: f'href="{target(m.group(1), doc, here, idx)}"', html)


def unique_ids(fragments, reserved=()):
    """Fragments for one page, with an id already taken earlier suffixed -2, -3 and on, and local references kept."""
    every, taken, out = set(reserved).union(*(ID.findall(f) for f in fragments)), set(reserved), []
    for frag in fragments:
        renames = {}

        def fresh(m):
            new = m.group(1)
            if new in taken:
                new = next(n for i in itertools.count(2) if (n := f"{m.group(1)}-{i}") not in every | taken)
                renames[m.group(1)] = new
            taken.add(new)
            return f'id="{new}"'

        frag = ID.sub(fresh, frag)
        out.append(references(frag, renames) if renames else frag)
    return out


def references(frag, renames):
    one = lambda m: m.group(1) + renames.get(m.group(2), m.group(2)) + m.group(3)
    frag = re.sub(r'(href="#|url\(#)([^")]+)([")])', one, frag)
    many = lambda m: m.group(1) + " ".join(renames.get(t, t) for t in m.group(2).split()) + '"'
    return re.sub(r'(\baria-(?:labelledby|describedby)=")([^"]*)"', many, frag)
