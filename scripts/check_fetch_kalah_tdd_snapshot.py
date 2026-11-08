#!/usr/bin/env python3
"""Check that the Kalah TDD snapshot comes from one clean tdd-experiment commit, drops host paths and matches its manifest.

Self-contained: builds throwaway git repos from scripts/fixtures/kalah-tdd, so CI needs only python3 and git.
Also checks the committed _snapshots/kalah-tdd-study against its MANIFEST.json.
Usage: check_fetch_kalah_tdd_snapshot.py
"""
import functools
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
FIXTURES = SCRIPTS / "fixtures/kalah-tdd"
SNAPSHOT = SCRIPTS.parent / "_snapshots/kalah-tdd-study"
# Source path in tdd-experiment to its fixture.
SOURCES = {"runs/full-1/report.html": "report.html", "runs/full-1/methods/classic.html": "classic.html",
           "runs/full-1/methods/outside-in.html": "outside-in.html", "artifact/showcase.html": "showcase.html", "harness/workflow/stages.json": "stages.json",
           "runs/full-1/args.json": "args.json", "runs/rep-2/rebuild/args.json": "rebuild-args.json",
           "harness/collect.sh": "collect.sh",
           "harness/report/render.py": "render.py", "harness/report/awards.py": "awards.py",
           "harness/report/stats.py": "stats.py", "docs/SPEC.md": "SPEC.md"}
# The args.json fields that hold host paths, as the committed snapshot drops them.
PATH_FIELDS = {"blind_dir", "cases_dir", "clones_dir", "path", "scratch_dir", "split"}
COMMIT = ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", "commit", "-qm")


@functools.cache
def fetcher():
    path = SCRIPTS / "fetch_kalah_tdd_snapshot.py"
    spec = importlib.util.spec_from_file_location("fetch_kalah_tdd_snapshot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(name):
    return (FIXTURES / f"{name}.fixture").read_bytes()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strings(value):
    """Every string in value, dict keys included."""
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [k, *strings(v)]]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return [value] if isinstance(value, str) else []


class Fetch(unittest.TestCase):
    """A fixture tdd-experiment repo, a doc repo and an artifacts backup version beside them."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        # Keeps git from finding a repository above the temp folder.
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.root)
        self.study = self.repo("tdd-experiment", {path: fixture(name) for path, name in SOURCES.items()})
        self.head = self.git(self.study, "rev-parse", "HEAD")
        docs = self.repo("course", {"tdd-methodologies.md": fixture("tdd-methodologies.md")})
        self.doc = docs / "tdd-methodologies.md"
        self.published = self.root / "artifacts/kalah-tdd-experiment/raw/v1-abcd"
        (self.published / "methods").mkdir(parents=True)
        self.published.with_name("v1-abcd.html").write_bytes(fixture("report.html"))
        # The published method page differs from the committed one, as the real backup's do.
        for name in ("classic.html", "outside-in.html"):
            (self.published / "methods" / name).write_bytes(fixture(name) + b"<!-- published -->\n")
        self.out = self.root / "_snapshots/kalah-tdd-study"

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()

    def repo(self, name, files):
        repo = self.root / name
        for path, data in files.items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_bytes(data)
        self.git(repo, "init", "-q")
        self.git(repo, "add", ".")
        self.git(repo, *COMMIT, "fixture")
        return repo

    def fetch(self, *extra):
        fetcher().main(["--study", str(self.study), "--doc", str(self.doc), "--published", str(self.published),
                        "--out", str(self.out), *extra])
        return json.loads((self.out / "MANIFEST.json").read_text()), json.loads((self.out / "facts.json").read_text())

    def assertRefuses(self, reason, *extra):
        with self.assertRaisesRegex(SystemExit, reason):
            self.fetch(*extra)
        self.assertFalse(self.out.exists(), "a refused fetch wrote a snapshot")

    def test_refuses_dirty_tree(self):
        (self.study / "harness/collect.sh").write_text("edited\n")
        self.assertRefuses("uncommitted")
        self.assertRefuses("uncommitted", "--sha", self.head[:7])
        self.git(self.study, "checkout", "--", "harness/collect.sh")
        (self.study / "untracked.txt").write_text("new\n")
        self.assertRefuses("uncommitted")
        (self.study / "untracked.txt").unlink()
        # The methods doc lives in another repo, so its own edits refuse too.
        self.doc.write_text("edited\n")
        self.assertRefuses("uncommitted")

    def test_refuses_foreign_sha(self):
        self.assertRefuses("is not .* HEAD", "--sha", "0000000")
        old = self.head
        (self.study / "docs/SPEC.md").write_text("# Newer spec\n")
        self.git(self.study, *COMMIT, "newer", "docs/SPEC.md")
        # An older commit is foreign too: the checkout must stand at the pinned commit.
        self.assertRefuses("is not .* HEAD", "--sha", old[:7])

    def test_drops_host_paths(self):
        _, facts = self.fetch()
        run = facts["runs"]["full-1"]
        self.assertEqual(run, {"tag": "full-1", "model": "opus", "effort": "medium",
                               "doc_sha256": "6460695052da555ae469d575fbe2ce5b3ae57df5825abf102a290ce4e65cba21",
                               "notes": ["kept note"], "caps": {"iterations": 15, "cycles": 15, "starts": 3},
                               "methods": {"classic": {"method": "Classic greedy TDD",
                                                       "steps": ["List test scenarios.", "Pick the smallest one."]}}})
        self.assertEqual([s for s in strings(facts) if fetcher().HOST_PATH.search(s) and "://" not in s], [])
        self.assertNotIn(str(self.root), (self.out / "facts.json").read_text() + (self.out / "MANIFEST.json").read_text())
        self.assertEqual(facts["dropped"], {
            "full-1": ["clones_dir", "methods.<key>", "methods.classic.home", "notes[1]", "notes[2]", "split"],
            "rep-2/rebuild": ["blind_dir", "harness_delta.path"]})

    def test_refuses_dropping_prose(self):
        # HOST_PATH's drive-letter branch also matches prose such as a review summary.
        args = json.loads(fixture("args.json"))
        args["summary"] = "E: distinct PMD findings per file"
        (self.study / "runs/full-1/args.json").write_text(json.dumps(args))
        self.git(self.study, *COMMIT, "prose", "runs/full-1/args.json")
        self.assertRefuses("full-1 drops summary, which holds no path")

    def test_redacts_local_paths(self):
        page = "runs/full-1/methods/classic.html"
        kept = ('<a href="https://example.com/Users/x">site</a> <a href="/studies/kalah-tdd-study/">study</a> '
                'E: distinct PMD findings. Marker ~ stays.')
        # A path with a space has no knowable end, so the fetch refuses it.
        (self.study / page).write_text(fixture("classic.html").decode() + "<p>/Users/x/My Docs/secret/file.txt</p>\n")
        self.git(self.study, *COMMIT, "spaced path", page)
        self.assertRefuses("split at a space")
        (self.study / page).write_text(
            fixture("classic.html").decode() + '<td class="brk">~/.claude/projects/-Users-x/1a2b/tool-results/b.txt</td>'
            "<p>See /Users/someone/project/run.md. Or C:\\Users\\someone\\split.sh, then Obi-Done/Claude/Notes.</p>"
            "<p>Session -Users-echo-project-COMPSCI-701 and -home-someone-x.</p>" + kept + "\n")
        self.git(self.study, *COMMIT, "paths", page)
        manifest, facts = self.fetch()
        data = (self.out / page).read_bytes()
        self.assertEqual(data.decode(), fixture("classic.html").decode()
                         + '<td class="brk">&lt;local path&gt;</td><p>See &lt;local path&gt;. Or &lt;local path&gt;, '
                           "then &lt;local path&gt;.</p><p>Session &lt;local path&gt; and &lt;local path&gt;.</p>"
                         + kept + "\n")
        self.assertEqual(facts["redacted"], {page: 6})
        self.assertEqual(manifest["files"][page]["sha256"], sha256(data))

    def test_redacts_local_paths_in_facts(self):
        self.doc.write_text(fixture("tdd-methodologies.md").decode().replace("Greedy.", "Greedy, see ~/notes/classic.md."))
        self.git(self.doc.parent, *COMMIT, "path", self.doc.name)
        _, facts = self.fetch()
        self.assertEqual(facts["analysis"]["methodologies"][1]["text"], "Greedy, see <local path>.")
        self.assertEqual(facts["redacted"], {"facts.json": 1})

    def test_host_path_pattern_follows_render(self):
        (self.study / "harness/report/render.py").write_text(fixture("render.py").decode().replace("|Cryptomator", ""))
        self.git(self.study, *COMMIT, "narrower", "harness/report/render.py")
        self.assertRefuses("HOST_PATH differs")

    def test_manifest_matches(self):
        manifest, _ = self.fetch()
        self.assertEqual(manifest["sha"], self.head)
        self.assertEqual(manifest["published"], "kalah-tdd-experiment/raw/v1-abcd")
        files = manifest["files"]
        copied = ["runs/full-1/report.html", "runs/full-1/methods/classic.html", "runs/full-1/methods/outside-in.html",
                  "artifact/showcase.html"]
        self.assertEqual(sorted(files), sorted(copied + ["facts.json"]))
        for path in copied:
            data = fixture(SOURCES[path])
            self.assertEqual((self.out / path).read_bytes(), data, path)
            self.assertEqual((files[path]["bytes"], files[path]["sha256"]), (len(data), sha256(data)), path)
        self.assertEqual(files["runs/full-1/report.html"]["published_sha256"], sha256(fixture("report.html")))
        for name in ("classic.html", "outside-in.html"):
            self.assertEqual(files[f"runs/full-1/methods/{name}"]["published_sha256"],
                             sha256((self.published / "methods" / name).read_bytes()), name)
        self.assertIsNone(files["artifact/showcase.html"]["published_sha256"])
        self.assertEqual(files["facts.json"]["sha256"], sha256((self.out / "facts.json").read_bytes()))
        self.assertEqual(manifest["doc"]["sha256"], sha256(fixture("tdd-methodologies.md")))
        self.assertEqual(manifest["doc"]["sha"], self.git(self.doc.parent, "rev-parse", "HEAD"))

    def test_drops_stale_pages(self):
        self.fetch()
        stale = self.out / "runs/full-1/methods/gone.html"
        stale.write_text("dropped upstream\n")
        manifest, _ = self.fetch()
        self.assertFalse(stale.exists(), "a page tdd-experiment dropped lingers")
        self.assertNotIn("runs/full-1/methods/gone.html", manifest["files"])

    def test_refuses_foreign_out(self):
        # Only a snapshot the fetcher wrote may be replaced.
        self.out.mkdir(parents=True)
        (self.out / "keep.txt").write_text("mine\n")
        with self.assertRaisesRegex(SystemExit, "has no MANIFEST.json"):
            self.fetch()
        self.assertEqual([p.name for p in self.out.iterdir()], ["keep.txt"])
        self.out = self.root / "elsewhere"
        self.out.mkdir()
        (self.out / "MANIFEST.json").write_text("{}\n")
        with self.assertRaisesRegex(SystemExit, "outside _snapshots"):
            self.fetch()
        self.assertEqual([p.name for p in self.out.iterdir()], ["MANIFEST.json"])

    def test_manifest_bytes_are_lf(self):
        # Text writes on Windows turn \n into \r\n, as this patch does.
        real = Path.write_text
        crlf = lambda path, text, encoding=None, errors=None, newline=None: real(path, text, encoding, errors, "\r\n")
        with mock.patch.object(Path, "write_text", crlf):
            manifest, _ = self.fetch()
        self.assertEqual((self.out / "MANIFEST.json").read_bytes(), (json.dumps(manifest, indent=2) + "\n").encode())

    def test_refuses_missing_published_copy(self):
        (self.published / "methods/classic.html").unlink()
        self.assertRefuses("backup .* lacks")

    def test_extracts_facts(self):
        _, facts = self.fetch()
        self.assertEqual(facts["sha"], self.head)
        self.assertEqual(facts["stages"], json.loads(fixture("stages.json")))
        # The rebuilt replicates ran at another harness commit.
        self.assertEqual(sorted(facts["runs"]), ["full-1", "rep-2/rebuild"])
        self.assertEqual(facts["runs"]["rep-2/rebuild"], {
            "tag": "rep-2", "methods": {"rep-2-r04": {"method": "Held-out TDD"}}, "waves": [["rep-2-r04"]],
            "harness": {"commit": "cc8c8cbb06373ce400666528458a349eb0ae4d7a"},
            "harness_delta": {"sha256": "8fde5d73aecf82700e53426dcbca82f2bd86cc1a421e20fa57f0176d86958cdf"}})
        step = lambda name, skippable=False: {"name": name, "skippable": skippable}
        self.assertEqual(facts["pipeline"], {
            "collect": {"collectOne": [step("fetchBack"), step("export", True), step("review"), step("report")],
                        "collectList": [step("fetchBack"), step("list", True)]},
            "notation": "Once means one agent runs the steps. Tag: verified.",
            "weight_text": "Weighted tokens count input 1 and output 5 per token. These state no dollar cost."})
        analysis = facts["analysis"]
        self.assertEqual(analysis["criteria"], [
            {"name": "cost_effective", "doc": None, "returns": "record['m'] if record['full'] else None"},
            {"name": "fewest_errors", "doc": "E, lower first.", "returns": "record['e']"}])
        self.assertEqual(analysis["awards"], [
            {"title": "Best overall", "rule": "Lowest plain sum of ranks. Cheapest never counts."},
            {"title": "Most consistent design", "rule": "Lowest C. Variance p {spread['p']:.3f}."}])
        self.assertEqual(analysis["constants"], {"TOP": 3, "MEDALS": ["gold", "silver", "bronze"], "CLEAN_MEDIAN": 4})
        self.assertEqual(analysis["stats"], [
            {"name": "holm", "doc": "Holm step-down adjusted p values in the order of ps, each capped at 1."},
            {"name": "spearman_test", "doc": None}])
        self.assertEqual(analysis["methodologies"], [
            {"level": 1, "title": "TDD methodologies", "text": "Twelve designs."},
            {"level": 2, "title": "Classic", "text": "Greedy."}])
        self.assertEqual(analysis["spec"], [
            {"level": 1, "title": "Kalah spec", "text": "The task."},
            {"level": 2, "title": "Board", "text": "Six pits a side.\n\n```\n# not a heading\n```"}])


class CommittedSnapshot(unittest.TestCase):
    """The committed snapshot is the fetcher's output, unedited."""

    def setUp(self):
        self.manifest = json.loads((SNAPSHOT / "MANIFEST.json").read_text())

    def test_manifest_matches(self):
        files = self.manifest["files"]
        on_disk = sorted(p.relative_to(SNAPSHOT).as_posix() for p in SNAPSHOT.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
        self.assertEqual(on_disk, sorted(files))
        for path, entry in files.items():
            data = (SNAPSHOT / path).read_bytes()
            self.assertEqual((len(data), sha256(data)), (entry["bytes"], entry["sha256"]), path)
        self.assertRegex(self.manifest["sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(json.loads((SNAPSHOT / "facts.json").read_text())["sha"], self.manifest["sha"])

    def test_bytes_survive_autocrlf(self):
        paths = [(FIXTURES / "args.json.fixture").relative_to(SCRIPTS.parent).as_posix(),
                 (SNAPSHOT / "facts.json").relative_to(SCRIPTS.parent).as_posix()]
        attrs = subprocess.run(["git", "-C", str(SCRIPTS.parent), "check-attr", "text", "--", *paths],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(attrs.splitlines(), [f"{p}: text: unset" for p in paths])

    def test_drops_host_paths(self):
        runs = json.loads((SNAPSHOT / "facts.json").read_text())["runs"]
        self.assertTrue(runs)
        self.assertEqual([s for s in strings(runs) if fetcher().HOST_PATH.search(s)], [])

    def test_holds_no_local_paths(self):
        # The repository is public, so no snapshot file may name a path on the machine that fetched it.
        hits = [(str(p.relative_to(SNAPSHOT)), m.group(0)) for p in sorted(SNAPSHOT.rglob("*")) if p.is_file()
                for m in fetcher().LOCAL_PATH.finditer(p.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])

    def test_drops_only_path_fields(self):
        # A new dropped field may be prose HOST_PATH caught; look at it before adding it here.
        facts = json.loads((SNAPSHOT / "facts.json").read_text())
        dropped = facts["dropped"]
        self.assertEqual(sorted(dropped), sorted(facts["runs"]))
        self.assertEqual({p for paths in dropped.values() for p in paths if p.split(".")[-1] not in PATH_FIELDS}, set())


if __name__ == "__main__":
    unittest.main()
