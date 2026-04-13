"""Shared pytest fixtures for pdf2learn tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2learn.models import ExtractedContent, ParagraphBlock, Section


@pytest.fixture
def tmp_output_root(tmp_path: Path) -> Path:
    """A fresh, writable output root for a single test."""
    root = tmp_path / "output"
    root.mkdir()
    return root


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """A zero-byte file with a ``.pdf`` extension for orchestrator-level tests.

    Integration tests stub out extraction, so the file contents are never read.
    """
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4 stub\n")
    return path


@pytest.fixture
def canned_content() -> ExtractedContent:
    """A small, realistic ``ExtractedContent`` used by stubbed-extract tests."""
    return ExtractedContent(
        title="Sample Document",
        sections=[
            Section(
                id="introduction",
                level=1,
                heading="Introduction",
                blocks=[ParagraphBlock(text="The canonical opening sentence.")],
            ),
            Section(
                id="body",
                level=2,
                heading="Body",
                blocks=[ParagraphBlock(text="Supporting detail here.")],
            ),
        ],
        page_count=3,
    )


@pytest.fixture
def stub_extract(monkeypatch: pytest.MonkeyPatch, canned_content: ExtractedContent):
    """Replace ``orchestrator.extract`` with a function returning ``canned_content``.

    Yields the stub so tests can inspect call counts or vary behavior.
    """
    calls: list[dict] = []

    def _stub(pdf_path: Path, *, asset_dir: Path, **_kw) -> ExtractedContent:
        calls.append({"pdf_path": pdf_path, "asset_dir": asset_dir})
        asset_dir.mkdir(parents=True, exist_ok=True)
        return canned_content

    monkeypatch.setattr("pdf2learn.orchestrator.extract", _stub)
    return calls
