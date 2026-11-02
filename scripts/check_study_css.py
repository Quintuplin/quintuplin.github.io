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


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    text = re.sub(r"/\*.*?\*/", "", (root / CSS).read_text(encoding="utf-8"), flags=re.S)
    parsed = list(rules(text))
    errors = summary_marker(parsed) + stacked_reset(parsed) + nested_card_reset(parsed)
    for e in errors:
        print("FAIL:", e, file=sys.stderr)
    if not errors:
        print("study css check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
