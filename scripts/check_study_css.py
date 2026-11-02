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
            yield media, [s.strip() for s in prelude.split(",")], {k.strip(): v.strip() for k, v in decls.items()}
        i = j


def summary_marker(parsed):
    """A summary laid out as anything but list-item loses its native disclosure marker, so it needs a ::before one."""
    flat = [s for _, sels, decls in parsed for s in sels if "content" in decls]
    has_marker = any(re.search(r"summary::before$", s) for s in flat)
    errors = []
    for _, sels, decls in parsed:
        for s in sels:
            if re.search(r"summary$", s) and decls.get("display", "list-item") != "list-item" and not has_marker:
                errors.append(f"{CSS}: {s} sets display:{decls['display']} and no summary::before marker replaces the native one")
    return errors


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    text = re.sub(r"/\*.*?\*/", "", (root / CSS).read_text(encoding="utf-8"), flags=re.S)
    errors = summary_marker(list(rules(text)))
    for e in errors:
        print("FAIL:", e, file=sys.stderr)
    if not errors:
        print("study css check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
