"""The analysis and validity page (#66): award scoring from awards.py, the tests the report used and the threats to
validity, from the report Limits, the run records and the code docstrings in facts.json."""

import re
from html import escape
from typing import NamedTuple

from .. import links, pagemap, parts, snapshot
from ..blocks import plain
from ..figures import flow

SLUG = "methodology/analysis"
MEASURES = "methodology/measures"
REBUILD, REP = "rep-2/rebuild", "rep-2"
# (facts group, file, function, phrase): a limit the analysis code states in a docstring.
CODE_LIMITS = (("stats", "stats.py", "mann_whitney_exact", "suit small samples only"),
               ("functions", "awards.py", "overall", "A method a criterion leaves out ranks last on it."))
SENTENCE = re.compile(r"(?<=[.?!])\s+(?=[A-Z])")
# awards.py criterion to the award it scores; best overall sums the ranks on these.
COUNTED = {"cost_effective": "Most cost effective", "fewest_errors": "Fewest errors", "alignment": "Best CQP/PMD alignment"}
OVERALL, BADGES, LIMITED = "Best overall", ("Cheapest", "Most consistent design"), "Most consistent design"
LIMIT = "{limit}"
NO_FUNCTION = "not stated in the snapshot"
BLOCK = re.compile(r"<(p|li|dd)\b[^>]*>(.*?)</\1>", re.S)


class TestUse(NamedTuple):
    lane: str
    question: str
    data: str
    section: str  # report heading id whose text holds the quoted sentence
    words: tuple  # how the report names the test, each found in that sentence
    functions: tuple  # stats.py functions whose docstrings describe the test; empty when facts name none
    correction: str
    reported: str  # page slug


TEST_USE = (
    TestUse("Survey scores", "Do mutation scores differ between the survey methods?", "full-1 mutation scores of 11 methods",
            "survey-full-1", ("seeded permutation chi-square", "Fisher exact tests with Holm correction"),
            ("permutation_chi2", "fisher_pairs", "holm"), "Holm over every pair of methods", "results/survey"),
    TestUse("Score intervals", "How precise is each method's mutation score?", "full-1 killed and compiled mutants per method",
            "survey-full-1", ("Wilson 95% interval",), ("wilson",), "None, descriptive only", "results/survey"),
    TestUse("Clean classes", "Do clean methods have more classes?", "full-1 classes per method, start clones left out",
            "survey-full-1", ("exact one-sided permutation test",), (), "None, one test", "results/survey"),
    TestUse("Planned contrasts", "Does one replicated arm differ from another?", "rep-1 and rep-2 replicates, 5 per arm",
            "contrast-table-rep-1", ("exact two-sided Mann-Whitney U", "Holm correction"), ("mann_whitney_exact", "holm"),
            "Holm over the planned pairs of each outcome", "results/contrasts"),
    TestUse("Consistency", "Does one design vary more between builds?", "rep-1 and rep-2 replicates pooled per method",
            "questions", ("Brown-Forsythe permutation tests", "Holm p"), ("brown_forsythe_permutation", "holm"),
            "Holm over the metrics", "results/consistency"),
    TestUse("Rater agreement", "Do the three raters agree?", "full-1, rep-1 and rep-2 blind ratings",
            "rating-agreement-full-1", ("Krippendorff's ordinal alpha", "seeded bootstrap 95% interval"), (), "None",
            "data/ratings"),
    TestUse("Ratings and code", "Do the ratings track lines of code and PMD?", "finals medians against LOC and PMD violations",
            "rating-agreement-full-1", ("Spearman correlations", "Holm-adjusted q"), ("spearman_trial", "holm"),
            "Holm over the correlations", "data/ratings"),
    TestUse("List reliability", "Do two listers agree on the test list?", "tcp-1-list clauses and candidates rated again",
            "list-reliability", ("linearly weighted kappa", "Spearman rho with a seeded bootstrap 95% interval",
                                 "mean Jaccard overlap"), ("weighted_kappa", "spearman_trial", "jaccard"), "None",
            "data/ratings"),
)


def section(id, title, *html):
    return f'<section aria-labelledby="{id}"><h2 id="{id}">{escape(title)}</h2>{"".join(html)}</section>'


def p(text, kind=None):
    return f"<p>{text}{' ' + parts.tag(kind) if kind else ''}</p>"


def code(text):
    return f"<code>{escape(str(text))}</code>"


def link(slug, text, frag=""):
    return f'<a href="{links.url(slug, frag)}">{escape(text)}</a>'


def listed(items):
    """a, b and c."""
    items = list(items)
    return "" if not items else items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def lead():
    return p(f"This page sets out how the study scores its awards, which test answers each question and what the study "
             f"cannot show. It defines no metric. {link(MEASURES, 'M', 'm')}, {link(MEASURES, 'E', 'e')}, "
             f"{link(MEASURES, 'C', 'consistency-score-c')} and every other measure are defined on "
             f"{link(MEASURES, 'Methodology: measures')}, and short labels such as CQP and PMD in the "
             f"{link('glossary', 'Glossary')}. The test results are on the results pages for the "
             f"{link('results/survey', 'survey')}, the {link('results/contrasts', 'planned contrasts')} and "
             f"{link('results/consistency', 'consistency')}.") + p(f"The medals are on the {link('', 'landing page')}.",
                                                                   "unchecked")


def grid(caption, head, rows):
    """A captioned table that stacks into labelled cells on a narrow screen. Cells are HTML."""
    th = "".join(f'<th scope="col">{escape(h)}</th>' for h in head)
    body = "".join("<tr>" + "".join(f'<td data-th="{escape(h)}">{c}</td>' for h, c in zip(head, r)) + "</tr>" for r in rows)
    return parts.table(f'<table class="cols"><caption>{escape(caption)}</caption><thead><tr>{th}</tr></thead>'
                       f"<tbody>{body}</tbody></table>", caption)


def rules(facts):
    """(title, rule without its limit placeholder, counts toward best overall) per award in order. Refuses a criterion
    or award this page cannot place, and a limit placeholder anywhere but the consistency award."""
    a = facts["analysis"]
    for c in a["criteria"]:
        if c["name"] not in COUNTED:
            raise ValueError(f"awards.py criterion {c['name']!r} scores no award this page knows")
    titles = [w["title"] for w in a["awards"]]
    for t in titles:
        if t not in (OVERALL, *COUNTED.values(), *BADGES):
            raise ValueError(f"award {t!r} is not one this page places")
    for name in {c["name"] for c in a["criteria"]}:
        if COUNTED[name] not in titles:
            raise ValueError(f"awards.py criterion {name!r} scores {COUNTED[name]!r}, which the award list lacks")
    if missing := [t for t in (OVERALL, *BADGES) if t not in titles]:
        raise ValueError(f"the award list lacks {', '.join(map(repr, missing))}, which this page places")
    out = []
    for w in a["awards"]:
        if (LIMIT in w["rule"]) != (w["title"] == LIMITED):
            raise ValueError(f"award {w['title']!r} {'carries' if LIMIT in w['rule'] else 'lacks'} the {LIMIT} placeholder")
        out.append((w["title"], w["rule"].replace(LIMIT, "").strip(), w["title"] in COUNTED.values()))
    return out


def counts_cell(title, counts):
    return "Yes" if counts else "Is the rank sum" if title == OVERALL else "No"


def award_scoring(snap, numbers):
    a = snap.facts["analysis"]
    found, k = rules(snap.facts), a["constants"]
    names = [c["name"] for c in a["criteria"]]
    badges = [t for t, _, counts in found if not counts and t != OVERALL]
    table = grid("Award rules", ["Award", "Rule", "Counts toward best overall"],
                 [[escape(t), escape(r), counts_cell(t, c)] for t, r, c in found])
    return section(
        "award-scoring", "Award scoring",
        p(f"Each award but {escape(OVERALL.lower())} places the methods on one value, lower first. {code('places')} gives competition places, ties "
          f"sharing the best place. {code('podium')} keeps the places up to TOP = {k['TOP']} and {code('award')} gives "
          f"them the medals {escape(listed(k['MEDALS']))}. {escape(OVERALL)} ranks every method on the {len(names)} "
          f"CRITERIA {listed(map(code, names))} with {code('stats.ranks')}, ties sharing their average rank, and sums "
          f"the ranks. {escape(listed(badges))} are bronze badges that never count toward it. Checked against awards.py "
          f"at tdd-experiment {code(snap.sha[:7])}.", "verified"),
        awards_figure(snap, next(numbers)),
        '<h3 id="award-rules">Award rules</h3>',
        p("Each rule is quoted from awards.py.", "verified"),
        p("Counts toward best overall marks the awards whose criterion joins the rank sum, by the criterion to award "
          "mapping in the Award column below.", "unchecked"),
        table,
        p(f"The {escape(LIMITED)} rule carries a consistency limit, which the {link('', 'landing page')} states with "
          f"the award.", "unchecked"),
        '<h3 id="awards-code">awards.py functions and constants</h3>',
        p("Criterion names and returns, docstrings and constants are quoted verbatim from awards.py at the snapshot "
          "sha.", "verified"),
        p("The Award column is this page's mapping of each criterion to the award it scores. awards.py does not state "
          "it.", "unchecked"),
        grid("awards.py criteria", ["Criterion", "Award", "Returns"],
             [[code(c["name"]), escape(COUNTED[c["name"]]), code(c["returns"])] for c in a["criteria"]]),
        grid("awards.py functions", ["Function", "Docstring"],
             [[code(f["name"]), escape(f["doc"] or "No docstring in awards.py.")] for f in a["functions"]]),
        grid("awards.py constants", ["Constant", "Value"],
             [[code(n), escape(", ".join(v) if isinstance(v, list) else str(v))] for n, v in k.items()]))


def awards_flow(snap):
    """F6 in three lanes, every route inside one lane, straight down one column or one elbow through an empty gap."""
    a = snap.facts["analysis"]
    k, names = a["constants"], [c["name"] for c in a["criteria"]]
    top = f"top {k['TOP']}: {', '.join(k['MEDALS'])}"
    lanes = ("Criteria", OVERALL, "Badges")
    nodes = [flow.node("records", "Method records", lanes[0], 0, "one per method"),
             flow.node("criteria", "CRITERIA", lanes[0], 1, ", ".join(names)),
             flow.node("places", "places", lanes[0], 2, "per criterion, lower first"),
             flow.node("podium", "podium", lanes[0], 3, top),
             flow.node("ranks", "stats.ranks", lanes[1], 1, "ties share their average rank"),
             flow.node("overall", "overall", lanes[1], 2, "rank sum over CRITERIA"),
             flow.node("best", "places and podium", lanes[1], 3, top),
             flow.node("badge-in", "Cost to completion, C", lanes[2], 1, "never ranked in CRITERIA"),
             flow.node("badge-places", "places", lanes[2], 2, "lower first"),
             flow.node("bronze", "Bronze badge only", lanes[2], 3, "limit stated with the award")]
    edges = [flow.edge("records", "criteria"), flow.edge("criteria", "places"), flow.edge("places", "podium"),
             flow.edge("criteria", "ranks"), flow.edge("ranks", "overall"), flow.edge("overall", "best"),
             flow.edge("records", "badge-in"), flow.edge("badge-in", "badge-places"), flow.edge("badge-places", "bronze")]
    return nodes, edges, []


def awards_figure(snap, n):
    nodes, edges, loops = awards_flow(snap)
    title = "How awards are scored"
    desc = ("Three lanes. Criteria: method records are scored on each criterion, placed lower first and given a podium "
            "of medals. Best overall: the criterion values are ranked, summed and placed. Badges: cost to completion "
            "and consistency score C are placed for a bronze badge only.")
    return parts.figure(n, "award-flow", title, flow.svg("f6", title, desc, nodes, edges, loops),
                        f"Each award but {escape(OVERALL.lower())} places methods on one value. Only the "
                        f"{len(snap.facts['analysis']['criteria'])} criteria feed the {escape(OVERALL.lower())} rank "
                        f"sum. {parts.tag('verified')}",
                        "#award-rules", flow.text_version(title, nodes, edges, loops))


def sentence(snap, use):
    """The first sentence of the use's report section that holds all its test words, as plain text."""
    text = snapshot.section(snap.files[snapshot.REPORT], use.section)
    for m in BLOCK.finditer(text):
        for s in SENTENCE.split(plain(m.group(2), "")):
            if all(w in s for w in use.words):
                return s
    raise ValueError(f"report section {use.section} has no sentence with {' and '.join(map(repr, use.words))}")


def statistical_tests(snap, numbers):
    stats = snap.facts["analysis"]["stats"]
    names = {f["name"] for f in stats}
    for use in TEST_USE:
        if missing := set(use.functions) - names:
            raise ValueError(f"{use.lane} names {', '.join(sorted(missing))}, which stats.py lacks")
    rows = [[escape(u.question), escape(u.data), escape("; ".join(u.words)), escape(", ".join(u.functions) or NO_FUNCTION),
             escape(u.correction), escape(pagemap.BY_SLUG[u.reported].title), escape(sentence(snap, u))] for u in TEST_USE]
    return section(
        "statistical-tests", "Statistical tests",
        p("Each row of the table names a question the study asks, the data it uses, the test as the report names it and "
          "the stats.py functions whose docstrings describe that test. The source sentence is quoted from the report "
          "section that reports the test.", "verified"),
        p("Functions are matched to tests by docstring. The snapshot does not record which function computed each "
          "reported number.", "unchecked"),
        test_figure(snap, next(numbers)),
        '<h3 id="test-use">Where each test is used</h3>',
        grid("Where each test is used", ["Question", "Data", "Test", "Function", "Correction", "Reported in", "Source sentence"],
             rows),
        '<h3 id="stats-functions">stats.py functions</h3>',
        p("Docstrings are quoted verbatim from stats.py at the snapshot sha.", "verified"),
        grid("stats.py functions", ["Function", "Docstring"],
             [[code(f["name"]), escape(f["doc"] or "No docstring in stats.py.")] for f in stats]))


def test_flow(snap):
    """F7: one lane per test with a stats.py function, from question to function, correction and the page reporting it."""
    nodes, edges = [], []
    for k, u in enumerate(u for u in TEST_USE if u.functions):
        ids = [f"q{k}", f"fn{k}", f"fix{k}", f"at{k}"]
        labels = [u.question, listed(u.functions), u.correction, pagemap.BY_SLUG[u.reported].nav]
        nodes += [flow.node(i, label, u.lane, col) for col, (i, label) in enumerate(zip(ids, labels))]
        edges += [flow.edge(a, b) for a, b in zip(ids, ids[1:])]
    return nodes, edges, []


def test_figure(snap, n):
    nodes, edges, loops = test_flow(snap)
    title = "Which test answers each question"
    desc = (f"{len({x.lane for x in nodes})} lanes, one per question. Each runs from the question to the stats.py "
            f"functions, the multiple-test correction and the page that reports the result.")
    left = listed(u.lane for u in TEST_USE if not u.functions)
    left = (f" {escape(left)} name no stats.py function in the snapshot, so only the table lists them. "
            f"{parts.tag('unchecked')}" if left else "")
    return parts.figure(n, "test-flow", title, flow.svg("f7", title, desc, nodes, edges, loops),
                        f"Connections show the next step in each lane.{left}", "#test-use", flow.text_version(title, nodes, edges, loops))


def rebuild(facts):
    """The rep-2 rebuild: one method rebuilt at a harness commit unlike the rest of rep-2."""
    runs = facts["runs"]
    if REBUILD not in runs or REP not in runs:
        raise ValueError(f"{REBUILD} needs the {REBUILD} and {REP} run records")
    again, base = runs[REBUILD], runs[REP]
    builds = [b for wave in again.get("waves", []) for b in wave]
    delta = (again.get("harness_delta") or {}).get("sha256")
    for field, value in (("methods", again.get("methods")), ("builds in its waves", builds), ("harness_delta.sha256", delta)):
        if not value:
            raise ValueError(f"{REBUILD} records no {field}")
    methods = sorted({m["method"] for m in again["methods"].values()})
    if len(methods) != 1:
        raise ValueError(f"{REBUILD} rebuilt {len(methods)} methods ({', '.join(methods)}); the gap row names one")
    new, old = (r.get("harness", {}).get("commit") for r in (again, base))
    if not new or not old or new == old:
        raise ValueError(f"{REBUILD} needs a harness commit unlike {REP}'s, got {new!r} against {old!r}")
    new_cli, old_cli = ((r["harness"].get("claude_version") or "").split()[:1] for r in (again, base))
    if not new_cli or not old_cli:
        raise ValueError(f"{REBUILD} and {REP} each need a harness claude_version")
    cli = (f"Both record agent CLI {new_cli[0]}." if new_cli == old_cli else
           f"They record agent CLI {new_cli[0]} and {old_cli[0]}.")
    return (f"{REBUILD} rebuilt the {len(builds)} {escape(methods[0])} replicates {listed(builds)} at harness commit "
            f"{code(new[:7])}, where the rest of {REP} records {code(old[:7])}. The rebuild records a harness delta of "
            f"sha256 {code(delta[:8])}. {cli}")


def docs(snap):
    """Each methods doc version by short sha256 with the runs built under it, the quoted one marked."""
    groups = {}
    for run in snap.facts["runs"]:
        groups.setdefault(snapshot.run_doc(snap, run), []).append(run)
    marked = lambda sha: f"{sha}, the methods text these pages quote" if sha == snap.doc else sha
    return ("Each run records the sha256 of the methods doc it was built under, shown here by its first 8 characters. " +
            " ".join(f"{marked(sha)}: {listed(runs)}." for sha, runs in groups.items()))


def harness(facts):
    none = [r for r, v in facts["runs"].items() if not v.get("harness", {}).get("commit")]
    if not none:
        return "Every run records a harness commit in args.json."
    return (f"{len(none)} of {len(facts['runs'])} runs record no harness commit in args.json: {listed(none)}. "
            f"The harness version they ran is not on record.")


def code_limits(facts):
    """Each docstring sentence that states a limit, quoted; a lost sentence is refused by function name."""
    out = []
    for group, file, name, phrase in CODE_LIMITS:
        doc = next((f["doc"] for f in facts["analysis"][group] if f["name"] == name), None) or ""
        found = [s for s in SENTENCE.split(doc) if phrase in s]
        if not found:
            raise ValueError(f"{file} {name} docstring no longer states {phrase!r}")
        out.append(f"{escape(file)} {code(name)}: “{escape(found[0])}”")
    return f"Docstrings state {len(out)} limits of the analysis code. " + " ".join(out)


def gap(id, text):
    return f'<div class="entry" id="{id}"><p>{text}</p><p class="sub">{parts.tag("recomputed")}</p></div>'


def threats(snap, idx):
    f = snap.facts
    limits = links.rewrite(snapshot.section(snap.files[snapshot.REPORT], "limits"), snapshot.REPORT, SLUG, idx)
    rows = [gap("gap-rebuild", rebuild(f)), gap("gap-docs", escape(docs(snap))), gap("gap-harness", escape(harness(f))),
            gap("gap-code-limits", code_limits(f))]
    return section(
        "threats", "Threats to validity",
        p("The report states its limits once, kept here word for word. The gaps after them come from the run records "
          "and the code docstrings in the snapshot.", "verified"),
        limits,
        p("The overall rank sum is descriptive. Alignment uses all eight principles, including those with low or "
          "unestimable agreement. E is an additive composite count and does not count unique defects.", "verified"),
        p("M = T × (1 − APFDc-H) is a trapezoidal estimate over recorded checkpoints. Checkpoint spacing can miss "
          "changes between observations. M_io recomputes the curve without output tokens as a sensitivity check. "
          "It does not establish comparability across CLI versions. C pools costs without correcting those differences.", "verified"),
        '<h3 id="record-gaps">Gaps in the records</h3>',
        p("Each row is derived from facts.json at the snapshot sha, so it changes when the snapshot does.", "recomputed"),
        f'<div class="shaped">{"".join(rows)}</div>')


def body(page, snap, idx):
    numbers = parts.numbers(page.slug)
    return [lead(), award_scoring(snap, numbers), statistical_tests(snap, numbers), threats(snap, idx)]
