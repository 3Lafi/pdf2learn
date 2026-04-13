"""Image-only / no-text PDFs fail with exit code 3 (T037)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2learn.config import Config
from pdf2learn.extract.marker_engine import ImageOnlyPDFError
from pdf2learn.orchestrator import run_job


def test_image_only_pdf_sets_exit_code_three_and_writes_log(
    fake_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(*_args, **_kwargs):
        raise ImageOnlyPDFError("no extractable text in sample.pdf")

    monkeypatch.setattr("pdf2learn.orchestrator.extract", _fail)

    config = Config(output_root=tmp_path / "out", quiet=True)
    job = run_job(fake_pdf, config=config)

    assert job.status == "failed"
    assert job.exit_code == 3
    assert job.log_path is not None
    assert job.log_path.is_file()
    log_text = job.log_path.read_text(encoding="utf-8")
    assert "no extractable text" in log_text
    # HTML should not have been produced on failure.
    assert not (job.output_dir / "index.html").exists()
