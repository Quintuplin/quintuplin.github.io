#!/usr/bin/env python3
"""Check the Kalah TDD critical questions page (#69): the report questions section with every answer id and paragraph
kept, Figure 10.1 framing the status bar, the status table in a labelled region and each answer's status and tag.

Usage: check_kalah_tdd_page_questions.py
"""
import functools
import importlib
import importlib.util
import re
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STUDY = SCRIPTS.parent / "studies/kalah-tdd-study"
BASE = "/studies/kalah-tdd-study/"
SLUG = "questions"
# Report questions items on the page, from check_kalah_tdd_study.inventory at the snapshot sha: 22 rows and 22 ids.
QUESTION_ITEMS = 44
P = re.compile(r"<p\b[^>]*>.*?</p>", re.S)
ANSWER = re.compile(r'<div class="answer" id="(q\d+)">(.*?)</div>', re.S)
ROW = re.compile(r'<td class="num">(Q\d+)</td><td class="q"><a href="#q\d+">(.*?)</a></td><td class="st">(.*?)</td>', re.S)
TAG = re.compile(r'<span class="tag">([^<]*)</span>')
CHART = re.compile(r'<a class="qchart" href="([^"]*)"')


@functools.cache
def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kalah(name):
    script("build_kalah_tdd_study")
    return importlib.import_module(f"kalah_tdd.{name}")


def study():
    return script("check_kalah_tdd_study")


@functools.cache
def snap():
    return kalah("snapshot").load()


def report():
    return snap().files[kalah("snapshot").REPORT]


@functools.cache
def source():
    return kalah("snapshot").section(report(), SLUG)


@functools.cache
def html():
    return (STUDY / SLUG / "index.html").read_text(encoding="utf-8")


@functools.cache
def parsed():
    return study().parse(html())


def main_html():
    return html()[html().index('<main id="main"'):html().index("</main>")]


def block(cls):
    """The source div of this class, which holds no nested div."""
    return re.search(rf'<div class="{cls}"[^>]*>.*?</div>' if cls != "qtable" else r'<div class="qtable">.*?</table></div>',
                     source(), re.S).group(0)


def rows():
    """{QN: (question html, chip html)} from the source status table."""
    return {n: (q, chip) for n, q, chip in ROW.findall(block("qtable"))}


def questions():
    return kalah("pages.questions")


def refused(test, html, *named, absent=()):
    with test.assertRaises(ValueError) as caught:
        questions().section(html, "10.1")
    for name in named:
        test.assertIn(name, str(caught.exception))
    for text in absent:
        test.assertNotIn(text, str(caught.exception))


class Questions(unittest.TestCase):
    def test_built_not_stub(self):
        page = parsed()
        self.assertFalse(page.stub, "questions is a stub")
        heads = [n for n in page.root.iter() if study().heading(n)]
        levels = [study().heading(h) for h in heads]
        self.assertEqual((levels.count(1), levels[0]), (1, 1))
        self.assertFalse([b for a, b in zip(levels, levels[1:]) if b > a + 1], f"heading skipped: {levels}")
        main = page.ids["main"]
        sub = [(n.tag, n.attrs["id"]) for n in main.iter() if n.tag in ("h2", "h3") and n.attrs.get("id")]
        self.assertEqual(sub, [("h2", "questions"), ("h3", "question-table"), ("h3", "answers")])
        self.assertEqual([i for t, i in sub if t == "h2"], list(kalah("pagemap").BY_SLUG[SLUG].anchors))
        ids = [n.attrs["id"] for n in page.root.iter() if n.attrs.get("id")]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        current = next(n for n in page.ids["toc"].iter() if n.attrs.get("aria-current") == "page")
        listed = [a.attrs["href"] for a in current.parent.iter() if a.tag == "a" and a is not current]
        self.assertEqual(listed, [f"{BASE}{SLUG}/#{i}" for _, i in sub])

    def test_coverage_counts_questions(self):
        items, errors = study().inventory(snap().files)
        self.assertEqual(errors, [])
        items = [i for i in items if i.page == SLUG]
        self.assertEqual(len(items), QUESTION_ITEMS)
        errors, checked = study().coverage(items, {SLUG: html()})
        self.assertEqual([e for e in errors if "questions lacks" in e], [])
        self.assertEqual(errors, [])
        self.assertEqual(checked, QUESTION_ITEMS)

    def test_answer_ids_kept(self):
        main = parsed().ids["main"]
        answers = [n for n in main.iter() if "answer" in n.classes()]
        self.assertEqual([n.attrs.get("id") for n in answers], [f"q{k}" for k in range(1, 23)])
        self.assertTrue(all(n.tag == "div" for n in answers))
        want = [study().question(study().Tree(f'<div id="{q}">{b}</div>').root) for q, b in ANSWER.findall(source())]
        self.assertEqual([study().question(n) for n in answers], want)
        idx, report_doc = kalah("links").index(snap()), kalah("snapshot").REPORT
        hrefs = re.findall(r'href="#(q\d+)"', report())
        self.assertEqual(len(hrefs), 42)
        for q in hrefs:
            self.assertEqual(idx[report_doc][q], (SLUG, q))
            self.assertIn(q, parsed().ids)

    def test_text_verbatim(self):
        want, have = P.findall(source()), iter(P.findall(main_html()))
        self.assertEqual(len(want), 169)
        missing = [p for p in want if not any(p == h for h in have)]
        self.assertEqual(missing, [], "source paragraphs missing or out of order")

    def test_status_and_tag_kept(self):
        tag, chips = kalah("parts").tag, rows()
        statuses, tags = Counter(), Counter()
        answers = ANSWER.findall(main_html())
        self.assertEqual(len(answers), 22)
        for q, body in answers:
            with self.subTest(q):
                kinds = TAG.findall(body)
                self.assertEqual(len(kinds), 1)
                self.assertEqual(TAG.search(body).group(0), tag(kinds[0]))
                chip = chips[q.upper()][1]
                line = re.match(r'<p class="aq">.*?</p><p>Status: (.*?)</p>', body, re.S)
                self.assertTrue(line, "no status line after the question")
                self.assertEqual(line.group(1), chip)
                self.assertEqual(body.count('class="chip"'), 1)
                statuses[re.sub(r"<[^>]+>", "", chip)] += 1
                tags[kinds[0]] += 1
        self.assertEqual(statuses, {"answered": 14, "partly answered": 8})
        self.assertEqual(tags, {"recomputed": 18, "verified": 4})

    def test_status_figure(self):
        main = main_html()
        fig = re.search(r'<figure id="question-status" aria-label="Figure 10\.1: [^"]+">.*?</figure>', main, re.S)
        self.assertTrue(fig, "no Figure 10.1")
        intro = P.findall(source())[0]
        self.assertTrue(main.index(intro) < fig.start() < main.index('id="question-table"'))
        self.assertEqual(main.index("<figure"), fig.start())
        fig = fig.group(0)
        self.assertIn(block("qbar") + block("qlegend"), fig)
        self.assertEqual(re.findall(r'<a href="([^"]+)" aria-label="Data for Figure 10.1">', fig), ["#question-table"])
        items = re.findall(r"<li>(.*?)</li>", fig)
        by = {}
        for n, (_, chip) in rows().items():
            by.setdefault(re.sub(r"<[^>]+>", "", chip), []).append(n)
        self.assertEqual(len(items), len(by))
        for item, (status, nums) in zip(items, by.items()):
            with self.subTest(status):
                self.assertTrue(item.lower().startswith(status))
                self.assertIn(f" {len(nums)} ", item)
                self.assertEqual(re.findall(r"Q\d+", item), nums)
        region = ('<h3 id="question-table">Status of each question</h3><div class="table-scroll" role="region" '
                  f'tabindex="0" aria-label="Status of each question">{block("qtable")}</div><h3 id="answers">')
        self.assertIn(region, main)

    def test_chart_links(self):
        idx, doc = kalah("links").index(snap()), kalah("snapshot").REPORT
        want = [kalah("links").target(h, doc, SLUG, idx) for h in CHART.findall(source())]
        self.assertEqual(len(want), 20)
        self.assertEqual(CHART.findall(main_html()), want)
        self.assertEqual([h for h in re.findall(r'href="([^"]*)"', html()) if "report.html" in h], [])

    def test_refuses_status_mismatch(self):
        cases = {"qbar flex": ('style="flex:14"', 'style="flex:13"', "qbar"),
                 "qbar title": ('title="answered 14"', 'title="answered 13"', "qbar"),
                 "qbar aria-label": ("14 answered and 8", "13 answered and 8", "qbar"),
                 "legend count": ('<b class="cnt">14</b>', '<b class="cnt">15</b>', "qlegend"),
                 "no chip": ('<td class="st"><span class="chip" data-k="good"><i></i>answered</span></td>',
                             '<td class="st"></td>', "Q1"),
                 "unknown status": ("<i></i>answered</span></td>", "<i></i>maybe</span></td>", "maybe")}
        for name, (old, new, said) in cases.items():
            with self.subTest(name):
                self.assertIn(old, source())
                refused(self, source().replace(old, new, 1), said)
        self.assertTrue(questions().section(source(), "10.1"))

    def test_refuses_answer_mismatch(self):
        sec = source()
        q2, q3 = (re.search(rf'<div class="answer" id="{q}">.*?</div>', sec, re.S).group(0) for q in ("q2", "q3"))
        tag = re.search(r'<span class="tag">[^<]*</span>', q3).group(0)
        cases = {"dropped": (sec.replace(q2, ""), "q2"),
                 "swapped": (sec.replace(q2 + q3, q3 + q2), "q2"),
                 "reworded": (sec.replace("<b>Q3</b> Does the", "<b>Q3</b> Did the"), "q3"),
                 "no tag": (sec.replace(q3, q3.replace(tag, "")), "q3"),
                 "two tags": (sec.replace(q3, q3.replace(tag, tag + tag)), "q3")}
        for name, (html, said) in cases.items():
            with self.subTest(name):
                self.assertNotEqual(html, sec)
                refused(self, html, said)
        # A tag span that is not plain parts.tag markup, and a label naming another question, get their own messages.
        refused(self, sec.replace(q3, q3.replace('<span class="tag">', '<span class="tag" title="t">')), "q3",
                absent=("1 claim tags, not 1",))
        refused(self, sec.replace(q3, q3.replace("<b>Q3</b>", "<b>Q4</b>")), "Q4")

    def test_refuses_unknown_block(self):
        for extra in ("<ul><li>b</li></ul>", "stray text", '<p class="lead">x</p>', '<div class="qbar"></div>'):
            with self.subTest(extra):
                refused(self, source().replace('<div class="answer" id="q1">', extra + '<div class="answer" id="q1">'),
                        "questions", extra[:12])


if __name__ == "__main__":
    unittest.main()
