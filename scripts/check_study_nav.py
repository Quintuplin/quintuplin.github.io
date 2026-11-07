#!/usr/bin/env python3
"""Check study page navigation (#60): sidebar links, links between study pages with their fragments, and unique ids.
It reads the source studies folder, which check_site.sh shows the built site serves byte for byte.

Usage: check_study_nav.py [repo root]
"""
import functools
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

STUDIES = "/studies/"


class Page(HTMLParser):
    """A page's ids, and each link as (href, in the sidebar, aria-current page). The sidebar is the first element of class toc.
    A stub page carries the kalah-tdd-stub meta until its page group builds it."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.has_toc, self.toc, self.stub = [], [], False, None, False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stub = self.stub or (tag == "meta" and a.get("name") == "kalah-tdd-stub")
        if self.toc and tag == self.toc[0]:
            self.toc[1] += 1
        elif not self.has_toc and "toc" in (a.get("class") or "").split():
            self.has_toc, self.toc = True, [tag, 1]
        if a.get("id") is not None:
            self.ids.append(a["id"])
        if tag == "a" and a.get("href") is not None:
            self.links.append((a["href"], self.toc is not None, a.get("aria-current") == "page"))

    def handle_endtag(self, tag):
        if self.toc and tag == self.toc[0]:
            self.toc[1] -= 1
            self.toc = self.toc if self.toc[1] else None


@functools.cache
def parse(html):
    return Page(html)


def load(root, suffix=".html"):
    """Map each URL under /studies/ to its page text, or to None for a file that is not a page."""
    root, out = Path(root), {}
    for f in sorted((root / "studies").rglob("*")):
        if f.is_file():
            url = "/" + f.relative_to(root).as_posix()
            if f.suffix == suffix:
                out[url.removesuffix("index" + suffix)] = f.read_text(encoding="utf-8")
            else:
                out[url] = None
    return out


def target(pages, here, href):
    """The (study URL, fragment) a link reaches, or None when it leaves the studies."""
    parts = urlsplit(urljoin(here, href))
    if parts.scheme or parts.netloc or not parts.path.startswith(STUDIES):
        return None
    path = parts.path.removesuffix("index.html")
    path = path + "/" if path + "/" in pages else path
    return path, unquote(parts.fragment)


def broken(pages, here, href):
    if not (t := target(pages, here, href)):
        return None
    path, frag = t
    if path not in pages:
        return f"{here} links {href} but no study page or file {path} exists"
    ids = set(parse(pages[path]).ids) if pages[path] else set()
    # A stub gains its ids when built, and check_kalah_tdd_study --final rejects every stub.
    if frag and frag not in ids and not (pages[path] and parse(pages[path]).stub):
        # The generator suffixes an id that collides on its page, so name the renamed id.
        renamed = sorted(i for i in ids if re.fullmatch(re.escape(frag) + r"-\d+", i))
        hint = f" (renamed to {', '.join(renamed)}?)" if renamed else ""
        return f"{here} links {path}#{frag} but that page has no id {frag}{hint}"
    return None


def html_pages(pages):
    return ((url, parse(html)) for url, html in pages.items() if html is not None)


def toc_links(pages):
    """Every sidebar link resolves, and a sidebar that links other pages marks exactly its own page as current."""
    with_toc = {url.split("/")[2] for url, page in html_pages(pages) if page.has_toc}
    errors = []
    for here, page in html_pages(pages):
        if not page.has_toc:
            if here.split("/")[2] in with_toc:
                errors.append(f"{here} has no sidebar but other pages of its study do")
            continue
        toc = [(href, current) for href, in_toc, current in page.links if in_toc]
        errors += filter(None, (broken(pages, here, href) for href, _ in toc))
        marked = [target(pages, here, href) for href, current in toc if current]
        others = any((t := target(pages, here, href)) and t[0] != here for href, _ in toc)
        if (marked or others) and marked != [(here, "")]:
            errors.append(f"{here} sidebar marks {len(marked)} links aria-current but must mark only its own page")
    return errors


def cross_links(pages):
    """Every link outside the sidebar that stays in the studies reaches an existing page or file and fragment."""
    return [e for here, page in html_pages(pages) for href, in_toc, _ in page.links
            if not in_toc and (e := broken(pages, here, href))]


def unique_ids(pages):
    return [f"{url} has id {i} {n} times" for url, page in html_pages(pages) for i, n in Counter(page.ids).items() if n > 1]


def check(root):
    pages = load(root)
    return toc_links(pages) + cross_links(pages) + unique_ids(pages)


if __name__ == "__main__":
    errors = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1 if errors else 0)
