"""The 29 study pages in reading order, each with its sidebar part and the report headings it takes over."""

from typing import NamedTuple

PARTS = ("Introduction", "Approach", "Methodology", "Results", "Discussion", "Designs", "Reference", "Data")


class Page(NamedTuple):
    slug: str
    title: str
    part: str
    blurb: str
    module: str
    # Report h1 to h3 ids whose sections land on this page. Links resolve through them.
    anchors: tuple = ()

    @property
    def nav(self):
        """Sidebar label: the title without its part prefix."""
        label = self.title.split(": ", 1)[-1]
        return label[:1].upper() + label[1:]


# Showcase design id, report method heading id, design name and showcase lede, in report order.
DESIGNS = (
    ("classic", "classic-greedy-tdd", "Classic greedy TDD", "Smallest failing test then smallest passing change."),
    ("noun-verb", "noun-verb-map", "Noun-verb map",
     "Plan classes from spec nouns and methods from verbs. Fill linked stubs."),
    ("mapped-path", "mapped-path-tdd", "Mapped-path TDD", "Walk the map leaves first toward one acceptance test at a time."),
    ("functions-first", "functions-first-classes-later", "Functions first, classes later",
     "Test-drive pure functions. Cluster them into classes later."),
    ("tpp", "transformation-priority-premise-tdd", "Transformation Priority Premise TDD",
     "Pick tests the simplest ranked transformation can pass."),
    ("coarse-to-fine", "coarse-to-fine-tdd", "Coarse-to-fine TDD", "One big step per feature. Drop a gear when it stalls."),
    ("annealed", "annealed-refactoring", "Annealed refactoring",
     "Uphill refactors allowed early on a fixed cooling schedule."),
    ("multi-start", "multi-start-tdd", "Multi-start TDD", "Independent attempts on one locked suite. Score rule fixed first."),
    ("mutation-guided", "most-informative-next-test", "Most informative next test",
     "Write the test that rules out the most wrong implementations."),
    ("property-based", "property-based-tdd", "Property-based TDD",
     "State rules over input regions. Generators sample and shrink."),
    ("held-out", "held-out-tdd", "Held-out TDD", "Visible tests drive the loop. Hidden tests measure overfitting."),
    ("anchor-engineering", "anchor-engineering", "Anchor Engineering",
     "Write claims that must hold with their checks. Build milestones behind a mutation gate and a judge."),
)

PAGES = (
    Page("", "12 ways to test-drive Kalah", "Introduction",
         "An AI coding agent built the same Java Kalah game with each test-driven design. 6 awards pick the stand-outs.",
         "landing",
         ("kalah-tdd-experiment", "headline", "key-findings", "awards", "methods")),
    Page("experimental-design", "Experimental design and approach", "Approach",
         "The study question, the task, the runs and arms, their caps and where the study sits in the course.",
         "experimental_design", ("study-stage", "course-context")),
    Page("methodology", "Methodology: harness and protocol", "Methodology",
         "How each design runs: stages, prompts and agents, the held-out split, blind review and the audit.", "harness"),
    Page("methodology/measures", "Methodology: measures", "Methodology",
         "Every metric with its formula, inputs and source module.", "measures", ("columns",)),
    Page("methodology/analysis", "Methodology: analysis and validity", "Methodology",
         "Award scoring, the statistical tests and the threats to validity.", "analysis", ("limits",)),
    Page("results/survey", "Results: survey (full-1)", "Results",
         "One build of each design in the survey run full-1.", "results", ("arguments", "survey-full-1")),
    Page("results/contrasts", "Results: planned contrasts", "Results",
         "Planned contrasts over five replicates per arm in runs rep-1 and rep-2.", "results",
         ("planned-contrasts-rep-1", "planned-contrasts-rep-2")),
    Page("results/consistency", "Results: consistency across runs", "Results",
         "How much each design varies between replicate builds.", "results", ("consistency-across-runs",)),
    Page("results/test-order", "Results: test order (tcp-1)", "Results",
         "One candidate test list built in five orders in run tcp-1.", "results", ("test-order",)),
    Page("questions", "Critical questions", "Discussion",
         "The questions the study set out to answer and the status of each answer.", "questions", ("questions",)),
    *(Page(f"designs/{slug}", name, "Designs", blurb, "designs", (heading,)) for slug, heading, name, blurb in DESIGNS),
    Page("designs/a02-reference", "A02 reference (not part of the comparison)", "Designs",
         "The A02 reference build by a human with AI, shown beside the designs and not compared with them.", "designs",
         ("a02-reference-human-ai-not-part-of-the-comparison", "reference")),
    Page("glossary", "Glossary", "Reference", "Every term the study pages use.", "glossary_data",
         ("scope-and-terms", "glossary")),
    Page("data", "Supporting data: findings", "Data", "The findings table and the audit flag dispositions.",
         "glossary_data", ("supporting-data", "findings", "audit-flag-dispositions")),
    Page("data/contrasts", "Supporting data: contrasts and replicates", "Data",
         "Contrast, consistency and replicate tables for rep-1 and rep-2.", "glossary_data",
         ("contrast-table-rep-1", "contrast-table-rep-2", "consistency-table", "replicate-table-rep-1",
          "replicate-table-rep-2")),
    Page("data/methods", "Supporting data: method table", "Data",
         "The method table, with each column linked to its measure.", "glossary_data", ("method-table",)),
    Page("data/ratings", "Supporting data: ratings", "Data", "List reliability and rating agreement for each run.",
         "glossary_data", ("list-reliability", "rating-agreement-full-1", "rating-agreement-rep-1", "rating-agreement-rep-2")),
    Page("data/runs", "Supporting data: run records", "Data", "The run records of full-1, rep-1 and rep-2.",
         "glossary_data", ("run-record-full-1", "run-record-rep-1", "run-record-rep-2")),
)
BY_SLUG = {p.slug: p for p in PAGES}


def neighbours(slug):
    """(previous page, next page) in reading order, None at either end."""
    i = PAGES.index(BY_SLUG[slug])
    return (PAGES[i - 1] if i else None), (PAGES[i + 1] if i + 1 < len(PAGES) else None)


def number(slug):
    """The page's 1-based place in reading order, as in "Part N of 29"."""
    return PAGES.index(BY_SLUG[slug]) + 1
