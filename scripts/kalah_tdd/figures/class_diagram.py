"""PlantUML class diagrams from the study run framed as numbered study figures with a text version (#87)."""

import re
from html import unescape

from .. import parts

SOURCE = re.compile(r'<figure class="diagram">(<svg\b.*?</svg>)</figure>', re.S)
HEADING = re.compile(r"<h([1-6])\b")
ENTITY = re.compile(r'<g class="entity" data-qualified-name="([^"]+)" id="[^"]*-(ent\d+)"')
CLUSTER = re.compile(r'<g class="cluster" data-qualified-name="([^"]+)"')
LINK = re.compile(r'<g class="link" data-entity-1="(ent\d+)" data-entity-2="(ent\d+)"[^>]*data-link-type="([^"]+)"')
# Entity 1 relates to entity 2. An aggregation diamond sits at entity 1.
VERB = {"dependency": "uses", "aggregation": "holds", "extension": "extends"}
# Said only in place of a report summary diagram, so it names the report.
SAME = ("<p>The report's class diagram for this design is identical to <a href=\"#{id}\">Figure {n}</a> below, "
        "so it is shown once. Tag: " + parts.tag("recomputed") + ".</p>")


def describe(svg, slug=None):
    """(class count, link count, text version items): one item per package naming its classes, one per class nested
    in another class, then one per link. A package is a drawn cluster. A refusal names slug when given."""
    where = f"{slug}: " if slug else ""
    entities = dict((key, name) for name, key in ENTITY.findall(svg))
    shorts = [n.rpartition(".")[2] for n in entities.values()]
    short = {k: s if shorts.count(s) == 1 else n for (k, n), s in zip(entities.items(), shorts)}
    owners, clusters = {n: short[k] for k, n in entities.items()}, set(CLUSTER.findall(svg))
    packages, nested = {}, []
    for key, name in entities.items():
        owner = name.rpartition(".")[0]
        if owner in owners:
            nested.append(f"{short[key]}, nested in {owners[owner]}")
        elif owner in clusters or not owner:
            packages.setdefault(owner, []).append(short[key])
        else:
            raise ValueError(f"{where}class diagram class {name} sits in {owner}, which is no drawn package or class")
    items = [f"Package {p}: {', '.join(names)}" if p else f"No package: {', '.join(names)}" for p, names in packages.items()]
    items += nested
    links = LINK.findall(svg)
    for a, b, kind in links:
        if kind not in VERB:
            raise ValueError(f"{where}class diagram link type {kind!r} has no reading")
        if a not in short or b not in short:
            raise ValueError(f"{where}class diagram link {a} to {b} names no class")
        items.append(f"{short[a]} {VERB[kind]} {short[b]}")
    return len(entities), len(links), items


def caption(classes, links):
    return (f"{classes} class{'' if classes == 1 else 'es'} and {links} link{'' if links == 1 else 's'}. "
            f"Tag: {parts.tag('recomputed')}.")


def frame_all(fragments, slug, report=None, numbers=None):
    """Each source class diagram framed as Figure P.k, its title one level below the enclosing heading. A diagram in
    fragments[report], the report summary, repeated later on the page is shown once and its first place links the
    later figure. Any other repeat is refused. numbers continues the page's figure numbers when earlier figures took some."""
    found = [(i, m) for i, f in enumerate(fragments) for m in SOURCE.finditer(f)]
    repeated = {k for k, (_, m) in enumerate(found) if any(m.group(0) == later.group(0) for _, later in found[k + 1:])}
    if stray := [k for k in repeated if found[k][0] != report]:
        raise ValueError(f"{slug}: class diagram {stray[0] + 1} repeats outside the report summary")
    numbers, number = numbers or parts.numbers(slug), {}
    for k in range(len(found)):
        if k not in repeated:
            number[k] = next(numbers)
    target = {k: number[next(j for j in range(k + 1, len(found)) if j not in repeated and found[j][1].group(0) == found[k][1].group(0))]
              for k in repeated}
    out, k, enclosing = [], 0, 1
    for i, fragment in enumerate(fragments):
        pieces, at = [], 0
        for m in re.finditer(rf"{HEADING.pattern}|{SOURCE.pattern}", fragment, re.S):
            if m.group(1):
                enclosing = int(m.group(1))
                continue
            pieces.append(fragment[at:m.start()])
            n = target.get(k) or number[k]
            id = "fig-" + n.replace(".", "-")
            pieces.append(SAME.format(id=id, n=n) if k in repeated else frame(slug, n, id, m.group(2), enclosing + 1))
            at, k = m.end(), k + 1
        out.append("".join(pieces) + fragment[at:])
    return out


def frame(slug, n, id, svg, level):
    label = re.match(r'<svg\b[^>]*\baria-label="([^"]*)"', svg)
    if not label:
        raise ValueError(f"{slug}: class diagram for Figure {n} has no aria-label to title it")
    title = unescape(label.group(1))
    classes, links, items = describe(svg, slug)
    return parts.figure(n, id, title, svg, caption(classes, links), None, items, level=level)
