"""Pins generated site data to one clean commit of a study checkout. Shared by the local-only generators."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Local paths and vault names. render.HOST_PATH also matches every https:// link and site-root href on a page.
LOCAL_PATH = re.compile(r"(?<![\w.-])(?:/(?:Users|home|private|tmp|mnt|Volumes|var/folders)/|~/)|(?<!\w)[A-Za-z]:[\\/]"
                        r"|Obi-Done|Cryptomator|file://")


def clean_head(study: Path, given: str | None) -> str | None:
    """Full study HEAD of a clean tree, which --sha must name. None where git cannot read the study but --sha is given."""
    git = lambda *a: subprocess.run(["git", "-C", str(study), *a], capture_output=True, text=True, check=True).stdout.strip()
    try:
        head = git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        if given:
            return None
        raise SystemExit(f"git cannot read {study}; pass --sha with the study commit")
    if git("status", "--porcelain"):
        raise SystemExit(f"{study} has uncommitted changes; the data must come from one commit")
    if given and not (len(given) >= 7 and head.startswith(given.lower())):
        raise SystemExit(f"--sha {given} is not {study} HEAD {head[:7]}")
    return head


def study_sha(study: Path, given: str | None) -> str:
    """Short study HEAD of a clean tree, or --sha. Where git cannot read the study, such as the study container, --sha stands alone."""
    head = clean_head(study, given)
    return given or head[:7]
