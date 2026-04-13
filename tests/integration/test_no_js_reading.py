"""Core reading works with JS disabled (T052, Q2 Session-2)."""

from __future__ import annotations

import re
from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import run_job


def test_toc_still_navigable_after_script_stripping(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    config = Config(output_root=tmp_path / "out", quiet=True)
    job = run_job(fake_pdf, config=config)

    html = (job.output_dir / "index.html").read_text(encoding="utf-8")
    no_js = re.sub(r"<script\b.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)

    hrefs = set(re.findall(r'href="#([^"]+)"', no_js))
    ids = set(re.findall(r'id="([^"]+)"', no_js))
    assert hrefs, "expected TOC even without JS"
    assert hrefs <= ids, f"broken anchors without JS: {hrefs - ids}"

    # Body content survives script removal.
    assert "<main" in no_js
    assert "doc-section" in no_js
