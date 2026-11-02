"""Pins generated site data to one clean commit of a study checkout. Shared by the local-only generators."""

from __future__ import annotations

import subprocess
from pathlib import Path


def study_sha(study: Path, given: str | None) -> str:
    """Study HEAD of a clean tree, which --sha must name. Where git cannot read the study, such as the study container, --sha stands alone."""
    git = lambda *a: subprocess.run(["git", "-C", str(study), *a], capture_output=True, text=True, check=True).stdout.strip()
    try:
        head = git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        if given:
            return given
        raise SystemExit(f"git cannot read {study}; pass --sha with the study commit")
    if git("status", "--porcelain"):
        raise SystemExit(f"{study} has uncommitted changes; the data must come from one commit")
    if given and not (len(given) >= 7 and head.startswith(given.lower())):
        raise SystemExit(f"--sha {given} is not {study} HEAD {head[:7]}")
    return given or head[:7]
