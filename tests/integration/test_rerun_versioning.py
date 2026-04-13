"""Re-run semantics: timestamped subdir by default, --force overwrites (T036)."""

from __future__ import annotations

import time
from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import run_job


def test_second_run_without_force_writes_to_timestamped_subdir(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    config = Config(output_root=tmp_path / "out", quiet=True)
    first = run_job(fake_pdf, config=config)
    # Guarantee a distinct wall-clock second for the timestamp dir name.
    time.sleep(1.1)
    second = run_job(fake_pdf, config=config)

    assert first.output_dir == tmp_path / "out" / "sample"
    assert second.output_dir.parent == tmp_path / "out" / "sample"
    assert second.output_dir != first.output_dir
    assert (first.output_dir / "index.html").is_file()
    assert (second.output_dir / "index.html").is_file()


def test_force_overwrites_existing_directory(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    config = Config(output_root=tmp_path / "out", quiet=True)
    first = run_job(fake_pdf, config=config)
    # Drop a marker file; --force must wipe it.
    (first.output_dir / "stale.txt").write_text("old", encoding="utf-8")

    config.force = True
    second = run_job(fake_pdf, config=config)

    assert second.output_dir == first.output_dir
    assert not (second.output_dir / "stale.txt").exists()
    assert (second.output_dir / "index.html").is_file()
