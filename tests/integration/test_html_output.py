"""Rendered HTML structure checks (T050)."""

from __future__ import annotations

import re
from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import run_job


def test_toc_anchors_resolve_and_themes_present(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    config = Config(output_root=tmp_path / "out", quiet=True)
    job = run_job(fake_pdf, config=config)

    html = (job.output_dir / "index.html").read_text(encoding="utf-8")
    css = (job.output_dir / "assets" / "style.css").read_text(encoding="utf-8")

    # Every TOC href="#slug" must map to an element id="slug" in the body.
    hrefs = set(re.findall(r'href="#([^"]+)"', html))
    ids = set(re.findall(r'id="([^"]+)"', html))
    assert hrefs, "expected TOC hrefs in output"
    assert hrefs <= ids, f"dangling TOC anchors: {hrefs - ids}"

    # Both theme strategies shipped.
    assert "prefers-color-scheme: dark" in css
    assert 'data-theme="dark"' in css
    assert "@media print" in css

    # Semantic landmarks.
    assert "<nav" in html and "</nav>" in html
    assert "<main" in html and "</main>" in html
