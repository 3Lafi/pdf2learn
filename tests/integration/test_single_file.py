"""End-to-end orchestrator test with extraction stubbed (T034)."""

from __future__ import annotations

from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import run_job


def test_single_file_produces_html_log_and_assets(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    config = Config(output_root=tmp_path / "out", quiet=True)
    job = run_job(fake_pdf, config=config)

    assert job.status == "succeeded"
    assert job.exit_code == 0
    assert job.output_dir == tmp_path / "out" / "sample"
    assert (job.output_dir / "index.html").is_file()
    assert (job.output_dir / "conversion.log").is_file()
    assert (job.output_dir / "assets" / "style.css").is_file()
    assert (job.output_dir / "assets" / "toggle.js").is_file()

    log_text = (job.output_dir / "conversion.log").read_text(encoding="utf-8")
    assert "input:" in log_text
    assert "page(s)" in log_text

    html = (job.output_dir / "index.html").read_text(encoding="utf-8")
    assert "Sample Document" in html
    assert 'href="#introduction"' in html
    assert "Supporting detail here." in html
