#!/usr/bin/env python3
"""Snapshot the Kalah TDD study pages and the harness facts the site pages need into _snapshots/kalah-tdd-study.

Usage: fetch_kalah_tdd_snapshot.py --study <tdd-experiment> --doc <tdd-methodologies.md> --published <raw version dir>
       [--sha <sha>] [--out <dir>]
Local only, CI never runs this. Every study file comes from one clean tdd-experiment commit through git show.
--published is the artifacts backup version, such as artifacts/kalah-tdd-experiment/raw/v1793403855-d60f.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# python3 -I leaves the script folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from study_checkout import clean_head  # noqa: E402

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "_snapshots/kalah-tdd-study"
REPORT = "runs/full-1/report.html"
METHODS = "runs/full-1/methods"
SHOWCASE = "artifact/showcase.html"
RENDER = "harness/report/render.py"
# A copy of render.HOST_PATH, which the fetch checks: evidence a reader of the repo cannot open.
HOST_PATH = re.compile(r"^(/|~|[A-Za-z]:)|://|Obi-Done|Cryptomator")
STEP = re.compile(r"(?:^|\|\||&&)\s*(step|branchStep) ([A-Za-z]+)\b")
FUNCTION = re.compile(r"^([A-Za-z]\w*)\(\) \{")
HEADING = re.compile(r"^(#{1,6}) +(.*?) *#*$")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- copySources ----
def copy_sources(study: Path, sha: str) -> dict[str, bytes]:
    """{path: bytes} of the report, every method page and the showcase at sha."""
    methods = git(study, "ls-tree", "--name-only", f"{sha}:{METHODS}").decode().split()
    paths = [REPORT, *(f"{METHODS}/{name}" for name in sorted(methods) if name.endswith(".html")), SHOWCASE]
    return {path: git(study, "show", f"{sha}:{path}") for path in paths}


def committed_doc(path: Path) -> tuple[bytes, str]:
    """(bytes, repo HEAD) of a file as committed in its own repo, refusing uncommitted edits to it."""
    try:
        head = git(path.parent, "rev-parse", "HEAD").decode().strip()
        dirty = git(path.parent, "status", "--porcelain", "--", path.name)
        data = git(path.parent, "show", f"HEAD:./{path.name}")
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(f"git cannot read {path} as a committed file")
    if dirty:
        raise SystemExit(f"{path} has uncommitted changes; the doc must come from one commit")
    return data, head


# ---- writeManifest ----
def published_copy(published: Path, path: str) -> Path | None:
    """The backup of a page: the version's .html for the report, its methods folder for a method page."""
    if path == REPORT:
        return published.with_name(published.name + ".html")
    return published / "methods" / Path(path).name if path.startswith(METHODS + "/") else None


def manifest(sha: str, files: dict[str, bytes], facts: bytes, published: Path, doc: dict) -> dict:
    entries = {}
    for path, data in files.items():
        copy = published_copy(published, path)
        if copy and not copy.is_file():
            raise SystemExit(f"the artifacts backup {published.name} lacks {path}")
        entries[path] = {"bytes": len(data), "sha256": sha256(data),
                         "published_sha256": sha256(copy.read_bytes()) if copy else None}
    entries["facts.json"] = {"bytes": len(facts), "sha256": sha256(facts), "published_sha256": None}
    return {"source": "Quintuplin/tdd-experiment", "sha": sha,
            "published": f"{published.parent.parent.name}/{published.parent.name}/{published.name}",
            "doc": doc, "files": entries}


def write_snapshot(out: Path, files: dict[str, bytes], facts: bytes, found: dict) -> None:
    # A page tdd-experiment dropped must not linger, but only a snapshot this script wrote may be replaced.
    if out.exists():
        if out.resolve().parent.name != "_snapshots":
            raise SystemExit(f"{out} lies outside _snapshots/; remove it or pick a new --out")
        if not (out / "MANIFEST.json").is_file():
            raise SystemExit(f"{out} has no MANIFEST.json, so it is no snapshot; remove it or pick a new --out")
        shutil.rmtree(out)
    for path, data in {**files, "facts.json": facts}.items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_bytes(data)
    # Bytes, so Windows writes no \r\n.
    (out / "MANIFEST.json").write_bytes((json.dumps(found, indent=2) + "\n").encode())


# ---- FactExtract ----
def is_host_path(value) -> bool:
    return isinstance(value, str) and bool(HOST_PATH.search(value))


def drop_host_paths(value):
    """value without the strings HOST_PATH matches, as keys or values, at any depth."""
    if isinstance(value, dict):
        return {k: drop_host_paths(v) for k, v in value.items() if not (is_host_path(k) or is_host_path(v))}
    if isinstance(value, list):
        return [drop_host_paths(v) for v in value if not is_host_path(v)]
    return value


def assigned(tree: ast.Module) -> dict[str, ast.expr]:
    return {t.id: node.value for node in tree.body if isinstance(node, ast.Assign) for t in node.targets
            if isinstance(t, ast.Name)}


def summary(node) -> str | None:
    """A docstring's first paragraph on one line."""
    doc = ast.get_docstring(node)
    return " ".join(doc.split("\n\n")[0].split()) if doc else None


def defs(tree: ast.Module) -> list[dict]:
    return [{"name": node.name, "doc": summary(node)} for node in tree.body if isinstance(node, ast.FunctionDef)]


def text_of(node: ast.expr) -> str:
    """A string literal's text, with an f-string's fields kept as {expression:spec}."""
    if isinstance(node, ast.Constant):
        return node.value
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(value.value)
        else:
            spec = text_of(value.format_spec) if value.format_spec else ""
            parts.append("{" + ast.unparse(value.value) + (":" + spec if spec else "") + "}")
    return "".join(parts)


def literal(node: ast.expr):
    """A literal's value, with a tuple as the list JSON writes."""
    value = ast.literal_eval(node)
    return list(value) if isinstance(value, tuple) else value


def awards_facts(source: str) -> dict:
    tree = ast.parse(source)
    found = assigned(tree)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    returns = lambda f: next(ast.unparse(n.value) for n in ast.walk(f) if isinstance(n, ast.Return))
    criteria = [{"name": e.id, "doc": summary(functions[e.id]), "returns": returns(functions[e.id])}
                for e in found["CRITERIA"].elts]
    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "award" and isinstance(n.args[0], ast.Constant)),
                   key=lambda n: (n.lineno, n.col_offset))
    return {"criteria": criteria, "awards": [{"title": n.args[0].value, "rule": text_of(n.args[1])} for n in calls],
            "constants": {k: literal(found[k]) for k in ("TOP", "MEDALS", "CLEAN_MEDIAN")},
            "functions": defs(tree)}


def collect_steps(text: str) -> dict[str, list[dict]]:
    """{function: steps in call order} of collect.sh's step and branchStep calls. A branchStep is skipped after a
    failed fetchBack."""
    out, function = {}, None
    for line in text.splitlines():
        if match := FUNCTION.match(line):
            function = match.group(1)
        elif not line.lstrip().startswith("#"):
            for kind, name in STEP.findall(line):
                out.setdefault(function, []).append({"name": name, "skippable": kind == "branchStep"})
    return out


def sections(text: str) -> list[dict]:
    """[{level, title, text}] of a markdown file's headings outside code fences, each with its text."""
    out, fenced = [], False
    for line in text.splitlines():
        fenced ^= line.startswith("```")
        match = None if fenced or line.startswith("```") else HEADING.match(line)
        if match:
            out.append({"level": len(match.group(1)), "title": match.group(2), "lines": []})
        elif out:
            out[-1]["lines"].append(line)
    return [{"level": s["level"], "title": s["title"], "text": "\n".join(s.pop("lines")).strip()} for s in out]


def extract_facts(study: Path, sha: str, doc: bytes) -> dict:
    show = lambda path: git(study, "show", f"{sha}:{path}").decode()
    render = ast.parse(show(RENDER))
    found = assigned(render)
    if ast.literal_eval(found["HOST_PATH"].args[0]) != HOST_PATH.pattern:
        raise SystemExit(f"{RENDER} HOST_PATH differs from this script's copy; update the copy first")
    # Nested runs such as rep-2/rebuild record replicates rebuilt at another harness commit.
    runs = sorted(p for p in git(study, "ls-tree", "-r", "--name-only", sha, "--", "runs").decode().split()
                  if re.fullmatch(r"runs/.+/args\.json", p))
    return {"sha": sha, "stages": json.loads(show("harness/workflow/stages.json")),
            "runs": {p[len("runs/"):-len("/args.json")]: drop_host_paths(json.loads(show(p))) for p in runs},
            "pipeline": {"collect": collect_steps(show("harness/collect.sh")),
                         "notation": ast.literal_eval(found["NOTATION"]),
                         "weight_text": ast.literal_eval(found["WEIGHT_TEXT"])},
            "analysis": {**awards_facts(show("harness/report/awards.py")),
                         "stats": defs(ast.parse(show("harness/report/stats.py"))),
                         "methodologies": sections(doc.decode()), "spec": sections(show("docs/SPEC.md"))}}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", type=Path, required=True, help="tdd-experiment checkout at the pinned commit")
    parser.add_argument("--doc", type=Path, required=True, help="tdd-methodologies.md in its own repo")
    parser.add_argument("--published", type=Path, required=True, help="artifacts raw version dir of the report")
    parser.add_argument("--sha", help="tdd-experiment commit, which must be the checkout's HEAD")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    sha = clean_head(args.study, args.sha)
    if not sha:
        raise SystemExit(f"git cannot read {args.study}; the snapshot comes from its commits")
    doc, doc_sha = committed_doc(args.doc)
    files = copy_sources(args.study, sha)
    facts = (json.dumps(extract_facts(args.study, sha, doc), indent=1, ensure_ascii=False) + "\n").encode()
    doc_entry = {"path": args.doc.name, "sha": doc_sha, "sha256": sha256(doc)}
    write_snapshot(args.out, files, facts, manifest(sha, files, facts, args.published, doc_entry))
    print(f"wrote {args.out} from tdd-experiment {sha[:8]}")


if __name__ == "__main__":
    main()
