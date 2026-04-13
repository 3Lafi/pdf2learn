"""Shared pytest fixtures for pdf2learn tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_output_root(tmp_path: Path) -> Path:
    """A fresh, writable output root for a single test."""
    root = tmp_path / "output"
    root.mkdir()
    return root
