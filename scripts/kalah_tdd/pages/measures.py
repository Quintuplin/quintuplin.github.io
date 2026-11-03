"""The measures page (#84): every report column and per-method column definition from the snapshot as a card with
its dfn, formula, inputs, module and claim tag, the glossary terms the plan names as metrics, and a column index."""

import re
from html import escape, unescape
from typing import NamedTuple

from .. import pagemap, parts, snapshot
from ..figures import flow

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
# Figure 4.1: each lane's cards, whose Source fields must name every file its nodes name.
LANES = {"Tests": ("Functional mark /15", "Hidden pass /76", "Unseen pass /69", "Acceptance pass /6"),
         "Static analysis": ("Strict PMD compliance", "Static analysis violations", "Strict PMD violations"),
         "Mutation": ("Mutation score", "Adjusted mutation", "Unadjusted mutation"),
         "Cost": ("Tokens", "Weighted tokens", "Agent calls", "Cost to completion", "APFDc-H", "M", "M_io"),
         "Review": FAMILIES[4][2]}
# One row of four columns: raw input, collected file, measure, score. Edges run left to right in each lane.
NODES = (("t1", "grade.tsv, seen.tsv, summary.json", "Tests", 1, ""),
         ("t2", "Functional mark; hidden, unseen, acceptance pass", "Tests", 2, ""),
         ("s0", "pmd.txt", "Static analysis", 0, ""), ("s1", "metrics.json", "Static analysis", 1, ""),
         ("s2", "Strict PMD, PMD violations", "Static analysis", 2, ""), ("s3", "E", "Static analysis", 3, "awards.py error_count"),
         ("m0", "mutate.txt", "Mutation", 0, ""), ("m1", "metrics.json", "Mutation", 1, ""),
         ("m2", "Mutation, adjusted mutation", "Mutation", 2, ""),
         ("c0", "transcripts", "Cost", 0, ""), ("c1", "costs.json", "Cost", 1, "With steps.csv or batch.json tcp.calls"),
         ("c2", "curve.json: cost to completion, APFDc-H", "Cost", 2, "harness/report/curve.py"),
         ("c3", "M, M_io", "Cost", 3, "Times 1 minus APFDc-H"),
         ("r0", "Blind raters", "Review", 0, ""), ("r1", "rating.json", "Review", 1, ""),
         ("r2", "Principle medians /5", "Review", 2, ""), ("r3", "CQP, CQP accepted", "Review", 3, ""))
# A score node: where its sentence comes from, then each input node with the terms that sentence gives it.
COMPOSITES = {"s3": ("function", "error_count", {"t2": ("hidden failures", "unseen failures"),
                                                 "s2": ("distinct PMD findings",), "m2": ("adjusted surviving mutants",)}),
              "c3": ("glossary", "M and M_io", {"c2": ("cost to completion", "APFDc-H")}),
              "r3": ("glossary", "CQP and CQP accepted", {"r2": ("rating medians",)})}
FILE = re.compile(r"[\w-]+\.(?:tsv|json|txt|csv|calls)\b")
KINDS = ("input", "cache creation", "cache read", "output")  # the token kinds weight_text weighs
# The other names results and data pages give a metric card, as labels or as a figure title's words.
ALIASES = {"Classes": ("Classes in src/", "Median classes"), "Static analysis violations": ("PMD violations",),
           "Mutation score": ("Mutants killed", "Score %"), "K/N": ("Killed", "Compiled mutants"),
           "Adjusted mutation": ("Adjusted %", "Adjusted mutation score", "Median adjusted mutation"),
           "Bench median ms": ("Bench run times", "Median ms"),
           "Cost to completion": ("Weighted tokens to completion", "Median cost to completion"),
           "M": ("M, weighted tokens per hidden test passed",), "CQP": ("Median CQP",), "Planned contrast": ("Contrast",),
           "Consistency score C": ("Consistency score",)}


def slug(name):
    """The dfn id: lower case, less a "(...)" note and a trailing " /N" total."""
    bare = re.sub(r"\s*\(.*?\)|\s*/\s*\d+$", "", name)
    return re.sub(r"[^a-z0-9]+", "-", bare.lower()).strip("-")


def link(name, text=None, title=None):
    hint = f' title="{escape(title)}"' if title else ""
    return f'<a href="#{slug(name)}"{hint}>{escape(text or name)}</a>'


class Field(NamedTuple):
    name: str
    text: str  # this site's definition, HTML
    # (kind, where, sentence): glossary row, report section id, function, a list phase phrase or a run's method pages
    quote: tuple = ()
    aliases: tuple = ()


RATING = "rating-agreement-full-1"
# Table fields: results and data page labels that name no metric, grouped as h3 sections.
FIELDS = (
    ("builds-and-methods", "Builds and methods", (
        Field("Slug", "The method's short lowercase name.",
              ("glossary", "Method and slug", "Its slug is its short lowercase name, which the Branch column shows after method/.")),
        Field("Build", "The build a method's row stands for.", ("section", "replicate-table-rep-1",
              "Build names the best, median and worst of each method by adjusted mutation, then lower cost to completion.")),
        Field("Source", "The run a build comes from, and whether it is its method's representative build."),
        Field("Replicate", "One build of a method in a replicated run. A Replicates column counts them.",
              ("glossary", "Replicate and representative build",
               "A replicate is one of the 5 builds of a method in run rep-1 or rep-2."), ("Replicates",)),
        Field("Representative build", "The one build of a method that a per-method row reports.",
              ("glossary", "Replicate and representative build", "The representative build is the middle replicate by "
               "adjusted mutation score, then by lower cost to completion.")),
        Field("Run ms", f"The time of each bench run of a build in milliseconds. Their median is the "
              f"{link('Bench median ms')}.", aliases=("Bench run time",)))),
    ("contrasts-and-tests", "Contrasts and tests", (
        Field("Outcome", f"The measure a {link('Planned contrast', 'planned contrast')} compares.",
              ("glossary", "Planned contrast", "A pair of methods and an outcome fixed before any build of its run.")),
        Field("n", "The count of builds or items a statistic is computed over, one count per group when it compares two."),
        Field("U", "The Mann-Whitney U statistic of a contrast.", ("function", "mann_whitney_exact")),
        Field("p", f"The p value of a test before Holm correction. The {link('Holm p')} column corrects it."),
        Field("Permutation p", "The p value of a seeded permutation test.", ("function", "brown_forsythe_permutation")),
        Field("Metric", "The measure a row's statistic is computed on."),
        Field("Statistic", "The test statistic a row reports, named with its value, such as a Brown-Forsythe F.",
              ("function", "brown_forsythe")),
        Field("Value", "The value a row reports for its statistic, cap or setting."),
        Field("95% interval", "A 95% interval around a row's value. A percent interval of a mutation score is a Wilson "
              "interval.", ("function", "wilson"), ("95% interval %",)))),
    ("ratings", "Ratings", (
        Field("Principle", "One of the review principles each build is rated on.", ("section", RATING,
              "Three blind raters scored each item from 1 to 5 on each cqp.html principle.")),
        Field("Alpha", "Rater agreement on a principle. A Finals or All prefix names the set of rated items it covers.",
              ("section", RATING, "Alpha is Krippendorff's ordinal alpha over the three rater slots, with a seeded "
               "bootstrap 95% interval in brackets."), ("Finals alpha [95% CI]", "All alpha [95% CI]")),
        Field("Finals q", "The bootstrap shares that show how sure a principle's status is.",
              ("section", RATING, "q is the share of bootstrap alphas below 0.8 and below 0.7."), ("Finals q 0.8, 0.7",)),
        Field("Status", "Whether a principle's ratings are accepted, tentative or unchecked.", ("section", RATING,
              "The finals alpha sets each status: accepted at 0.8 or more, tentative at 0.7 or more and unchecked below.")),
        Field("LOC and PMD rho", "How closely a principle's ratings follow code size and PMD violations.",
              ("section", RATING, "LOC and PMD rho are Spearman correlations of the finals medians with lines of code and "
               "with distinct PMD violations, with Holm-adjusted q."), ("LOC rho (q)", "PMD rho (q)")),
        Field("Round", "One rating round of the blind raters, such as round-a."),
        Field("Role", "What a rating round was for, such as a calibration that passed or failed.",
              ("section", RATING, "A calibration round's role comes from its committed verdict.json.")),
        Field("Agent time", f"The sum over a round's agents of each agent's first to last timestamp, beside its "
              f"{link('Wall time')}. Agents that ran side by side add up.", ("method", "full-1",
              "Agent time sums each agent's first to last timestamp, so agents that ran side by side add up.")))),
    ("run-records", "Run records", (
        Field("Label", "The harness label of an agent call, such as review:r18."),
        Field("Cap", "The harness limit a labelled call reached, such as cycles."),
        Field("Agent id", "The id of an agent transcript that the cost records attribute to no method."))),
    ("test-list-and-stages", "Test list and stages", (
        Field("Rating", "The list phase rating a reliability row checks, such as Risk.", ("section", "list-reliability",
              "A second lister in run tcp-1-list2 rated the clauses and candidate tests of the list of run tcp-1-list blind.")),
        Field("Run", "The snapshot run a row belongs to."),
        Field("Setting", "A setting of run tcp-1."),
        Field("Arm", "One arm of run tcp-1.", ("glossary", "Arm", "In tcp-1 each arm follows one order of the same test list.")),
        Field("Order", "The order of the test list an arm follows."),
        Field("Clause", "A numbered functional rule of the spec.", ("list", "as a clause R1 to Rn")),
        Field("Risk", "A clause's 1 to 3 rating of the chance a first implementation gets it wrong.",
              ("list", "chance a first implementation gets it wrong")),
        Field("Usage", "A clause's 1 to 100 rating of how much of a game exercises it.", ("list", "Rate its usage")),
        Field("Candidate", "A candidate test of the list.", ("list", "candidate tests")),
        Field("Checks", "The clauses a candidate's assertions observe.", ("list", "checks lists every clause")),
        Field("Relies", "The clauses a candidate needs and does not assert.", ("list", "relies lists clauses")),
        Field("Estimate", "The production lines a candidate needs on the starter alone.",
              ("list", "Estimate the production lines each candidate needs")),
        Field("Stage", "One stage of an arm's harness flow."),
        Field("Runs as", "How a stage runs, once throughout an arm or repeated per unit."),
        Field("Steps", "The steps a stage takes."),
        Field("Details", "Further detail of a stage."),
        Field("Note", "A note on a row."),
        Field("Hidden-pass curve area", f"The area under an arm's curve of hidden tests passed, which {link('APFD-I')} "
              "scores."))),
)
# Field labels the G10b results pages build from facts: {name: (label kind, page slugs)}, as G10-plan.md places them.
LATER = {**dict.fromkeys(("Run", "Outcome", "U"), ("Table header", ("results/contrasts",))),
         **dict.fromkeys(("Setting", "Value", "Arm", "Order", "Clause", "Risk", "Usage", "Candidate", "Checks", "Relies",
                          "Estimate", "Stage", "Runs as", "Steps", "Details", "Note"),
                         ("Table header", ("results/test-order",))),
         "Hidden-pass curve area": ("Axis label", ("results/test-order",))}


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
        if not (m := FOLD.search(self.columns_html)):
            raise ValueError("the report Columns section has no Column definitions fold summary")
        return m.group(1)

    def intro(self):
        """The paragraph before the Columns fold. A definition paragraph inside the fold is no intro."""
        if not (m := re.search(r"<p>.*?</p>", self.columns_html.split("<details>")[0], re.S)):
            raise ValueError("the report Columns section has no intro paragraph before its fold")
        return m.group(0)


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
        dfn = lambda words: f'<dfn id="{slug(name)}"{alias_attr(ALIASES.get(name, ()))}>{words}</dfn>'
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
        lines += [self.module(name), also(ALIASES.get(name, ()))]
        return f'<div class="entry"><div>{self.marked(name)}</div>{"".join(sub(l) for l in lines if l)}</div>'


def alias_attr(aliases):
    return f' data-alias="{escape("|".join(aliases))}"' if aliases else ""


def also(aliases):
    return f"Also labelled: {escape('; '.join(aliases))}." if aliases else None


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
    weights = re.findall(rf"({'|'.join(KINDS)}) ([\d.]+)", weight_text)
    if sorted(kind for kind, _ in weights) != sorted(KINDS):
        raise ValueError(f"facts.pipeline.weight_text does not weigh each of {', '.join(KINDS)} once: {weight_text!r}")
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
    # An operand is read from its column (a failure from a pass count), so the link says so.
    e = " + ".join(link(c, t, f"read from {c}") for t, c in operands)
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
            "module that computes it. Formula, Inputs, Module and Also labelled lines, this lead and the Figure 4.1 "
            f"caption are written by this site. Tag: {parts.tag('unchecked')}.</p>\n"
            f"<p>The methods text on these pages is from methods doc {snap.doc}. The runs this page names were built "
            f"under these doc versions, by short sha256: {docs}.</p>")


def heading_text(html):
    return plain(m.group(2)) if (m := re.search(r"<h([1-6])\b[^>]*>(.*?)</h\1>", html, re.S)) else ""


class TableFields:
    """A card per results or data page label that names no metric: this site's definition, a quoted source line
    where the snapshot defines it, and the report sections whose tables head a column with it."""

    def __init__(self, src, taken):
        self.src, self.heads = src, self.table_heads(src.report)
        ids = list(taken) + [slug(f.name) for _, _, fields in FIELDS for f in fields]
        if dup := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"dfn ids {dup} are on two cards")

    @staticmethod
    def table_heads(report):
        """{header, case folded: [section titles]} over the results and data page anchors. An anchor holds its own
        section less the sections of anchors under it."""
        anchors = [a for p in pagemap.PAGES for a in p.anchors]
        heads = {}
        for p in pagemap.PAGES:
            for a in p.anchors if p.part in ("Results", "Data") else ():
                own = snapshot.section(report, a)
                for b in anchors:
                    if b != a and re.search(rf'<h[1-6]\b[^>]*{snapshot.ID_ATTR}{re.escape(b)}"', own):
                        own = own.replace(snapshot.section(report, b), "")
                for thead in re.findall(r"<thead\b.*?</thead>", own, re.S):
                    for th in re.findall(r"<th\b[^>]*>(.*?)</th>", thead, re.S):
                        titles = heads.setdefault(plain(th).casefold(), [])
                        if (title := heading_text(own)) not in titles:
                            titles.append(title)
        return heads

    def quote(self, f):
        if not f.quote:
            return None
        kind, where, *said = f.quote
        if kind == "function":
            return f"Function <code>{where}</code> doc: {escape(self.src.fact_doc(where))}"
        if kind == "list":
            runs = self.src.snap.facts["runs"]
            run = runs["tcp-1"]["tcp"]["list_tag"]
            for k, step in enumerate(runs[run]["list_phase"], 1):
                if where in step:
                    return f"List phase step {k} of run <code>{run}</code>: {escape(step)}"
            raise ValueError(f"field '{f.name}': no list phase step of run {run} says {where!r}")
        if kind == "glossary":
            row = self.src.glossary.get(where)
            if row and said[0] in plain(row.inner):
                return f"The glossary row <i>{escape(row.name)}</i> says: {escape(said[0])} Tag: {parts.tag(row.tag)}."
            raise ValueError(f"field '{f.name}': the glossary row {where!r} no longer says {said[0]!r}")
        if kind == "method":  # an untagged paragraph every method page of the run repeats, so no pill
            pages = {n: t for n, t in self.src.snap.files.items() if n.startswith(f"runs/{where}/methods/")}
            if lacking := sorted(n for n, t in pages.items()
                                 if not any(said[0] in plain(p) for p in re.findall(r"<p\b[^>]*>.*?</p>", t, re.S))):
                raise ValueError(f"field '{f.name}': method pages {lacking} do not say {said[0]!r}")
            if not pages:
                raise ValueError(f"field '{f.name}': run {where} has no method pages")
            return f"Each method page of run <code>{where}</code> says: {escape(said[0])}"
        section = snapshot.section(self.src.report, where)
        for para in re.findall(r"<p\b[^>]*>.*?</p>", section, re.S):
            if said[0] in plain(para) and (tag := re.search(r"Tag: (\w+)\.", plain(para))):
                return (f"The report section <i>{escape(heading_text(section))}</i> says: {escape(said[0])} "
                        f"Tag: {parts.tag(tag.group(1))}.")
        raise ValueError(f"field '{f.name}': no tagged paragraph of report section {where!r} says {said[0]!r}")

    def where(self, f):
        titles = list(dict.fromkeys(t for n in (f.name,) + f.aliases for t in self.heads.get(n.casefold(), [])))
        said = [f"Table header in: {escape(joined(titles))}."] if titles else []
        if f.name in LATER:
            kind, pages = LATER[f.name]
            said.append(f"{kind} on {escape(joined([pagemap.BY_SLUG[p].title for p in pages]))}.")
        if not said:
            raise ValueError(f"field '{f.name}' heads no table on a results or data page")
        return " ".join(said)

    def card(self, f):
        head = (f'<b><dfn id="{slug(f.name)}"{alias_attr(f.aliases)}>{escape(f.name)}</dfn></b>. '
                f"Tag: {parts.tag('unchecked')}.")
        lines = [self.quote(f), self.where(f), also(f.aliases)]
        return (f'<div class="entry">{sub(head)}<p><b>Definition:</b> {f.text}</p>'
                + "".join(sub(l) for l in lines if l) + "</div>")

    def section(self):
        groups = "\n".join(f'<h3 id="{id}">{escape(title)}</h3>\n<div class="shaped fields">'
                           + "".join(self.card(f) for f in fields) + "</div>" for id, title, fields in FIELDS)
        return ('<h2 id="table-fields">Table fields</h2>\n<p>Each card defines a table header or axis label of the '
                "results and data pages that names no metric above. This site writes each definition, and a quoted glossary "
                "or report line keeps its source's tag. The Table header line names the report sections whose tables use the field. "
                f"Tag: {parts.tag('unchecked')}.</p>\n{groups}")


def column_index(src, cards):
    """Every report column with its source, tag and family, under the source fold's own summary."""
    family = {n: title for _, title, names in FAMILIES + (TEST_ORDER,) for n in names}
    summary = src.summary()
    if not (count := re.search(r"(\d+) rows", summary)):
        raise ValueError(f"{summary!r} states no row count")
    if int(count.group(1)) != len(src.columns):
        raise ValueError(f"{summary!r} but the report Columns section holds {len(src.columns)} rows")
    names = ("Column", "Source", "Tag", "Section")
    head = "".join(f'<th scope="col">{h}</th>' for h in names)
    # td cells with data-th, so the .cols table stacks into labelled cards on a narrow screen.
    body = "".join("<tr>" + "".join(f'<td data-th="{h}">{c}</td>' for h, c in zip(names, (
        escape(r.name, quote=False), r.source, parts.tag(r.tag), escape(family[r.name])))) + "</tr>" for r in src.columns)
    table = f'<table class="cols"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    return ('<h2 id="column-index">Column index</h2>\n<p>Each report column with its source file, its claim tag and '
            f"the section of this page that defines it.</p>\n<details><summary>{escape(summary)}</summary>"
            f"{parts.table(table, 'Column index')}</details>")


class MeasurePipeline:
    """Figure 4.1 from the lane cards' Source fields and the sentences that define each score node."""

    def __init__(self, src, cards):
        self.src, self.cards = src, cards
        self.nodes = [flow.node(*n) for n in NODES]
        lanes = [[n for n in self.nodes if n.lane == lane] for lane in LANES]
        self.edges = [flow.edge(a.id, b.id) for lane in lanes for a, b in zip(lane, lane[1:])]
        self.edges += [flow.edge(i, t) for t, (_, _, inputs) in COMPOSITES.items() for i in inputs
                       if self.lane(i) != self.lane(t)]
        self.check()

    def lane(self, id):
        return next(n.lane for n in self.nodes if n.id == id)

    def sentence(self, kind, name):
        return self.src.fact_doc(name) if kind == "function" else plain(self.src.glossary_row(name).inner)

    def check(self):
        for n in self.nodes:
            fields = " ".join(plain(self.cards.by_name[c].source) for c in LANES[n.lane])
            for name in FILE.findall(f"{n.label} {n.note}"):
                if name not in fields:
                    raise ValueError(f"Figure 4.1 node {n.label!r} names {name} but no {n.lane} card Source does")
            # A module must be in a lane card, the glossary row its Module line cites, or the card the node is.
            named = list(LANES[n.lane]) +[n.label] * (n.label in self.cards.by_name)
            stated = set(MODULE.findall(" ".join(f"{self.cards.source_text(c)} {plain(self.cards.module(c))}" for c in named)))
            stated |= {s.rsplit("/", 1)[-1] for s in stated}  # a bare file name matches its path's last part
            for name in MODULE.findall(f"{n.label} {n.note}"):
                if name not in stated:
                    raise ValueError(f"Figure 4.1 node {n.label!r} names {name} but no {n.lane} card or cited row does")
        for target, (kind, name, inputs) in COMPOSITES.items():
            text = self.sentence(kind, name)
            if absent := [t for terms in inputs.values() for t in terms if t not in text]:
                raise ValueError(f"{name} no longer names {absent}, which Figure 4.1 draws into {target}")

    def caption(self):
        said = []
        for target, (kind, name, inputs) in COMPOSITES.items():
            label = next(n.label for n in self.nodes if n.id == target).replace(", ", " and ")
            whose = f"the doc of function {name}" if kind == "function" else f"the glossary row {name}"
            said.append(f"{label} take{'' if ' and ' in label else 's'} {joined([t for terms in inputs.values() for t in terms])}, as {whose} states.")
        return ("Each lane reads left to right from raw input to collected file to measure to score. " + " ".join(said)
                + f" {self.undrawn()} Their cards below define them. On a narrow "
                "screen the diagram scrolls sideways and the text version holds the same steps.")

    def undrawn(self):
        """The sentence naming each card in no lane and on no node, by whole family where a family has none drawn."""
        drawn = {c for names in LANES.values() for c in names} | {n.label for n in self.nodes}
        whole, cards = [], []
        for _, title, names in FAMILIES + (TEST_ORDER,):
            left = [n for n in names if n not in drawn]
            if len(left) == len(names):
                whole.append(title)
            else:
                cards += left
        are = "is" if len(cards) == 1 else "are"
        if not whole:
            return f"{joined(cards)} {are} not drawn." if cards else ""
        families = f"The {joined(whole)} famil{'y is' if len(whole) == 1 else 'ies are'} not drawn"
        return f"{families}, nor {are} {joined(cards)}." if cards else f"{families}."

    def figure(self, n):
        title = "From raw inputs to scores"
        desc = (f"{len(LANES)} lanes, {', '.join(LANES)}, each from raw input to collected file to measure to score. "
                "E draws on the Tests, Static analysis and Mutation lanes.")
        svg = flow.svg("f4", title, desc, self.nodes, self.edges)
        return parts.figure(n, "f4", title, svg, escape(self.caption()), None,
                            flow.text_version(title, self.nodes, self.edges))


def pipeline(snap):
    """Figure 4.1's (nodes, edges), checked against the snapshot."""
    src = MetricSources(snap)
    drawn = MeasurePipeline(src, MetricCards(src))
    return drawn.nodes, drawn.edges


def family(id, title, names, cards, typed, level=3):
    return (f'<h{level} id="{id}">{escape(title)}</h{level}>\n<div class="shaped">'
            + "".join(cards.card(n, typed.get(n)) for n in names) + "</div>")


def body(page, snap, idx):
    src = MetricSources(snap)
    cards = MetricCards(src)
    typed = formulas(src, cards)
    intro = src.intro()
    figure = MeasurePipeline(src, cards).figure(next(parts.numbers(page.slug)))
    rest = [f'<h2 id="measurement-pipeline">Measurement pipeline</h2>\n{figure}',
            f'<h2 id="columns">Columns</h2>\n{intro}\n'
            + "\n".join(family(id, title, names, cards, typed) for id, title, names in FAMILIES),
            family(*TEST_ORDER, cards, typed, level=2), TableFields(src, map(slug, cards.by_name)).section(),
            column_index(src, cards)]
    return [lead(snap, "\n".join(rest))] + rest
