#!/usr/bin/env python3
"""Static checks on the Kalah TDD study stylesheet (#58). Usage: check_study_css.py [repo root]"""
import re
import sys
from pathlib import Path

CSS = "studies/kalah-tdd-study/study.css"


def rules(text, media=None):
    """Yield (media prelude, selectors, declarations) for each rule, one level of @media deep."""
    i = 0
    while (start := text.find("{", i)) != -1:
        prelude, depth, j = text[i:start].strip(), 1, start + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        body = text[start + 1:j - 1]
        if prelude.startswith("@media"):
            yield from rules(body, prelude)
        elif not prelude.startswith("@"):
            decls = dict(d.split(":", 1) for d in (p.strip() for p in body.split(";")) if ":" in d)
            sels = [s.strip() for s in re.split(r",(?![^()]*\))", prelude)]
            yield media, sels, {k.strip(): v.strip() for k, v in decls.items()}
        i = j


def summary_marker(parsed):
    """A summary laid out as anything but list-item loses its native disclosure marker, so it needs a ::before one."""
    markers = [(specificity(m), i, m, decls["content"]) for i, (media, sels, decls) in enumerate(parsed)
               if media is None and "content" in decls for m in sels if m.endswith("summary::before")]
    errors = []
    for _, sels, decls in parsed:
        for s in sels:
            if re.search(r"summary$", s) and decls.get("display", "list-item") != "list-item":
                # The winning ::before rule that reaches this summary must draw something.
                applies = [(sp, i, c) for sp, i, m, c in markers if m in ("summary::before", f"{s}::before")]
                if not applies or re.sub(r"\s+", "", max(applies)[2]) in ("none", "normal", '""', "''"):
                    errors.append(f"{CSS}: {s} sets display:{decls['display']} and no summary::before marker replaces the native one")
    return errors


def specificity(sel):
    """Selector specificity as (ids, classes, types). :is, :not and :has count their highest argument; :where counts 0."""
    sel, extra = re.sub(r"\[[^\]]*\]", ".a", sel), (0, 0, 0)
    while m := re.search(r":(is|not|has|where)\(([^()]*)\)", sel):
        if m.group(1) != "where":
            extra = tuple(map(sum, zip(extra, max(specificity(a) for a in m.group(2).split(",")))))
        sel = sel[:m.start()] + sel[m.end():]
    ids = sel.count("#")
    classes = len(re.findall(r"\.[\w-]+|(?<!:):[\w-]+", sel))
    types = len(re.findall(r"(?:^|[\s>+~])[a-z][\w-]*|::[\w-]+", sel))
    return tuple(map(sum, zip((ids, classes, types), extra)))


def stacked_reset(parsed):
    """Stacked .qtable and .cols cards at 640px and below must outrank the sticky first column and clear its patch."""
    sticky = [(i, s) for i, (media, sels, decls) in enumerate(parsed) if media is None and decls.get("position") == "sticky"
              for s in sels if re.search(r"\btd\b", s)]
    need = max((specificity(s) for _, s in sticky), default=(0, 0, 0))
    last = max((i for i, _ in sticky), default=-1)
    errors = []
    for card in ("qtable", "cols"):
        # An equal specificity wins only when the reset comes later in the file.
        if not any(re.search(r"max-width:\s*640px", media or "") and decls.get("position") == "static" and "background" in decls
                   and re.search(rf"\.{card}\b", s) and re.search(r"\btd\b", s)
                   and (specificity(s) > need or (specificity(s) == need and i > last))
                   for i, (media, sels, decls) in enumerate(parsed) for s in sels):
            errors.append(f"{CSS}: no stacked .{card} td reset at 640px sets position:static and background "
                          f"with specificity {need} or more, so its first cell stays sticky")
    return errors


def nested_card_reset(parsed):
    """A .qtable card nested with its .table-scroll wrapper, either way round, must drop the inner card border."""
    card = [(i, specificity(s)) for i, (media, sels, decls) in enumerate(parsed) if media is None and "border" in decls
            for s in sels if s in (".qtable", ".table-scroll")]
    need = max((sp for _, sp in card), default=(0, 0, 0))
    last = max((i for i, _ in card), default=-1)
    errors = []
    for outer, inner in (("table-scroll", "qtable"), ("qtable", "table-scroll")):
        if not any(media is None and re.sub(r"\s+", "", decls.get("border", "")) in ("0", "none")
                   and re.fullmatch(rf"\.{outer}(\s+|\s*>\s*)\.{inner}", s)
                   and (specificity(s) > need or (specificity(s) == need and i > last))
                   for i, (media, sels, decls) in enumerate(parsed) for s in sels):
            errors.append(f"{CSS}: no .{outer} .{inner} rule sets border:0 above the card rule's specificity {need}, "
                          f"so the nested card draws a double border")
    return errors


# Flowchart fills and strokes use var() tokens, so High Contrast needs system colours for every class flow.py emits.
# .flow .note outranks .flow text, so it needs its own rule.
FORCED_FLOW = {".flow text": {"fill": "CanvasText"}, ".flow .note": {"fill": "CanvasText"},
               ".flow .head": {"fill": "CanvasText"}, ".flow .node": {"fill": "Canvas", "stroke": "CanvasText"},
               ".flow .edge": {"stroke": "CanvasText"}, ".flow .loop": {"stroke": "CanvasText"},
               ".flow .lane": {"fill": "none", "stroke": "GrayText"}}


def forced_flow(parsed):
    """Each flowchart class keeps a visible system colour under forced colours."""
    return [f"{CSS}: no forced-colors rule sets {sel} {{{prop}:{value}}}, so it may vanish in High Contrast"
            for sel, want in FORCED_FLOW.items() for prop, value in want.items()
            if not any(re.search(r"forced-colors:\s*active", media or "") and sel in sels and decls.get(prop) == value
                       for media, sels, decls in parsed)]


# Navigation controls and figure Data links meet the 44px touch target the rest of the site uses (#60, #79).
# Sidebar rows stay compact in the tall desktop rail and grow on touch or narrow screens, as do the landing contents
# links.
COARSE = "@media (max-width:899.98px), (pointer:coarse)"
TOUCH = ((".toc > summary", None, 44, None), (".toc a", None, 24, 28), (".toc a", COARSE, 44, None),
         (".pager a", None, 44, None), ("details:not(.toc) > summary", None, 44, None), (".fig-foot a", None, 44, None),
         (".contents li > a", COARSE, 44, None))


def px(value):
    """A length in px with rem and em at the 16px default. Any other unit or auto counts as 0, so it fails."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(px|r?em)", value.replace("!important", "").strip())
    return float(m.group(1)) * (1 if m.group(2) == "px" else 16) if m else 0


def same_media(a, b):
    return re.sub(r"\s+", "", a or "") == re.sub(r"\s+", "", b or "")


def coarse(m):
    """Whether every query in media m is one of the COARSE queries, so it only applies where touch rows are allowed."""
    parts = lambda q: set(re.sub(r"\s+", "", q or "").removeprefix("@media").split(","))
    return m is not None and parts(m) <= parts(COARSE)


def reaches(s, sel):
    """Whether selector s styles the same element as sel inside the same container, such as .toc ol ol a for .toc a."""
    head, tail = sel.split()[0], sel.split()[-1]
    # A .toc head also matches #toc and details.toc, but not :not(.toc).
    name = rf"[.#]{re.escape(head[1:])}" if head.startswith(".") else re.escape(head)
    return s == sel or ("::" not in s and re.search(rf"(?<!:not\(){name}(?![\w-])", s) is not None
                        and re.search(rf"[\s>]\s*{re.escape(tail)}(?![\w-])[^\s>+~]*$", s) is not None)


# Methodology table cell links get the touch target where the nav rows do (#64).
CELL_TOUCH = ((".cols td a", COARSE, 44, None),)


def touch_targets(parsed):
    errors = []
    for sel, media, need, cap in TOUCH + CELL_TOUCH:
        meets = [(i, specificity(sel)) for i, (m, sels, decls) in enumerate(parsed)
                 if same_media(m, media) and sel in sels and need <= px(decls.get("min-height", "")) <= (cap or float("inf"))]
        if not meets:
            size = f"between {need}px and {cap}px" if cap else f"of {need}px or more"
            errors.append(f"{CSS}: {sel} has no min-height {size}{' under ' + media if media else ''}, "
                          f"so it is a small touch target{' or a tall desktop row' if cap else ''}")
            continue
        last, spec = max(meets)
        # Any media counts for lowering, as a lowering rule in another query still wins where both apply.
        # A raise counts in any media but the coarse query, which raises the compact rows on purpose.
        for i, (m, sels, decls) in enumerate(parsed):
            value = px(decls.get("min-height", f"{need}px"))
            verb = "lowers" if value < need else "raises" if cap and value > cap and not coarse(m) else None
            errors += [f"{CSS}: later or more specific rule {s} {verb} {sel} min-height to {decls['min-height']}, "
                       f"outside {need}px{f' to {cap}px' if cap else ' or more'}"
                       for s in sels if verb and reaches(s, sel)
                       and (i > last or specificity(s) > spec or "!important" in decls["min-height"])]
    return errors


# Long words wrap so a 320px page never scrolls sideways, while code in table cells keeps short tokens such as a
# doc sha whole and stacked cards keep their caption (#64).
KEPT = (("dl.terms dd", None, "overflow-wrap", "anywhere"),
        (".table-scroll > table.cols :is(th,td)", None, "overflow-wrap", "break-word"),
        (".table-scroll > table.cols code", None, "overflow-wrap", "break-word"),
        (".cols caption", "@media (max-width:640px)", "display", "block"))


def kept_rules(parsed):
    return [f"{CSS}: no rule sets {sel} {{{prop}:{value}}}{' under ' + media if media else ''}"
            for sel, media, prop, value in KEPT
            if not any(same_media(m, media) and sel in sels and decls.get(prop) == value for m, sels, decls in parsed)]


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    text = re.sub(r"/\*.*?\*/", "", (root / CSS).read_text(encoding="utf-8"), flags=re.S)
    parsed = list(rules(text))
    errors = summary_marker(parsed) + stacked_reset(parsed) + nested_card_reset(parsed) + forced_flow(parsed) + \
        touch_targets(parsed) + kept_rules(parsed)
    for e in errors:
        print("FAIL:", e, file=sys.stderr)
    if not errors:
        print("study css check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
