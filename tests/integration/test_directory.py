"""Directory + --recursive input handling (T035)."""

from __future__ import annotations

from pathlib import Path

from pdf2learn.config import Config
from pdf2learn.orchestrator import iter_pdfs, run_batch


def _make_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 stub\n")
    return path


def test_iter_pdfs_non_recursive_skips_subdirs(tmp_path: Path) -> None:
    root = tmp_path / "pdfs"
    _make_pdf(root / "top.pdf")
    _make_pdf(root / "nested" / "inner.pdf")

    found = iter_pdfs(root, recursive=False)
    assert [p.name for p in found] == ["top.pdf"]


def test_iter_pdfs_recursive_descends(tmp_path: Path) -> None:
    root = tmp_path / "pdfs"
    _make_pdf(root / "top.pdf")
    _make_pdf(root / "nested" / "inner.pdf")

    found = iter_pdfs(root, recursive=True)
    names = sorted(p.name for p in found)
    assert names == ["inner.pdf", "top.pdf"]


def test_run_batch_processes_every_pdf(tmp_path: Path, stub_extract) -> None:
    root = tmp_path / "pdfs"
    pdfs = [_make_pdf(root / f"doc{i}.pdf") for i in range(3)]
    config = Config(output_root=tmp_path / "out", quiet=True)

    exit_code = run_batch(pdfs, config=config)
    assert exit_code == 0
    assert len(stub_extract) == 3
    for pdf in pdfs:
        assert (tmp_path / "out" / pdf.stem / "index.html").is_file()
