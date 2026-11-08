"""Page bodies. A page whose module is in this package is built by its body(page, snap, idx), which returns the
page's fragments in order; any other is a stub."""

import importlib
import importlib.util
import re
from html import escape

from .. import pagemap
from ..blocks import plain

# Exact narrative corrections from the whole-study evidence review. Counts are per rendered page.
REVIEWED = (
    ({"": 1, "glossary": 1}, "The mean weighted-token cost to pass one hidden test. Lower is better.",
     "The trapezoidal checkpoint-area estimate of weighted-token cost per hidden test. Lower is better."),
    ({"": 1, "glossary": 1}, "M with output tokens left out.",
     "A sensitivity check that recomputes M without output-token costs."),
    ({"": 1, "glossary": 1}, "The mutation score after dropping surviving mutants the hidden tests also miss, which are likely equivalent. Higher is better.",
     "Surviving mutants missed by the hidden suite are excluded. They may be equivalent or expose gaps in that suite. Higher is better."),
    ({"methodology/measures": 1}, "Survivors the hidden suite also misses are likely equivalent and left out.",
     "Survivors missed by the hidden suite are excluded. They may be equivalent or expose gaps in that suite."),
    ({"glossary": 1}, "It is likely equivalent to the original code or a gap in the hidden suite.",
     "It may be equivalent or expose a gap in the hidden suite."),
    ({"results/survey": 1}, "The adjusted score drops the survivors the hidden suite also passes, likely equivalent mutants or gaps in the hidden suite.",
     "Surviving mutants missed by the hidden suite are excluded. They may be equivalent or expose gaps in that suite."),
    ({"questions": 1}, "The hidden suite also passes 77 of the 164 surviving mutants, so those are likely equivalent mutants or gaps in the hidden suite.",
     "The hidden suite also passes 77 of the 164 surviving mutants. They may be equivalent or expose gaps in that suite."),
    ({"glossary": 1}, "M is the mean weighted-token cost to pass a hidden test, the cost to completion times 1 minus APFDc-H.",
     "M is a trapezoidal checkpoint-area estimate of weighted-token cost per hidden test: the cost to completion times 1 minus APFDc-H."),
    ({"methodology/measures": 1}, "Mean weighted-token cost to pass a hidden test: the cost to completion times 1 minus APFDc-H, the area above the hidden-suite pass share. A lower M costs less.",
     "Trapezoidal checkpoint-area estimate of weighted-token cost per hidden test: the cost to completion times 1 minus APFDc-H. Lower M costs less."),
    ({"glossary": 1}, "M_io is M with output tokens left out of every cost, so it compares across CLI builds whose output per request differs.",
     "M_io recomputes the curve with output tokens excluded. It is a sensitivity check and does not establish comparability across CLI builds."),
    ({"methodology/measures": 1}, "M with output tokens left out of every cost, so it compares across CLI builds whose output per request differs.",
     "M_io recomputes the curve without output tokens as a sensitivity check. This does not establish comparability across CLI builds."),
    ({"glossary": 1}, "A method's relative spread on one metric is the mean absolute deviation of its replicates from their median over the mean of that deviation across the replicated methods off the metric's bound.",
     "A method's relative spread divides its mean absolute deviation from its own median by the pooled mean absolute deviation across eligible builds off the metric's bound. The pooled reference weights builds, so unequal replicate counts contribute unequally."),
    ({"methodology/measures": 1}, "A method's mean absolute deviation from its own median over the mean deviation of the replicated methods off the metric's bound. 1 is the average.",
     "A method's mean absolute deviation from its own median divided by the pooled mean absolute deviation across eligible builds off the metric's bound. 1 is the pooled reference spread. The reference weights builds, including unequal replicate counts."),
    ({"results/consistency": 1}, "a method's mean absolute deviation from its own median over the mean deviation of the methods off the metric's bound",
     "a method's mean absolute deviation from its own median divided by the pooled mean absolute deviation across eligible builds"),
    ({"results/consistency": 1}, "Lower is more consistent.", "Lower C means less observed spread on this composite."),
    ({"questions": 1}, "The analogy holds for the climb and no variant reached a better end point. All 10 variants and Classic greedy TDD reached the same functional end point of 15/15 with 76/76 hidden and 69/69 unseen tests. No LOG.md row of the 14 full-1 clones lowered the hidden pass count, so no method stepped back.",
     "The 10 variants and Classic greedy TDD reached the same functional score in these survey builds: 15/15 with 76/76 hidden and 69/69 unseen tests. Cost, PMD and mutation results differed. No recorded LOG.md checkpoint reduced the hidden-pass count."),
    ({"questions": 1}, "The A02 reference at commit 2ed6c36 passes 76/76 hidden tests with 69/69 unseen and 7/7 seen.",
     "The A02 reference at commit 2ed6c36 passes 76/76 hidden tests with 69/69 unseen and 7/7 seen. This checks compatibility with the reference. It does not establish that every grading failure represents a real defect."),
    ({"questions": 1}, ", which ties that gap to the method for this task, model and batch.",
     ". The planned contrast detected this adjusted mutation difference for this task, model and batch."),
    ({"questions": 1}, "Functions first, classes later and Noun-verb map did not differ, Holm p 0.548.",
     "The test did not detect a difference between Functions first, classes later and Noun-verb map (Holm p 0.548)."),
    ({"questions": 1}, "No leader differed from Classic greedy TDD on M, Holm p 1.000 for all three.",
     "The tests did not detect a difference from Classic greedy TDD on M (Holm p 1.000 for all three)."),
    ({"": 1}, "Functions first, classes later and Noun-verb map did not differ, with Holm p 0.548.",
     "The test did not detect a difference between Functions first, classes later and Noun-verb map (Holm p 0.548)."),
    ({"": 1}, "In rep-2 no survey leader differed from Classic greedy TDD on M, and Held-out TDD scored a lower adjusted mutation score with Holm p 0.024.",
     "In rep-2 the M tests did not detect a difference from Classic greedy TDD. Held-out TDD scored lower on adjusted mutation (Holm p 0.024) in this task and batch."),
    ({"questions": 1}, "Whether to adopt it as an arm is open.",
     "These limits define what the constructed agent-only arm represents."),
    ({"questions": 1}, "With so few replicates no method is shown more consistent than another.",
     "The global spread test did not detect a difference."),
    ({"questions": 1}, "Consistency score C, where lower is more consistent,",
     "Consistency score C, where lower means less observed spread,"),
    ({"designs/noun-verb": 1}, "Its consistency score C of 1.65 was the highest of the seven replicated methods, so its builds varied most, an exploratory result.",
     "Its observed consistency score C of 1.65 was the highest among the seven replicated methods. This exploratory test did not detect a difference in spread."),
    ({"designs/mutation-guided": 1}, "Their consistency score C of 0.38 was the lowest of the seven replicated methods, an exploratory result.",
     "Their observed consistency score C of 0.38 was the lowest among seven replicated methods. The exploratory test did not detect a difference in spread."),
    ({"designs/noun-verb": 1}, "Its replicates' median adjusted mutation of 0.964 did not differ from Functions first, classes later, Holm p 0.548.",
     "Its replicates' median adjusted mutation was 0.964. The test against Functions first, classes later did not detect a difference (Holm p 0.548)."),
    ({"designs/functions-first": 1}, "Its replicates' median adjusted mutation of 0.927 did not differ from Noun-verb map's 0.964, Holm p 0.548.",
     "Its replicates' median adjusted mutation was 0.927 against Noun-verb map's 0.964. The test did not detect a difference (Holm p 0.548)."),
    ({"designs/coarse-to-fine": 1}, "Its 5 rep-2 replicates did not differ from Classic greedy TDD on M, U 9 and Holm p 1.000, and passed",
     "The M test of its 5 rep-2 replicates against Classic greedy TDD did not detect a difference (U 9 and Holm p 1.000). The replicates passed"),
    ({"designs/mutation-guided": 1}, "Its 5 rep-2 replicates did not differ from Classic greedy TDD on M, U 17 and Holm p 1.000, with a median M of 735111.",
     "The M test of its 5 rep-2 replicates against Classic greedy TDD did not detect a difference (U 17 and Holm p 1.000). Their median M was 735111."),
    ({"designs/held-out": 1}, "The replicates did not differ from Classic greedy TDD on M, U 11 and Holm p 1.000, and their median share",
     "The M test did not detect a difference from Classic greedy TDD (U 11 and Holm p 1.000). The replicates' median share"),
    ({"experimental-design": 1}, "Mutation score is a test criterion stronger than the lecture's branch coverage example.",
     "Mutation score adds a fault-based check alongside the course's coverage example."),
    ({f"designs/{slug}": 1 for slug, *_ in pagemap.DESIGNS}, "The steps the agent followed, in order.",
     "The procedure supplied to the agents."),
)
NARRATIVE = re.compile(r"<(pre|code|table|svg)\b.*?</\1>|<(?:p|dd)\b[^>]*>.*?</(?:p|dd)>", re.S)
QUOTED = ("The glossary row ", "The report section ", "Function ", "List phase step ", "Each method page ", "Actions:")


def narrative(html, old, new):
    """Replace one exact narrative claim while preserving source quotes and structural content."""
    count = 0
    def replace(m):
        nonlocal count
        block = m.group()
        if m.group(1) or "<code" in block or plain(block, " ").startswith(QUOTED):
            return block
        chunks = re.split(r"(<[^>]+>)", block)
        for i in range(0, len(chunks), 2):
            target = old if old in chunks[i] else escape(old)
            count += chunks[i].count(target)
            chunks[i] = chunks[i].replace(target, new if target == old else escape(new))
        return "".join(chunks)
    return NARRATIVE.sub(replace, html), count


def reviewed(slug, html, strict=True):
    for expected, old, new in REVIEWED:
        if slug in expected:
            html, count = narrative(html, old, new)
            if strict and count != expected[slug]:
                raise ValueError(f"{slug}: reviewed narrative {old[:70]!r} matched {count}, expected {expected[slug]}")
    return html


def built(page):
    """The page's module, or None while the page is a stub."""
    name = f"{__name__}.{page.module}"
    return importlib.import_module(name) if importlib.util.find_spec(name) else None


def stub():
    """The header above already shows the title and blurb."""
    return ('<div class="callout">\n<p class="eyebrow">In progress</p>\n<p>This part is being written. '
            'Use the contents to reach the parts already published.</p>\n</div>')


def body(page, snap, idx):
    """(main body fragments, is a stub). Each fragment keeps its own id references when unique_ids renames."""
    module = built(page)
    return (reviewed(page.slug, "\0".join(module.body(page, snap, idx))).split("\0"), False) if module else ([stub()], True)
