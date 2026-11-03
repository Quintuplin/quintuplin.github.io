"""Dot charts for the Kalah TDD results pages (#90): one row per label, one linear value axis, series 1 as circles
and series 2 as squares, hollow marks for a flagged value and dashed reference lines. Colours come only from the
study.css plot and series classes, so both themes and forced colours apply."""
from html import escape
from typing import NamedTuple

W, PAD, ROW, LINE, R = 480, 24, 44, 16, 5
# Two series sit above and below the row centre, so equal values stay apart.
DODGE = 6


class Mark(NamedTuple):
    row: str
    value: float
    title: str
    series: int = 0
    hollow: bool = False


class Ref(NamedTuple):
    value: float
    label: str


def num(v):
    return f"{round(v, 1):g}"


def scale(domain):
    """The x of a value on a linear axis from PAD to W - PAD. Refuses a value outside the domain."""
    lo, hi = domain
    if not lo < hi:
        raise ValueError(f"empty domain {domain}")

    def x(v):
        if not lo <= v <= hi:
            raise ValueError(f"value {v} is outside the domain {domain}")
        return round(PAD + (v - lo) / (hi - lo) * (W - 2 * PAD), 1)
    return x


def text(x, y, s, anchor="middle", cls=""):
    attr = f' class="{cls}"' if cls else ""
    return f'<text x="{num(x)}" y="{num(y)}" text-anchor="{anchor}"{attr}>{escape(s)}</text>'


def shape(series, x, y, cls, title=""):
    """A circle for series 0 and a square for series 1, with its title."""
    t = f"<title>{escape(title)}</title>" if title else ""
    if series == 0:
        return f'<circle class="{cls}" cx="{num(x)}" cy="{num(y)}" r="{R}">{t}</circle>'
    return f'<rect class="{cls}" x="{num(x - R)}" y="{num(y - R)}" width="{2 * R}" height="{2 * R}">{t}</rect>'


def svg(label, axis, series, marks, domain, ticks, refs=()):
    """The chart as an inline SVG string. series names one or two series; a key shows only when there are two.
    Each row label sits above its marks, so the chart keeps its labels at narrow widths."""
    two = len(series) == 2
    if len(series) not in (1, 2) or any(m.series >= len(series) for m in marks):
        raise ValueError(f"marks name a series outside {series}")
    x, out, y = scale(domain), [], 8
    if two:
        key = [shape(i, PAD + i * W // 3 + R, y + R, f"s{i + 1}") + text(PAD + i * W // 3 + 2 * R + 6, y + 9, name, "start")
               for i, name in enumerate(series)]
        out.append(f'<g class="key">{"".join(key)}</g>')
        y += 2 * R + 12
    ref_tops = []
    for ref in refs:
        y += LINE
        rx = x(ref.value)
        out.append(text(rx + 4 if rx < W / 2 else rx - 4, y, ref.label, "start" if rx < W / 2 else "end"))
        ref_tops.append((rx, y + 4))
    top = y + 6
    rows = list(dict.fromkeys(m.row for m in marks))
    bottom = top + len(rows) * ROW
    out = ([f'<line class="grid" x1="{num(x(t))}" x2="{num(x(t))}" y1="{top}" y2="{bottom}"/>' for t in ticks] + out
           + [f'<line class="refline" x1="{num(rx)}" x2="{num(rx)}" y1="{ry}" y2="{bottom}"/>' for rx, ry in ref_tops])
    for i, row in enumerate(rows):
        out.append(text(PAD, top + i * ROW + 14, row, "start", "lbl"))
    for m in marks:
        cy = top + rows.index(m.row) * ROW + 30 + ((DODGE if m.series else -DODGE) if two else 0)
        out.append(shape(m.series, x(m.value), cy, f"mk s{m.series + 1}" + (" hollow" if m.hollow else ""), m.title))
    out += [text(x(t), bottom + 16, f"{t:g}") for t in ticks]
    # The axis label comes right after the axis line, where MetricDefs reads it.
    out += [f'<line class="axis" x1="{PAD}" x2="{W - PAD}" y1="{bottom}" y2="{bottom}"/>', text(W / 2, bottom + 36, axis)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="plot" viewBox="0 0 {W} {bottom + 46}" width="{W}" '
            f'role="img" aria-label="{escape(label)}">{"".join(out)}</svg>')
