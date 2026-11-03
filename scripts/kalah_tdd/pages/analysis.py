"""The analysis and validity page (#66): award scoring from awards.py, the tests the report used and the threats to
validity, from the report Limits, the run records and the code docstrings in facts.json."""

import re
from html import escape

from .. import links, parts, snapshot

SLUG = "methodology/analysis"
REBUILD, REP = "rep-2/rebuild", "rep-2"
# (facts group, file, function, phrase): a limit the analysis code states in a docstring.
CODE_LIMITS = (("stats", "stats.py", "mann_whitney_exact", "suit small samples only"),
               ("functions", "awards.py", "overall", "A method a criterion leaves out ranks last on it."))
SENTENCE = re.compile(r"(?<=[.?!])\s+(?=[A-Z])")


def section(id, title, *html):
    return f'<section aria-labelledby="{id}"><h2 id="{id}">{escape(title)}</h2>{"".join(html)}</section>'


def p(text, kind=None):
    return f"<p>{text}{' ' + parts.tag(kind) if kind else ''}</p>"


def code(text):
    return f"<code>{escape(str(text))}</code>"


def link(slug, text):
    return f'<a href="{links.url(slug)}">{escape(text)}</a>'


def listed(items):
    """a, b and c."""
    items = list(items)
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def lead():
    return p(f"This page sets out how the study scores its awards, which test answers each question and what the study "
             f"cannot show. It defines no metric. M, E, C and every other measure are defined on "
             f"{link('methodology/measures', 'Methodology: measures')}, and short labels such as CQP and PMD in the "
             f"{link('glossary', 'Glossary')}. The medals are on the {link('', 'landing page')}. The test results are on "
             f"the results pages for the {link('results/survey', 'survey')}, the "
             f"{link('results/contrasts', 'planned contrasts')} and {link('results/consistency', 'consistency')}.")


def rebuild(facts):
    """The rep-2 rebuild: one method rebuilt at a harness commit unlike the rest of rep-2."""
    runs = facts["runs"]
    again, base = runs[REBUILD], runs[REP]
    methods = sorted({m["method"] for m in again["methods"].values()})
    if len(methods) != 1:
        raise ValueError(f"{REBUILD} rebuilt {len(methods)} methods ({', '.join(methods)}); the gap row names one")
    new, old = (r.get("harness", {}).get("commit") for r in (again, base))
    if not new or not old or new == old:
        raise ValueError(f"{REBUILD} needs a harness commit unlike {REP}'s, got {new!r} against {old!r}")
    builds = [b for wave in again["waves"] for b in wave]
    cli = {r["harness"]["claude_version"].split()[0] for r in (again, base)}
    cli = (f"Both record agent CLI {cli.pop()}." if len(cli) == 1 else
           f"They record agent CLI {again['harness']['claude_version'].split()[0]} and "
           f"{base['harness']['claude_version'].split()[0]}.")
    return (f"{REBUILD} rebuilt the {len(builds)} {escape(methods[0])} replicates {listed(builds)} at harness commit "
            f"{code(new[:7])}, where the rest of {REP} records {code(old[:7])}. The rebuild records a harness delta of "
            f"sha256 {code(again['harness_delta']['sha256'][:8])}. {cli}")


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
          "and the code docstrings in the snapshot."),
        limits, '<h3 id="record-gaps">Gaps in the records</h3>',
        p("Each row is derived from facts.json at the snapshot sha, so it changes when the snapshot does."),
        f'<div class="shaped">{"".join(rows)}</div>')


def body(page, snap, idx):
    return [lead(), threats(snap, idx)]
