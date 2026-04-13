"""Unicode + space-containing input filenames (T026, FR-014)."""

from __future__ import annotations

from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import run_job


def test_filename_with_spaces_converts_cleanly(tmp_path: Path, stub_extract) -> None:
    pdf = tmp_path / "Lecture 01 - Intro.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub\n")
    config = Config(output_root=tmp_path / "out", quiet=True)

    job = run_job(pdf, config=config)

    assert job.exit_code == 0
    assert job.output_dir == tmp_path / "out" / "Lecture-01-Intro"
    assert (job.output_dir / "index.html").is_file()


def test_unicode_filename_does_not_crash(tmp_path: Path, stub_extract) -> None:
    pdf = tmp_path / "محاضرة 01.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub\n")
    config = Config(output_root=tmp_path / "out", quiet=True)

    job = run_job(pdf, config=config)

    assert job.exit_code == 0
    assert job.output_dir is not None
    assert job.output_dir.parent == tmp_path / "out"
    assert (job.output_dir / "index.html").is_file()
