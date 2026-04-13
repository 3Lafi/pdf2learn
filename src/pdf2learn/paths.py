"""Filesystem path helpers.

Two responsibilities:

1. Safe slugification of arbitrary PDF filenames, including Unicode, spaces,
   and unusual punctuation (FR-014).
2. Output-directory resolution honoring the re-run rules from FR-016 / R8:
   default to a timestamped subdirectory when a collision exists; overwrite
   in place only when ``force=True``.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

_SLUG_STRIP_RE = re.compile(r"[^\w\s.-]", flags=re.UNICODE)
_SLUG_DASH_RE = re.compile(r"[\s_]+")
_SLUG_COLLAPSE_RE = re.compile(r"-{2,}")


def slugify_basename(filename: str) -> str:
    """Turn an arbitrary filename (with or without extension) into a safe directory name.

    Preserves Unicode letters where possible, collapses whitespace and punctuation
    to single dashes, strips leading/trailing dashes. Always returns a non-empty
    string — falls back to ``"pdf"`` for pathological input.
    """
    stem = Path(filename).stem
    normalized = unicodedata.normalize("NFKC", stem)
    cleaned = _SLUG_STRIP_RE.sub("-", normalized)
    cleaned = _SLUG_DASH_RE.sub("-", cleaned)
    cleaned = _SLUG_COLLAPSE_RE.sub("-", cleaned)
    cleaned = cleaned.strip("-.")
    return cleaned or "pdf"


def timestamp(now: datetime | None = None) -> str:
    """Sortable timestamp string used for collision-avoiding subdirectories."""
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def resolve_output_dir(
    output_root: Path,
    input_basename: str,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> Path:
    """Compute the per-job output directory, honoring FR-016.

    - Fresh target: ``<output_root>/<slug>/``.
    - Collision + ``force=False``: ``<output_root>/<slug>/<YYYYMMDD-HHMMSS>/``.
    - Collision + ``force=True``: ``<output_root>/<slug>/`` after ``rmtree``.

    The directory is created before return. Parents are created as needed.
    """
    slug = slugify_basename(input_basename)
    base = output_root / slug

    if base.exists():
        if force:
            shutil.rmtree(base)
            base.mkdir(parents=True)
            return base
        versioned = base / timestamp(now)
        versioned.mkdir(parents=True, exist_ok=False)
        return versioned

    base.mkdir(parents=True)
    return base
