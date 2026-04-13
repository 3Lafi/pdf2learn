"""Render ``ExtractedContent`` into a self-contained HTML document.

Uses Jinja2 with templates in ``pdf2learn/render/templates/``. Static
assets (``style.css``, ``toggle.js``, the KaTeX bundle if vendored) are
copied from ``pdf2learn/assets/`` into the job's ``asset_dir`` alongside
any extracted figures.

The template is intentionally minimal here; learning-optimized styling
and progressive-enhancement affordances (T045–T049) are layered in
Phase 7 without changing this module's interface.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import ExtractedContent, RenderedDocument, TocEntry

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def render(
    content: ExtractedContent,
    *,
    output_dir: Path,
    document_stem: str,
) -> RenderedDocument:
    """Produce ``<output_dir>/index.html`` + populated ``assets/``."""
    asset_dir = output_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    _copy_static_assets(asset_dir)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["isinstance"] = isinstance
    template = env.get_template("base.html.j2")

    toc = [
        TocEntry(id=s.id, heading=s.heading, level=s.level)
        for s in content.sections
        if s.heading
    ]

    html = template.render(
        title=content.title or document_stem,
        content=content,
        toc=toc,
        figure_rel=_figure_rel_paths(content, asset_dir),
    )

    html_path = output_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    return RenderedDocument(html_path=html_path, asset_dir=asset_dir, toc=toc)


def _copy_static_assets(asset_dir: Path) -> None:
    """Copy ``style.css`` and ``toggle.js`` into the job's asset dir."""
    for name in ("style.css", "toggle.js"):
        src = _STATIC_ASSETS_DIR / name
        if src.is_file():
            shutil.copy2(src, asset_dir / name)


def _figure_rel_paths(content: ExtractedContent, asset_dir: Path) -> dict[str, str]:
    """Map figure id → relative href usable inside the produced HTML."""
    mapping: dict[str, str] = {}
    for fig in content.figures:
        try:
            rel = fig.asset_path.relative_to(asset_dir.parent)
        except ValueError:
            rel = Path("assets") / fig.asset_path.name
        mapping[fig.id] = str(rel).replace("\\", "/")
    return mapping
