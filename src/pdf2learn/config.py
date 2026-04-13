"""Configuration loader.

Zero hard-coded paths or course codes (FR-005). A ``config.yaml`` is optional;
all values have sensible defaults and every setting is overridable via the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    output_root: Path = Path("output")
    recursive: bool = False
    force: bool = False
    quiet: bool = False
    # Threshold (characters of extracted text) below which a PDF is treated as
    # image-only and the run fails with exit code 3 (FR-015 / R9).
    image_only_text_threshold: int = 200

    # Extraction engine: "llamaparse" (hosted API, default), "docling" (CPU), "marker" (GPU).
    engine: str = "llamaparse"
    # Quality / parse mode. For llamaparse: fast|cost_effective|agentic|agentic_plus.
    # For docling: fast|rich|scanned. Default is tuned for llamaparse.
    quality: str = "cost_effective"

    extra: dict = field(default_factory=dict)


DEFAULT_CONFIG_FILENAMES = ("pdf2learn.yaml", "pdf2learn.yml", "config.yaml")


def load_config(path: Path | None = None) -> Config:
    """Load configuration from an explicit path or search the CWD.

    Returns defaults if no config file is found. Never raises on absence;
    raises only if an explicitly-passed ``path`` cannot be read or parsed.
    """
    if path is not None:
        return _load_from_file(path)

    for candidate in DEFAULT_CONFIG_FILENAMES:
        candidate_path = Path.cwd() / candidate
        if candidate_path.is_file():
            return _load_from_file(candidate_path)

    return Config()


def _load_from_file(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file {path} must be a YAML mapping at the top level")

    cfg = Config()
    if "output_root" in raw:
        cfg.output_root = Path(raw["output_root"]).expanduser()
    if "recursive" in raw:
        cfg.recursive = bool(raw["recursive"])
    if "force" in raw:
        cfg.force = bool(raw["force"])
    if "quiet" in raw:
        cfg.quiet = bool(raw["quiet"])
    if "image_only_text_threshold" in raw:
        cfg.image_only_text_threshold = int(raw["image_only_text_threshold"])
    if "engine" in raw:
        cfg.engine = str(raw["engine"]).lower()
    if "quality" in raw:
        cfg.quality = str(raw["quality"]).lower()

    known = {
        "output_root",
        "recursive",
        "force",
        "quiet",
        "image_only_text_threshold",
        "engine",
        "quality",
    }
    cfg.extra = {k: v for k, v in raw.items() if k not in known}
    return cfg
