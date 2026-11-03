#!/usr/bin/env python3
"""Check the Kalah TDD design pages (#87): the 12 designs and the A02 reference, built from the showcase view, the
report card and the method page, with class diagrams as numbered figures.

Usage: check_kalah_tdd_page_designs.py
"""
import functools
import importlib
import importlib.util
import re
import sys
import unittest
from html import unescape
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
BASE = "/studies/kalah-tdd-study/"
METHODS = "runs/full-1/methods/"
A02 = "designs/a02-reference"
DIAGRAM = re.compile(r'<figure class="diagram">.*?</figure>', re.S)
SPAN = re.compile(r'<span class="(hd|st)">(.*?)</span>', re.S)
CAPTION = re.compile(r"^(\d+) class(?:es)? and (\d+) links?\. Tag: recomputed\.$")
VERB = {"dependency": "uses", "aggregation": "holds", "extension": "extends"}


@functools.cache
def kalah(name):
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(f"kalah_tdd.{name}")


@functools.cache
def study():
    spec = importlib.util.spec_from_file_location("check_kalah_tdd_study", SCRIPTS / "check_kalah_tdd_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def snap():
    return kalah("snapshot").load()


def designs():
    return kalah("pagemap").DESIGNS


def slugs():
    return [f"designs/{d[0]}" for d in designs()] + [A02]


@functools.cache
def html(slug):
    return (STUDY / slug / "index.html").read_text(encoding="utf-8")


@functools.cache
def tree(slug):
    return study().Tree(html(slug)).root


def main(slug):
    return next(n for n in tree(slug).iter() if n.tag == "main")


def text(node):
    return " ".join(unescape(node.text()).split())


def flat(fragment):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def method(slug):
    return snap().files[f"{METHODS}{slug}.html"]


def view(slug):
    return kalah("snapshot").view(snap().files[kalah("snapshot").SHOWCASE], slug)


def report_section(heading):
    return kalah("snapshot").section(snap().files[kalah("snapshot").REPORT], heading)


def mutated(name, old, new):
    """The snapshot with the first old in file name replaced by new."""
    files = dict(snap().files)
    if old not in files[name]:
        raise AssertionError(f"{name} holds no {old[:60]!r}")
    files[name] = files[name].replace(old, new, 1)
    return snap()._replace(files=files)


def code_lines(slug):
    code = re.search(r'<h2 id="how-it-works">.*?<pre><code>(.*?)</code></pre>', method(slug), re.S).group(1)
    return unescape(code).split("\n")


def level(node):
    return study().heading(node)


def heading_after(slug, id):
    """The first p after the heading with this id."""
    kids = list(main(slug).iter())
    at = next(i for i, n in enumerate(kids) if n.attrs.get("id") == id)
    return next(n for n in kids[at + 1:] if n.tag == "p")


def class_figures(slug):
    """Each framed class diagram on the page as (figure node, enclosing heading level)."""
    out, last = [], 1
    for n in main(slug).iter():
        if level(n) and not n.closest("figure"):
            last = level(n)
        elif n.tag == "figure" and any(k.tag == "svg" and k.attrs.get("data-diagram-type") == "CLASS" for k in n.iter()):
            out.append((n, last))
    return out


class Built(unittest.TestCase):
    def test_built_not_stub(self):
        for slug in slugs():
            with self.subTest(slug):
                page = html(slug)
                self.assertFalse("kalah-tdd-stub" in page, "the page is a stub")
                self.assertEqual(page.count("<h1"), 1)
                levels = [level(n) for n in tree(slug).iter() if level(n)]
                self.assertEqual(levels[0], 1)
                self.assertTrue(all(b <= a + 1 for a, b in zip(levels, levels[1:])), f"a heading skips a level: {levels}")
                ids = [n.attrs["id"] for n in tree(slug).iter() if n.attrs.get("id")]
                self.assertEqual(len(ids), len(set(ids)))
                toc = next(n for n in tree(slug).iter() if n.attrs.get("id") == "toc")
                hrefs = [n.attrs.get("href") for n in toc.iter() if n.tag == "a"]
                wanted = kalah("pagemap").BY_SLUG[slug].anchors if slug == A02 else ("how-it-works", "conclusion")
                for id in wanted:
                    self.assertIn(f"{BASE}{slug}/#{id}", hrefs)

    def test_coverage_counts_designs(self):
        items, errors = study().inventory(snap().files)
        self.assertEqual([e for e in errors if "designs/" in e], [])
        mine = [i for i in items if (i.page or "").startswith("designs/")]
        self.assertEqual(len(mine), 3738)
        pages = study().load_pages(SCRIPTS.parent)
        self.assertEqual(study().coverage(mine, pages), ([], len(mine)))

    def test_deterministic(self):
        build = importlib.import_module("build_kalah_tdd_study")
        page, idx = kalah("pagemap").BY_SLUG["designs/tpp"], kalah("links").index(snap())
        first = build.render_page(page, snap(), idx)
        self.assertFalse("kalah-tdd-stub" in first, "the page is a stub")
        self.assertEqual(first, build.render_page(page, snap(), idx))


class Merge(unittest.TestCase):
    def test_steps_union(self):
        for slug, *_ in designs():
            with self.subTest(slug):
                shown = [(k, unescape(t)) for k, t in SPAN.findall(re.search(r'<pre class="steps">(.*?)</pre>', view(slug), re.S).group(1))]
                numbers = [m.group(1) if (m := re.match(r"  (\d+)\. ", line)) else None for line in code_lines(slug)]
                self.assertEqual(len(shown), len(numbers))
                want = [(k, f"{n}. {t}" if n else t) for (k, t), n in zip(shown, numbers)]
                pre = next(n for n in main(f"designs/{slug}").iter() if n.tag == "pre" and "steps" in n.classes())
                got = [(s.attrs["class"], text(s)) for s in pre.elements()]
                self.assertEqual(got, want)
                borrowed = [line for line in code_lines(slug) if line.startswith("  with ")]
                self.assertEqual(len(borrowed), sum(t.startswith("also: ") for _, t in want))

    def test_steps_union_refuses_loss(self):
        d = kalah("pages.designs")
        pre = re.search(r'<pre class="steps">.*?</pre>', view("tpp"), re.S).group(0)
        code = re.search(r"<pre><code>.*?</code></pre>", method("tpp"), re.S).group(0)
        self.assertIn('<span class="st">2. Pick the next test', d.merge_steps("tpp", pre, code))
        step = '<span class="st">Pass it with that one transformation. Name it in the commit message.</span>'
        for broken in (pre.replace(step, ""), pre.replace("Name it in the commit", "Name it in a commit")):
            with self.subTest(broken[-80:]), self.assertRaisesRegex(ValueError, r"tpp\b.*step"):
                d.merge_steps("tpp", broken, code)
        last = pre.rpartition('<span class="st">')
        broken = {"last step dropped": (last[0] + "</pre>", code, "only one"),
                  "text between lines": (pre.replace("</span><span", "</span>stray<span", 1), code, "outside a step line"),
                  "unknown method line": (pre, code.replace("<pre><code>", "<pre><code>  x. &quot;y&quot;\n", 1), "no known form")}
        for name, (shown, method_code, why) in broken.items():
            with self.subTest(name), self.assertRaisesRegex(ValueError, rf"tpp\b.*{why}"):
                d.merge_steps("tpp", shown, method_code)

    def test_text_union(self):
        d = kalah("pages.designs")
        for slug, heading, *_ in designs():
            with self.subTest(slug):
                page = flat(html(f"designs/{slug}"))
                verdict = flat(re.search(r"<h2>Verdict</h2><p>(.*?)</p>", view(slug), re.S).group(1))
                conclusion = flat(re.search(r'<h2 id="conclusion">Conclusion</h2>\s*<p>(.*?)</p>', method(slug), re.S).group(1))
                self.assertEqual(conclusion, verdict + " Tag: recomputed.")
                self.assertEqual(text(heading_after(f"designs/{slug}", "conclusion")), conclusion)
                self.assertEqual(page.count(verdict), 1)
                card = flat(re.search(r"</h3>\s*<p>(.*?)</p>", report_section(heading), re.S).group(1))
                family = flat(re.search(r'<h2 id="how-it-works">.*?<p>(.*?)</p>', method(slug), re.S).group(1))
                self.assertIn(family, card)
                self.assertEqual(page.count(family), 1)
                self.assertIn(card, page)
        self.assertIn("rep-1 contrast arm, no survey run. Family:", flat(html("designs/anchor-engineering")))
        self.assertEqual(d.union("tpp", "a b", "x a  b y"), "x a  b y")
        with self.assertRaisesRegex(ValueError, "tpp"):
            d.union("tpp", "one text", "another text")

    def test_showcase_header_matches(self):
        d = kalah("pages.designs")
        for slug, _, name, blurb in designs():
            with self.subTest(slug):
                self.assertEqual(unescape(re.search(r"<h1>(.*?)</h1>", view(slug)).group(1)), name)
                self.assertEqual(unescape(re.search(r'<p class="lede">(.*?)</p>', view(slug)).group(1)), blurb)
                self.assertNotIn("All designs", html(f"designs/{slug}"))
        page = kalah("pagemap").BY_SLUG["designs/tpp"]
        self.assertTrue(d.showcase(page, view("tpp")))
        for wrong in (page._replace(title="TPP"), page._replace(blurb="Another lede.")):
            with self.subTest(wrong.title), self.assertRaisesRegex(ValueError, "tpp"):
                d.showcase(wrong, view("tpp"))
        # The report card name is replaced by "Report summary", so it must also equal the page title.
        h3 = f'<h3 id="{designs()[4][1]}">{page.title}</h3>'
        renamed = mutated(kalah("snapshot").REPORT, h3, h3.replace(page.title, "TPP"))
        with self.assertRaisesRegex(ValueError, "tpp.*report"):
            d.design(page, renamed, kalah("links").index(snap()))


class Diagrams(unittest.TestCase):
    def test_class_diagrams_framed(self):
        sources = sum(len(DIAGRAM.findall(method(s))) for s, *_ in designs())
        sources += sum(len(DIAGRAM.findall(report_section(a))) for a in [d[1] for d in designs()] + [kalah("pagemap").BY_SLUG[A02].anchors[0]])
        self.assertEqual(sources, 67)
        framed = links = 0
        for slug in slugs():
            part = kalah("pagemap").number(slug)
            figures = class_figures(slug)
            framed += len(figures)
            ids = {n.attrs.get("id") for n in tree(slug).iter()}
            with self.subTest(slug):
                self.assertEqual([f.attrs["id"] for f, _ in figures], [f"fig-{part}-{k}" for k in range(1, len(figures) + 1)])
                for fig, enclosing in figures:
                    title = next(k for k in fig.elements() if level(k))
                    self.assertEqual(level(title), enclosing + 1, fig.attrs["id"])
                    self.assertNotIn("id", title.attrs)
                    self.assertIsNotNone(next((k for k in fig.elements() if k.tag == "figcaption"), None))
                said = re.findall(r"<p>The report's class diagram for this design is identical to <a href=\"#(fig-[\d-]+)\">", html(slug))
                links += len(said)
                self.assertTrue(set(said) <= ids, said)
        self.assertEqual((framed, links), (56, 11))

    def test_only_report_diagram_deduped(self):
        frame_all = kalah("figures.class_diagram").frame_all
        figure = f'<figure class="diagram">{re.search(r"<svg.*?</svg>", method("tpp"), re.S).group(0)}</figure>'
        fragments = [f"<h2>Report summary</h2>{figure}", f"<h2>Builds</h2>{figure}"]
        first, later = frame_all(fragments, "designs/tpp", report=0)
        self.assertIn('identical to <a href="#fig-15-1">Figure 15.1</a>', first)
        self.assertIn('id="fig-15-1"', later)
        with self.assertRaisesRegex(ValueError, "tpp"):
            frame_all(fragments, "designs/tpp", report=None)
        with self.assertRaisesRegex(ValueError, "tpp"):
            frame_all([*fragments, fragments[1]], "designs/tpp", report=0)

    def test_class_diagram_text_version(self):
        diagram = kalah("figures.class_diagram")
        for slug in slugs():
            for fig, _ in class_figures(slug):
                with self.subTest(fig.attrs["id"]):
                    svg = next(n for n in fig.iter() if n.tag == "svg")
                    entities = [g for g in svg.iter() if g.tag == "g" and "entity" in g.classes()]
                    lines = [g for g in svg.iter() if g.tag == "g" and "link" in g.classes()]
                    caption = next(k for k in fig.elements() if k.tag == "figcaption")
                    m = CAPTION.match(text(next(p for p in caption.elements() if p.tag == "p")))
                    self.assertEqual((int(m.group(1)), int(m.group(2))), (len(entities), len(lines)))
                    items = [text(li) for li in caption.iter() if li.tag == "li"]
                    said = [i for i in items if re.search(r" (uses|holds|extends) ", i)]
                    self.assertEqual(len(said), len(lines))
                    self.assertEqual(sorted(re.search(r" (uses|holds|extends) ", i).group(1) for i in said),
                                     sorted(VERB[g.attrs["data-link-type"]] for g in lines))
                    # A package is a drawn cluster. A class inside another class reads as nested in it.
                    clusters = {g.attrs["data-qualified-name"] for g in svg.iter() if g.tag == "g" and "cluster" in g.classes()}
                    packages = [re.match(r"Package (.*?): ", i).group(1) for i in items if i.startswith("Package ")]
                    self.assertLessEqual(set(packages), clusters)
                    rest = [i for i in items if i not in said and not i.startswith(("Package ", "No package: "))]
                    self.assertTrue(all(", nested in " in i for i in rest), rest)
        held = ('<svg aria-label="t"><g class="cluster" data-qualified-name="kalah" id="d-ent0002"></g>'
                '<g class="entity" data-qualified-name="kalah.MoveResult" id="d-ent0003"></g>'
                '<g class="entity" data-qualified-name="kalah.MoveResult.Outcome" id="d-ent0004"></g></svg>')
        self.assertEqual(diagram.describe(held)[2], ["Package kalah: MoveResult", "Outcome, nested in MoveResult"])
        with self.assertRaisesRegex(ValueError, "kalah.Lost.Outcome"):
            diagram.describe(held.replace("kalah.MoveResult.Outcome", "kalah.Lost.Outcome"))
        svg = re.search(r"<svg\b.*?</svg>", method("tpp"), re.S).group(0)
        self.assertEqual(diagram.describe(svg)[:2], (3, 2))
        self.assertIn("Kalah uses Board", diagram.describe(svg)[2])
        with self.assertRaisesRegex(ValueError, "realization"):
            diagram.describe(svg.replace('data-link-type="dependency"', 'data-link-type="realization"', 1))


class Tables(unittest.TestCase):
    def test_tables_wrapped(self):
        for slug in slugs():
            with self.subTest(slug):
                tables = [n for n in main(slug).iter() if n.tag == "table"]
                self.assertTrue(tables)
                for t in tables:
                    region = t.parent
                    self.assertEqual((region.attrs.get("class"), region.attrs.get("role")), ("table-scroll", "region"))
                    self.assertTrue(region.attrs.get("aria-label", "").strip())
                    self.assertFalse([n for n in t.iter() if n.tag == "th" and not n.attrs.get("scope")])
                labels = [n.attrs.get("aria-label") for n in main(slug).iter() if n.attrs.get("role") == "region"]
                self.assertEqual([k for k in set(labels) if labels.count(k) > 1], [])
        d = kalah("pages.designs")
        self.assertIn('aria-label="Headline"', d.wrap_tables(['<h5 id="h">Headline</h5><table><tr><td>x</td></tr></table>'])[0])
        table = "<table><tr><td>x</td></tr></table>"
        twice = d.wrap_tables([f"<h2>Records</h2><h4>Replicate r1</h4><h5>Headline</h5>{table}{table}",
                               f"<h4>Replicate r2</h4><h5>Headline</h5>{table}<h3>Consistency</h3>{table}"])
        self.assertEqual(re.findall(r'aria-label="([^"]*)"', "".join(twice)),
                         ["Headline, Replicate r1, table 1 of 2", "Headline, Replicate r1, table 2 of 2",
                          "Headline, Replicate r2", "Consistency"])
        with self.assertRaisesRegex(ValueError, "nested"):
            d.wrap_tables(["<h3>T</h3><table><tr><td><table><tr><td>x</td></tr></table></td></tr></table>"])


class Ids(unittest.TestCase):
    def test_ids_and_links_kept(self):
        s, ID = kalah("snapshot"), kalah("snapshot").ID
        idx = kalah("links").index(snap())
        for slug, heading, *_ in designs():
            here = f"designs/{slug}"
            with self.subTest(slug):
                ids = {n.attrs["id"] for n in tree(here).iter() if n.attrs.get("id")}
                source = ID.findall(method(slug).partition("<main")[2]) + ID.findall(view(slug)) + ID.findall(report_section(heading))
                kept = lambda i: i in ids or any(re.fullmatch(re.escape(i) + r"-\d+", j) for j in ids)
                self.assertEqual([i for i in source if not kept(i)], [])
                self.assertEqual(idx[s.REPORT][heading], (here, heading))
                self.assertIn(heading, ids)
                for href in re.findall(r'href="([^"]*)"', html(here).split('<main id="main">', 1)[1]):
                    if href.startswith(BASE) and not href.startswith(BASE + "designs/"):
                        self.assertNotIn("#", href)
                columns = next(n for n in tree(here).iter() if n.attrs.get("id") == "columns")
                pointer = heading_after(here, "columns")
                self.assertEqual(text(columns), "Terms and columns")
                self.assertEqual({a.attrs["href"] for a in pointer.iter() if a.tag == "a"},
                                 {BASE + "methodology/measures/", BASE + "glossary/"})

    def test_lead_and_summary_links_rewritten(self):
        s, d = kalah("snapshot"), kalah("pages.designs")
        page, idx = kalah("pagemap").BY_SLUG["designs/tpp"], kalah("links").index(snap())
        card, shown = report_section(designs()[4][1]), view("tpp")
        cases = ((s.REPORT, card, card.replace("</svg>", '<a href="#classic-greedy-tdd">Classic</a></svg>', 1),
                  f'<a href="{BASE}designs/classic/#classic-greedy-tdd">Classic</a>'),
                 (s.SHOWCASE, shown, shown.replace("No award in this survey.", 'No <a href="#classic">award</a>.'),
                  f'<a href="{BASE}designs/classic/">award</a>'))
        for name, old, new, want in cases:
            with self.subTest(name):
                fragments, _ = d.design(page, mutated(name, old, new), idx)
                self.assertTrue(want in "".join(fragments), want)


class Reference(unittest.TestCase):
    def test_reference_page(self):
        page = kalah("pagemap").BY_SLUG[A02]
        h2 = [n.attrs.get("id") for n in main(A02).iter() if n.tag == "h2"]
        self.assertEqual(tuple(h2), page.anchors)
        figures = class_figures(A02)
        self.assertEqual([f.attrs["id"] for f, _ in figures], ["fig-23-1"])
        self.assertIn("Figure 23.1", text(figures[0][0]))
        regions = {n.attrs["aria-label"]: n for n in main(A02).iter() if n.attrs.get("role") == "region" and n.tag == "div"
                   and "table-scroll" in n.classes()}
        rows = lambda label: len([r for r in regions[label].iter() if r.tag == "tr"])
        self.assertEqual(rows("Reference"), 32)
        self.assertEqual(rows(unescape(re.search(r"<h3[^>]*>(.*?)</h3>", report_section(page.anchors[0])).group(1))), 12)


if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPTS))
    unittest.main()
