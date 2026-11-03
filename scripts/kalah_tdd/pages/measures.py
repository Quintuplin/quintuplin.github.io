"""The measures page (#84): every report column and per-method column definition from the snapshot as a card with
its dfn, formula, inputs, module and claim tag, the glossary terms the plan names as metrics, and a column index."""

import re
from html import escape, unescape
from typing import NamedTuple

from .. import parts, snapshot

ENTRY = re.compile(r'<div class="entry">(<p class="sub"><b>(.*?)</b>\. (?:Source: (.*?)\. )?Tag: (\w+)\.</p>.*?)</div>', re.S)
FOLD = re.compile(r"<details><summary>(Column definitions[^<]*)</summary>(.*?)</details>", re.S)
MODULE = re.compile(r"[\w/.-]+\.py\b")
ABSENT = "not stated in the snapshot"
# Family h3 id and title, then its card names in order. Every column and method row sits in one family.
FAMILIES = (
    ("tests", "Tests", ("Functional mark /15", "Hidden pass /76", "Unseen pass /69", "Acceptance pass /6", "Seen tests")),
    ("static-analysis-and-mutation", "Static analysis and mutation",
     ("Strict PMD compliance", "Static analysis violations", "Strict PMD violations", "Mutation score", "K/N",
      "Adjusted mutation", "Unadjusted mutation")),
    ("size-and-speed", "Size and speed", ("Lines of code", "Classes", "Methods", "Fields", "Bench median ms")),
    ("cost", "Cost", ("Tokens", "Weighted tokens", "Wall time", "Agent calls", "Run order", "Cost to completion", "M",
                      "M_io")),
    ("review-ratings", "Review ratings",
     ("Clear Presentation /5", "Explanatory Language /5", "Consistent Code /5", "Used Content /5", "Simple Constructs /5",
      "Minimal Duplication /5", "Modular Structure /5", "Problem Alignment (tentative) /5", "CQP", "CQP accepted")),
    ("combined-and-consistency", "Combined and consistency", ("E", "Relative spread", "Consistency score C")),
    ("records", "Records", ("Method", "Branch", "Audit flags", "Family", "Planned contrast", "Holm p")),
)
TEST_ORDER = ("test-order-measures", "Test order measures", ("APFD-I", "APFDc-H", "Kendall distance"))
# Metrics with no column row, quoted from a report glossary row: (row name, the words the dfn marks in it).
TERMS = {"Seen tests": ("Hidden, seen, unseen and acceptance tests", "Seen tests"),
         "K/N": ("Mutation score and K/N", "K/N"), "E": ("Awards and E", "E"),
         "APFD-I": ("APFD-I", "APFD-I"), "Kendall distance": ("Kendall distance", "Kendall distance")}
# Column rows whose source module only a glossary row names.
CITES = {"APFDc-H": "APFDc-H", "Cost to completion": "Cost to completion", "M": "M and M_io", "M_io": "M and M_io"}
# Term cards whose inputs are the Source fields of these columns.
INPUT_ROWS = {"K/N": ("Mutation score",),
              "E": ("Static analysis violations", "Adjusted mutation", "Hidden pass /76", "Unseen pass /69")}
FUNCTIONS = {"E": "error_count"}


class Row(NamedTuple):
    name: str  # plain text
    source: str  # HTML, "" for a glossary row
    tag: str
    inner: str  # the entry's HTML inside its div
    head: str  # the name as the source writes it in HTML


def rows(html):
    return [Row(unescape(m.group(2)), m.group(3) or "", m.group(4), m.group(1), m.group(2)) for m in ENTRY.finditer(html)]


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


class MetricSources:
    """The definitions the page quotes, read from the snapshot report, method pages and facts."""

    def __init__(self, snap):
        self.snap, self.report = snap, snap.files[snapshot.REPORT]
        self.columns_html = snapshot.section(self.report, "columns")
        self.columns = rows(self.columns_html)
        self.glossary = {r.name: r for r in rows(snapshot.section(self.report, "glossary"))}
        self.methods = self.method_rows()

    def method_rows(self):
        """Distinct method page Column definitions rows, less exact copies of a report column row."""
        seen = {plain(r.inner) for r in self.columns}
        out = []
        for name, text in sorted(self.snap.files.items()):
            if not name.startswith("runs/full-1/methods/"):
                continue
            for _, fold in FOLD.findall(text):
                for r in rows(fold):
                    if plain(r.inner) not in seen:
                        seen.add(plain(r.inner))
                        out.append(r)
        return out

    def glossary_row(self, name):
        if name not in self.glossary:
            raise ValueError(f"report glossary has no row {name!r}")
        return self.glossary[name]

    def fact_doc(self, name):
        analysis = self.snap.facts["analysis"]
        for f in analysis["functions"] + analysis["stats"]:
            if f["name"] == name and f.get("doc"):
                return f["doc"]
        raise ValueError(f"facts.analysis has no doc for {name!r}")

    def summary(self):
        return FOLD.search(self.columns_html).group(1)


def slug(name):
    """The dfn id: lower case, less a "(...)" note and a trailing " /N" total."""
    bare = re.sub(r"\s*\(.*?\)|\s*/\s*\d+$", "", name)
    return re.sub(r"[^a-z0-9]+", "-", bare.lower()).strip("-")


def link(name, text=None):
    return f'<a href="#{slug(name)}">{escape(text or name)}</a>'


def sub(html):
    return f'<p class="sub">{html}</p>'


class MetricCards:
    """One card per family entry: the source entry word for word with a dfn and a pill, then formula, inputs and
    module lines."""

    def __init__(self, src):
        self.src = src
        self.by_name = self.assign()

    def assign(self):
        """{card name: Row}. Refuse a source row in no family or in two, and a family name with no row."""
        named = [n for _, _, names in FAMILIES + (TEST_ORDER,) for n in names]
        if dup := sorted({n for n in named if named.count(n) > 1}):
            raise ValueError(f"cards {dup} sit in two families")
        by_name = {}
        for r in self.src.columns + self.src.methods:
            if r.name not in named:
                raise ValueError(f"source row {r.name!r} is in no family")
            if r.name in by_name:
                raise ValueError(f"two source rows are named {r.name!r}")
            by_name[r.name] = r
        for name, (row, _) in TERMS.items():
            by_name[name] = self.src.glossary_row(row)
        if missing := [n for n in named if n not in by_name]:
            raise ValueError(f"family cards {missing} have no source row")
        return by_name

    def source_text(self, name):
        return plain(self.by_name[name].inner)

    def marked(self, name):
        """The entry HTML with its dfn and its claim tag as a pill. A term's dfn marks its words in the definition."""
        r = self.by_name[name]
        inner = r.inner.replace(f"Tag: {r.tag}.</p>", f"Tag: {parts.tag(r.tag)}.</p>", 1)
        dfn = lambda words: f'<dfn id="{slug(name)}">{words}</dfn>'
        if name not in TERMS or TERMS[name][1] == r.name:
            return inner.replace(f"<b>{r.head}</b>", f"<b>{dfn(r.head)}</b>", 1)
        words = escape(TERMS[name][1], quote=False)
        at = inner.index("<b>Definition:</b>")
        found = re.compile(rf"(?<![\w-]){re.escape(words)}(?![\w-])").search(inner, at)
        if not found:
            raise ValueError(f"glossary row {r.name!r} never states {TERMS[name][1]!r}")
        return inner[:found.start()] + dfn(words) + inner[found.end():]

    def module(self, name):
        if m := MODULE.search(self.source_text(name)):
            return f"Module: <code>{escape(m.group(0))}</code>."
        if name in CITES:
            row = self.src.glossary_row(CITES[name])
            if m := MODULE.search(plain(row.inner)):
                return f"Module: <code>{escape(m.group(0))}</code>, as the glossary row <i>{escape(row.name)}</i> states."
        return f"Module: {ABSENT}."

    def inputs(self, name):
        if name not in TERMS:
            return None  # a column row states its Source
        if name in INPUT_ROWS:
            cols = [self.by_name[c] for c in INPUT_ROWS[name]]
            listed = [f"{link(c.name)} ({c.source})" for c in cols]
            return f"Inputs: the Source{'s' * (len(cols) > 1)} of " + joined(listed) + "."
        files = re.findall(r"[\w/-]+\.(?:tsv|json|txt|csv)\b", self.source_text(name))
        return "Inputs: " + (joined([f"<code>{escape(f)}</code>" for f in files]) + ", as the glossary row states"
                             if files else ABSENT) + "."

    def card(self, name, formula=None):
        lines = [f"Formula: {formula}" if formula else None, self.inputs(name)]
        if name in FUNCTIONS:
            fn = FUNCTIONS[name]
            lines.append(f"Function <code>{fn}</code> doc: {escape(self.src.fact_doc(fn))}")
        lines.append(self.module(name))
        return f'<div class="entry"><div>{self.marked(name)}</div>{"".join(sub(l) for l in lines if l)}</div>'


def joined(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def cited(code, sentence, what):
    """Refuse a typed formula whose numbers are not all in the sentence it is read from."""
    for number in re.findall(r"\d+(?:\.\d+)?", plain(code)):
        if not re.search(rf"(?<![\d.]){re.escape(number)}(?![\d.])", sentence):
            raise ValueError(f"{what} formula number {number} is not in its source sentence")
    return f"<code>{code}</code>"


def formulas(src, cards):
    """Typed expressions for weighted tokens, M and E, each from its source sentence."""
    weight_text = src.snap.facts["pipeline"]["weight_text"]
    weights = re.findall(r"(input|cache creation|cache read|output) ([\d.]+)", weight_text)
    if not weights:
        raise ValueError(f"facts.pipeline.weight_text names no token weights: {weight_text!r}")
    if weight_text not in cards.source_text("Weighted tokens"):
        raise ValueError("the Weighted tokens row does not quote facts.pipeline.weight_text")
    tokens = " + ".join(f"{w} × {link('Tokens', kind)}" for kind, w in weights)
    m_row, error_doc = cards.source_text("M"), src.fact_doc("error_count")
    if "cost to completion times 1 minus APFDc-H" not in m_row:
        raise ValueError("the M row no longer states M as the cost to completion times 1 minus APFDc-H")
    m = f"{link('Cost to completion', 'cost to completion')} × (1 − {link('APFDc-H')})"
    operands = [(t, c) for t, c in zip(("distinct PMD findings", "adjusted surviving mutants", "hidden failures",
                                        "unseen failures"), INPUT_ROWS["E"])]
    if absent := [t for t, _ in operands if t not in error_doc]:
        raise ValueError(f"error_count doc no longer names {absent}")
    e = " + ".join(link(c, t) for t, c in operands)
    return {"Weighted tokens": cited(tokens, weight_text, "Weighted tokens"), "M": cited(m, m_row, "M"),
            "E": cited(e, error_doc, "E")}


def named_runs(snap, html):
    """Each snapshot run the text of html names, in first-mention order. A run inside a longer run name is none."""
    runs = sorted(snap.facts["runs"], key=len, reverse=True)
    pattern = re.compile(r"(?<![\w/-])(?:" + "|".join(map(re.escape, runs)) + r")(?![\w/-])")
    return list(dict.fromkeys(m.group(0) for m in pattern.finditer(re.sub(r"<[^>]+>", " ", html))))


def lead(snap, rest):
    docs = joined([f"{run} {snapshot.run_doc(snap, run)}" for run in named_runs(snap, rest)])
    return ("<p>Each card quotes a column or term definition from the snapshot with its claim tag. The lines under it "
            "give the typed formula where the page has one, the inputs when the definition names no Source, and the "
            "module that computes it.</p>\n"
            f"<p>The methods text on these pages is from methods doc {snap.doc}. The runs this page names were built "
            f"under these doc versions, by short sha256: {docs}.</p>")


def column_index(src, cards):
    """Every report column with its source, tag and family, under the source fold's own summary."""
    family = {n: title for _, title, names in FAMILIES + (TEST_ORDER,) for n in names}
    summary = src.summary()
    if int(re.search(r"(\d+) rows", summary).group(1)) != len(src.columns):
        raise ValueError(f"{summary!r} but the report Columns section holds {len(src.columns)} rows")
    head = "".join(f'<th scope="col">{h}</th>' for h in ("Column", "Source", "Tag", "Section"))
    body = "".join(f'<tr><th scope="row">{escape(r.name, quote=False)}</th><td>{r.source}</td>'
                   f"<td>{parts.tag(r.tag)}</td><td>{escape(family[r.name])}</td></tr>" for r in src.columns)
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    return ('<h2 id="column-index">Column index</h2>\n<p>Each report column with its source file, its claim tag and '
            f"the section of this page that defines it.</p>\n<details><summary>{escape(summary)}</summary>"
            f"{parts.table(table, 'Column index')}</details>")


def family(id, title, names, cards, typed, level=3):
    return (f'<h{level} id="{id}">{escape(title)}</h{level}>\n<div class="shaped">'
            + "".join(cards.card(n, typed.get(n)) for n in names) + "</div>")


def body(page, snap, idx):
    src = MetricSources(snap)
    cards = MetricCards(src)
    typed = formulas(src, cards)
    intro = re.search(r"<p>.*?</p>", src.columns_html, re.S).group(0)
    rest = [f'<h2 id="columns">Columns</h2>\n{intro}\n'
            + "\n".join(family(id, title, names, cards, typed) for id, title, names in FAMILIES),
            family(*TEST_ORDER, cards, typed, level=2), column_index(src, cards)]
    return [lead(snap, "\n".join(rest))] + rest
