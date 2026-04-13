"""CLI unit tests (T039). Exercises exit codes per contracts/cli.md."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2learn.cli import app
from pdf2learn.extract.marker_engine import ExtractionError, ImageOnlyPDFError

runner = CliRunner()


def test_version_flag_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pdf2learn" in result.output


def test_missing_input_exits_two(tmp_path: Path) -> None:
    missing = tmp_path / "nope.pdf"
    result = runner.invoke(app, [str(missing)])
    assert result.exit_code == 2


def test_non_pdf_file_exits_two(tmp_path: Path) -> None:
    not_pdf = tmp_path / "readme.txt"
    not_pdf.write_text("hi", encoding="utf-8")
    result = runner.invoke(app, [str(not_pdf)])
    assert result.exit_code == 2


def test_empty_directory_exits_two(tmp_path: Path) -> None:
    empty = tmp_path / "nopdfs"
    empty.mkdir()
    result = runner.invoke(app, [str(empty)])
    assert result.exit_code == 2


def test_successful_single_file_exits_zero(
    fake_pdf: Path, tmp_path: Path, stub_extract
) -> None:
    result = runner.invoke(
        app,
        [str(fake_pdf), "--output-dir", str(tmp_path / "out"), "--quiet"],
    )
    assert result.exit_code == 0
    assert len(stub_extract) == 1
    assert (tmp_path / "out" / "sample" / "index.html").is_file()


def test_image_only_pdf_exits_three(
    fake_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(*_args, **_kwargs):
        raise ImageOnlyPDFError("no text")

    monkeypatch.setattr("pdf2learn.orchestrator.extract", _fail)
    result = runner.invoke(
        app,
        [str(fake_pdf), "--output-dir", str(tmp_path / "out"), "--quiet"],
    )
    assert result.exit_code == 3


def test_extraction_error_exits_four(
    fake_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(*_args, **_kwargs):
        raise ExtractionError("marker blew up")

    monkeypatch.setattr("pdf2learn.orchestrator.extract", _fail)
    result = runner.invoke(
        app,
        [str(fake_pdf), "--output-dir", str(tmp_path / "out"), "--quiet"],
    )
    assert result.exit_code == 4
