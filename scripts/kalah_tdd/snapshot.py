"""The committed tdd-experiment snapshot: its files checked against MANIFEST.json, and fragments cut from them."""

import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2] / "_snapshots/kalah-tdd-study"
REPORT = "runs/full-1/report.html"
SHOWCASE = "artifact/showcase.html"
# An id attribute, which data-id is not.
ID_ATTR = r'(?<![\w-])id="'
ID = re.compile(ID_ATTR + r'([^"]+)"')
# Only headings with an id end a section, as links.placed homes ids; figure titles in figcaption have none.
HEADING = re.compile(r'<h([1-6])\b[^>]*' + ID_ATTR)


class Snapshot(NamedTuple):
    sha: str
    run: str
    files: dict
    facts: dict


def load(root=ROOT):
    """Every manifest file as text, refused if any byte differs from its recorded sha256."""
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    files = {}
    for name, entry in manifest["files"].items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{root / name} does not match MANIFEST.json; fetch the snapshot again")
        files[name] = data.decode("utf-8")
    facts = json.loads(files.pop("facts.json"))
    if facts["sha"] != manifest["sha"]:
        raise SystemExit(f"facts.json is from {facts['sha']}, MANIFEST.json from {manifest['sha']}")
    return Snapshot(manifest["sha"], REPORT.split("/")[1], files, facts)


def section(html, id):
    """From the heading with this id up to the next heading with an id of the same or a higher level, or the end of main."""
    head = re.search(rf'<h([1-6])\b[^>]*{ID_ATTR}{re.escape(id)}"', html)
    if not head:
        raise ValueError(f"no heading with id {id}")
    level, main = int(head.group(1)), html.find("</main>", head.end())
    stop = main if main != -1 else len(html)
    end = next((m.start() for m in HEADING.finditer(html, head.end(), stop) if int(m.group(1)) <= level), stop)
    return html[head.start():end].strip()


def view(html, id):
    """The inside of the showcase view <main id=...>."""
    m = re.search(rf'<main\b[^>]*{ID_ATTR}{re.escape(id)}"[^>]*>(.*?)</main>', html, re.S)
    if not m:
        raise ValueError(f"no showcase view {id}")
    return m.group(1).strip()
