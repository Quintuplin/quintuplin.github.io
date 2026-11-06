"""Report HTML cut into top-level blocks, shared by the study pages (#112)."""

import re
from html import unescape

OPEN = re.compile(r"\s*<([a-z][a-z0-9]*)\b([^>]*)>")


def close(html, tag, at):
    """The end of the element whose start tag ends at at, counting nested elements of the same tag."""
    depth = 1
    for m in re.compile(rf"<(/?){tag}\b[^>]*>").finditer(html, at):
        depth += -1 if m.group(1) else 1
        if not depth:
            return m.end()
    return -1


def elements(id, html):
    """(tag, attrs, block) of each top-level element in order. Refuses text outside them."""
    at, out = 0, []
    while html[at:].strip():
        m = OPEN.match(html, at)
        end = close(html, m.group(1), m.end()) if m else -1
        if end == -1:
            raise ValueError(f"section {id} holds an unrecognised block {html[at:].strip()[:60]!r}")
        out.append((m.group(1), m.group(2), html[at:end].strip()))
        at = end
    return out


def plain(html, sep):
    """The text of html with each tag replaced by sep, unescaped and with whitespace collapsed."""
    return " ".join(unescape(re.sub(r"<[^>]+>", sep, html)).split())
