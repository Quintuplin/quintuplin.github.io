#!/usr/bin/env python3
"""Check that the Kalah TDD study pages keep all the snapshot data (#61).
Inventory parses the snapshot sources on its own, without the generator's slicing, so a generator bug cannot hide.
Coverage finds each item on its mapped page as the whole text of an element. MetricDefs finds each results and data page label defined on measures.
Stub pages are skipped, and --final fails on any stub.

Usage: check_kalah_tdd_study.py [--final] [repo root]
"""
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

# python3 -I leaves the script folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_study_nav  # noqa: E402
from kalah_tdd import pagemap, snapshot  # noqa: E402

KINDS = ("figure", "row", "table", "tile", "term")
SHARED = "glossary or measures"
SHARED_PAGES = ("glossary", "methodology/measures")
MEASURES = "methodology/measures"
METHODS = "runs/full-1/methods/"
STUB = "kalah-tdd-stub"
BASE = "/studies/kalah-tdd-study/"
ANCHORS = {a: p.slug for p in pagemap.PAGES for a in p.anchors}
VIEWS = {"summary": "", **{d[0]: f"designs/{d[0]}" for d in pagemap.DESIGNS}}
ROWS = re.compile(r"\b(\d+) rows?\b")
UNIT = re.compile(r"(,[^,]*| /\s*\d+)$")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Node:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs), [], parent

    def iter(self):
        """This element and every element under it, in document order."""
        yield self
        for kid in self.kids:
            if isinstance(kid, Node):
                yield from kid.iter()

    def text(self, sep=""):
        return sep.join(k if isinstance(k, str) else k.text(sep) for k in self.kids
                        if isinstance(k, str) or k.tag not in ("script", "style"))

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def closest(self, tag=None, cls=None):
        node = self.parent
        while node and not ((tag is None or node.tag == tag) and (cls is None or cls in node.classes())):
            node = node.parent
        return node

    def elements(self):
        return [k for k in self.kids if isinstance(k, Node)]


class Tree(HTMLParser):
    """A lenient element tree: an end tag closes its nearest open match, and a stray one is ignored."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.at = Node("#root", (), None)
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.at)
        self.at.kids.append(node)
        self.at = self.at if tag in VOID else node

    def handle_startendtag(self, tag, attrs):
        self.at.kids.append(Node(tag, attrs, self.at))

    def handle_endtag(self, tag):
        node = self.at
        while node is not self.root and node.tag != tag:
            node = node.parent
        self.at = node.parent if node is not self.root else self.at

    def handle_data(self, data):
        self.at.kids.append(data)


class Item(NamedTuple):
    kind: str
    page: str  # a page slug, SHARED, or None when nothing maps it
    key: object  # whitespace-free text, ("id", id, its question), or (aria-label, sorted mark titles) for a figure
    shown: str
    source: str = ""


def squash(text):
    """Whitespace-free, so a page may rewrap or re-indent text."""
    return "".join(text.split())


def spaced(node):
    return " ".join(node.text(" ").split())


def heading(node):
    return int(node.tag[1]) if re.fullmatch(r"h[1-6]", node.tag) else 0


def placed(name, root):
    """Each element in document order with its page. Report headings map through the page anchors."""
    design = name.removeprefix(METHODS).removesuffix(".html")
    heads = []
    for node in root.iter():
        if (level := heading(node)) and node.attrs.get("id"):
            heads = [h for h in heads if h[0] < level] + [(level, node.attrs["id"])]
        if name.startswith(METHODS):
            page = f"designs/{design}" if design in VIEWS else None
        elif name == snapshot.SHOWCASE:
            main = node if node.tag == "main" else node.closest("main")
            page = VIEWS.get(main.attrs.get("id")) if main else None
        else:
            page = next((ANCHORS[i] for _, i in reversed(heads) if i in ANCHORS), None)
        yield node, page


def fold(node):
    """The summary text of the nearest enclosing details, or ""."""
    details = node.closest("details")
    summary = next((k for k in details.elements() if k.tag == "summary"), None) if details else None
    return spaced(summary) if summary else ""


def method_columns(name, summary):
    """Per-method column definitions live once on glossary or measures, without their own fold."""
    return name.startswith(METHODS) and summary.startswith("Column definitions")


def is_row(node):
    return (node.tag == "tr" and not node.closest("thead")) or "entry" in node.classes()


def pair(dt):
    """A dt's text with its following dd's, as one term."""
    kids = dt.parent.elements()
    dd = kids[kids.index(dt) + 1:][:1]
    return " ".join([spaced(dt)] + [spaced(d) for d in dd if d.tag == "dd"])


def figure(node):
    marks = tuple(sorted(spaced(t) for t in node.iter() if t.tag == "title" and t.parent is not node))
    return (node.attrs["aria-label"], marks)


def question(node):
    """The squashed text of an answer's .aq question, or ""."""
    return next((squash(n.text()) for n in node.iter() if "aq" in n.classes()), "")


def item(name, node, page):
    """The item this element holds, or None."""
    cls = node.classes()
    if node.tag == "svg" and node.attrs.get("aria-label"):
        return Item("figure", page, figure(node), node.attrs["aria-label"])
    if is_row(node):
        kind = "term" if page == "glossary" else "row"
        return Item(kind, SHARED if method_columns(name, fold(node)) else page, squash(node.text()), spaced(node))
    if node.tag == "summary" and ROWS.search(text := spaced(node)) and not method_columns(name, text):
        return Item("table", page, squash(node.text()), text)
    if "tile" in cls or "kpi" in cls or (node.tag == "li" and node.closest(cls="award")):
        return Item("tile", page, squash(node.text()), spaced(node))
    if node.tag == "dt" and node.closest("dl", "terms"):
        return Item("term", SHARED, squash(text := pair(node)), text)
    if re.fullmatch(r"q\d+", node.attrs.get("id") or ""):
        return Item("term", page, ("id", node.attrs["id"], question(node)), "#" + node.attrs["id"])
    return None


def row_counts(name, root):
    """Each "N rows" summary against the rows under its own details, which guards this parser. A wide table is
    split into column slices, so every table under the details holds N rows; an entry list holds N entries."""
    groups = {}
    for row in filter(is_row, root.iter()):
        if group := (row.closest("table") if row.tag == "tr" else None) or row.closest("details"):
            groups.setdefault(id(group), [group, 0])[1] += 1
    sizes = {}
    for group, n in groups.values():
        details = group if group.tag == "details" else group.closest("details")
        sizes.setdefault(id(details), set()).add(n)
    errors = []
    for summary in (n for n in root.iter() if n.tag == "summary" and n.parent.tag == "details"):
        found = sizes.get(id(summary.parent), {0})
        if (m := ROWS.search(text := spaced(summary))) and found != {int(m.group(1))}:
            errors.append(f"{name}: {text!r} but {', '.join(map(str, sorted(found)))} rows parse under it")
    return errors


def inventory(files):
    """(items, errors) over the snapshot HTML sources, by name relative to the snapshot root."""
    items, errors = [], []
    for name, html in sorted(files.items()):
        if name not in (snapshot.REPORT, snapshot.SHOWCASE) and not name.startswith(METHODS):
            continue
        root = Tree(html).root
        errors += row_counts(name, root)
        for node, page in placed(name, root):
            if found := item(name, node, page):
                items.append(found._replace(source=name))
                if found.page is None:
                    errors.append(f"{name}: no page maps {found.kind} {found.shown!r}")
    return items, errors


class Page(NamedTuple):
    stub: bool
    texts: Counter
    ids: dict  # id to its element
    figures: Counter
    root: Node


def squashed(node, out):
    """Fill out with {id(element): squashed text} for node and the elements under it, in one pass."""
    out[id(node)] = text = "".join(squash(k) if isinstance(k, str) else squashed(k, out) for k in node.kids
                                   if isinstance(k, str) or k.tag not in ("script", "style"))
    return text


def texts(nodes, root):
    """How many elements hold each whole squashed text. A wrapper around one same-text element adds no copy,
    and a dt with its dd counts as one term."""
    text = {}
    squashed(root, text)
    counts = Counter()
    for n in nodes:
        if (t := text.get(id(n))) and t not in {text.get(id(k)) for k in n.elements()}:
            counts[t] += 1
        if n.tag == "dt" and (p := squash(pair(n))) not in (text[id(n)], text[id(n.parent)]):
            counts[p] += 1
    return counts


def parse(html):
    root = Tree(html).root
    nodes = list(root.iter())
    stub = any(n.tag == "meta" and n.attrs.get("name") == STUB for n in nodes)
    figures = Counter(figure(n) for n in nodes if n.tag == "svg" and n.attrs.get("aria-label"))
    return Page(stub, texts(nodes, root), {n.attrs["id"]: n for n in nodes if n.attrs.get("id")}, figures, root)


def label(slug):
    return slug or "landing"


def mark_diff(want, page):
    """Why no figure on the page matches: the mark titles missing and extra against a same-labelled one."""
    same = [f for f in page.figures if f[0] == want[0]]
    if not same:
        return "no figure has this aria-label"
    have = Counter(same[0][1])
    missing, extra = Counter(want[1]) - have, have - Counter(want[1])
    return f"missing marks {sorted(missing)}, extra marks {sorted(extra)}"


def lacks(want, page):
    """How the page falls short of one item seen n times, or None."""
    (kind, key, shown), n = want
    if kind == "figure":
        return None if page.figures[key] >= n else mark_diff(key, page)
    if isinstance(key, tuple):
        if (node := page.ids.get(key[1])) is None:
            return "no such id"
        return None if question(node) == key[2] else "question differs"
    have = page.texts[key]
    return None if have >= n else f"found {have} of {n}"


ORDER = {p.slug: i for i, p in enumerate(pagemap.PAGES)}


def order(slug):
    return ORDER.get(slug, len(ORDER))


def needed(items):
    """{page: Counter of (kind, key, shown)} in page order, shared last. A page needs each item as often as one
    source repeats it, so a page may merge the copies that two sources hold. A shared item is needed once."""
    per, out = {}, {}
    for i in items:
        per.setdefault((i.source, i.page), Counter())[(i.kind, i.key, i.shown)] += 1
    for (_, page), counts in per.items():
        out[page] = out.get(page, Counter()) | (Counter(set(counts)) if page == SHARED else counts)
    return dict(sorted(out.items(), key=lambda kv: order(kv[0])))


def coverage(items, pages, final=False):
    """(errors, items checked). pages maps slug to html. An item on a stub page waits, as shared ones do while
    glossary or measures is a stub."""
    parsed = {slug: parse(html) for slug, html in pages.items()}
    errors = [f"{label(s)} is a stub" for s in sorted(parsed, key=order) if final and parsed[s].stub]
    checked = []
    for page, counts in needed(items).items():
        homes = SHARED_PAGES if page == SHARED else (page,)
        if page is None:  # inventory already names each unmapped item
            continue
        if absent := [h for h in homes if h not in parsed]:
            errors.append(f"no page {label(absent[0])} for {sum(counts.values())} items")
            continue
        if any(parsed[h].stub for h in homes):
            continue
        checked.append(page)
        for want in counts.items():
            if all(why := [lacks(want, parsed[h]) for h in homes]):
                (kind, _, shown), _ = want
                errors.append(f"{SHARED if page == SHARED else label(page)} lacks {kind} {shown!r}: {why[0]}")
    return errors, sum(i.page in checked for i in items)


def is_label_page(slug):
    return slug.startswith("results/") or slug == "data" or slug.startswith("data/")


def labels(root):
    """(what, text) for each figure title, axis label, table header and tile label."""
    for node in root.iter():
        if node.tag == "figcaption":
            yield from (("figure title", spaced(h)) for h in node.iter() if heading(h))
        elif node.tag == "figure":
            # A parts.figure title sits above its diagram, outside the figcaption.
            yield from (("figure title", spaced(h)) for h in node.elements() if heading(h))
        elif node.tag == "th" and node.closest("thead"):
            yield "table header", spaced(node)
        elif "tile" in node.classes() or "kpi" in node.classes():
            first = next((k for k in node.elements() if k.tag == "span"), None)
            yield from [("tile label", spaced(first))] if first else []
        elif node.tag == "svg":
            # A source chart names an axis in the centred text right after its axis line.
            kids = node.elements()
            yield from (("axis label", spaced(t)) for a, t in zip(kids, kids[1:]) if a.tag == "line"
                        and "axis" in a.classes() and t.tag == "text" and t.attrs.get("text-anchor") == "middle")


def dfn_names(page):
    """Each dfn's text, its id read as words, and its data-alias names split on |."""
    names = set()
    for dfn in (n for n in page.root.iter() if n.tag == "dfn"):
        names |= {spaced(dfn), (dfn.attrs.get("id") or "").replace("-", " ")}
        names |= set((dfn.attrs.get("data-alias") or "").split("|"))
    return {n.strip().casefold() for n in names if n.strip()}


def folded(label):
    return label.strip().casefold()


def bare(label):
    """A label less a trailing ", unit" or " /N", folded for case."""
    return folded(UNIT.sub("", label))


def metric_defs(pages):
    """(errors, labels checked). A figure title is defined when a dfn name on measures appears in it as whole words,
    and any other label when it is a dfn name less its unit. Labels wait while measures is a stub."""
    measures = parse(pages[MEASURES]) if MEASURES in pages else None
    if measures and measures.stub:
        return [], 0
    names = dfn_names(measures) if measures else set()
    alts = "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
    within = re.compile(r"(?<!\w)(?:" + alts + r")(?!\w)") if names else None

    def defined(what, text):
        """A dfn name, which may hold a comma, is the label whole or less its unit."""
        if what == "figure title":
            return bool(within and within.search(text.casefold()))
        return folded(text) in names or bare(text) in names

    errors, checked = [], 0
    for slug in sorted(filter(is_label_page, pages), key=order):
        page = parse(pages[slug])
        for what, text in [] if page.stub else labels(page.root):
            if not re.search(r"[^\W\d_]", text):
                continue
            checked += 1
            if not defined(what, text):
                errors.append(f"{slug} {what} {text!r} has no dfn on {MEASURES}")
    return errors, checked


def load_pages(root):
    """{slug: html} for every page of the study."""
    pages = check_study_nav.load(root)
    return {url.removeprefix(BASE).rstrip("/"): html for url, html in pages.items()
            if url.startswith(BASE) and html is not None}


def check(root, final=False):
    """(errors, summary line) for the committed snapshot and study pages under root."""
    items, errors = inventory(snapshot.load(Path(root) / "_snapshots/kalah-tdd-study").files)
    pages = load_pages(root)
    covered, checked = coverage(items, pages, final)
    defined, labelled = metric_defs(pages)
    stubs = sum(parse(html).stub for html in pages.values())
    kinds = ", ".join(f"{n} {k}" for k, n in sorted(Counter(i.kind for i in items).items()))
    summary = f"{len(items)} items ({kinds}): {checked} checked, {labelled} labels checked, {stubs} stub pages skipped"
    return errors + covered + defined, summary


if __name__ == "__main__":
    args = sys.argv[1:]
    final = "--final" in args
    errors, summary = check(next((a for a in args if a != "--final"), "."), final)
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    print(f"Kalah TDD study completeness: {summary}")
    sys.exit(1 if errors else 0)
