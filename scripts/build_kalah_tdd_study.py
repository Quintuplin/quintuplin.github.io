"""Build the Kalah TDD study pages under studies/kalah-tdd-study from the committed snapshot.

Usage: build_kalah_tdd_study.py [--check]
--check builds into a temp folder and fails unless every committed page matches byte for byte, as CI runs it.
"""

from __future__ import annotations

import argparse
import filecmp
import sys
import tempfile
from pathlib import Path

# python3 -I leaves the script folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kalah_tdd import chrome, links, pagemap, pages, snapshot  # noqa: E402
from study_checkout import LOCAL_PATH  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "studies/kalah-tdd-study"


def page_path(page):
    return f"{page.slug}/index.html" if page.slug else "index.html"


def render_page(page, snap, idx):
    fragments, stub = pages.body(page, snap, idx)
    return chrome.shell(page, snap, "\n".join(links.unique_ids(fragments, reserved=chrome.IDS)), stub)


def render_pages(snap):
    """{path under OUT: html} for every page, in page map order."""
    idx = links.index(snap)
    return {page_path(p): render_page(p, snap, idx) for p in pagemap.PAGES}


def refuse_host_paths(rendered):
    for path, html in rendered.items():
        if m := LOCAL_PATH.search(html):
            raise SystemExit(f"{path} holds host path text {html[max(0, m.start() - 20):m.end() + 20]!r}")


def existing(out):
    return {p.relative_to(out).as_posix() for p in out.rglob("index.html")}


def write_pages(out, rendered):
    """Writes every page and deletes any index.html the page map no longer has."""
    for stale in existing(out) - rendered.keys():
        (out / stale).unlink()
    for path, html in rendered.items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_bytes(html.encode("utf-8"))


def check_current(out, rendered):
    """Problems with the pages under out against a fresh build, empty when they match byte for byte."""
    with tempfile.TemporaryDirectory() as tmp:
        write_pages(Path(tmp), rendered)
        problems = [f"{p} differs from a fresh build" for p in sorted(rendered.keys() & existing(out))
                    if not filecmp.cmp(Path(tmp) / p, out / p, shallow=False)]
    problems += [f"{p} is missing" for p in sorted(rendered.keys() - existing(out))]
    return problems + [f"{p} is not in the page map" for p in sorted(existing(out) - rendered.keys())]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare the committed pages with a fresh build")
    args = ap.parse_args(argv)
    rendered = render_pages(snapshot.load())
    refuse_host_paths(rendered)
    if not args.check:
        write_pages(OUT, rendered)
        return 0
    problems = check_current(OUT, rendered)
    for p in problems:
        print(f"FAIL: studies/kalah-tdd-study/{p}; run scripts/build_kalah_tdd_study.py", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
