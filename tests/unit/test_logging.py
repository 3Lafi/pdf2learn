"""Unit tests for the per-job logging layer (T015)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pdf2learn.logging_ import get_logger, job_logging


def test_log_file_is_written_on_success(tmp_path: Path) -> None:
    log_path = tmp_path / "job" / "conversion.log"
    with job_logging(log_path) as log:
        log.info("hello")
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "hello" in content


def test_log_file_persists_after_exception(tmp_path: Path) -> None:
    log_path = tmp_path / "job" / "conversion.log"
    with pytest.raises(RuntimeError):
        with job_logging(log_path) as log:
            log.warning("about to fail")
            raise RuntimeError("boom")
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "about to fail" in content


def test_stdout_handler_suppressed_when_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    log_path = tmp_path / "conversion.log"
    with job_logging(log_path, quiet=True) as log:
        log.info("should not appear on stdout")
    captured = capsys.readouterr()
    assert "should not appear on stdout" not in captured.out
    assert "should not appear on stdout" not in captured.err


def test_stdout_handler_uses_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    log_path = tmp_path / "conversion.log"
    with job_logging(log_path) as log:
        log.info("progress line")
        log.warning("watch out")
        log.error("bad thing")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "[pdf2learn] progress line" in combined
    assert "[pdf2learn:warn] watch out" in combined
    assert "[pdf2learn:error] bad thing" in combined


def test_handlers_detach_after_context(tmp_path: Path) -> None:
    log_path = tmp_path / "conversion.log"
    logger = get_logger()
    before = list(logger.handlers)
    with job_logging(log_path):
        pass
    after = list(logger.handlers)
    assert before == after
