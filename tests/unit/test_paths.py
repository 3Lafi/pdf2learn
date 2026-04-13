"""Unit tests for slugification and output-dir resolution (T014)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pdf2learn.paths import resolve_output_dir, slugify_basename, timestamp


class TestSlugify:
    def test_simple_name(self) -> None:
        assert slugify_basename("lecture.pdf") == "lecture"

    def test_spaces_become_dashes(self) -> None:
        assert slugify_basename("CS348 - Chapter 01.pdf") == "CS348-Chapter-01"

    def test_unicode_preserved(self) -> None:
        # NFKC normalization keeps the word-character class happy.
        result = slugify_basename("محاضرة 01.pdf")
        assert result  # non-empty
        assert " " not in result

    def test_punctuation_stripped(self) -> None:
        assert slugify_basename("weird!!!name???.pdf") == "weird-name"

    def test_falls_back_to_default_for_empty(self) -> None:
        assert slugify_basename("???.pdf") == "pdf"

    def test_extension_ignored(self) -> None:
        assert slugify_basename("doc.PDF") == "doc"


class TestResolveOutputDir:
    def test_fresh_target_is_base_dir(self, tmp_output_root: Path) -> None:
        out = resolve_output_dir(tmp_output_root, "first.pdf")
        assert out == tmp_output_root / "first"
        assert out.is_dir()

    def test_collision_without_force_creates_timestamped_subdir(
        self, tmp_output_root: Path
    ) -> None:
        first = resolve_output_dir(tmp_output_root, "same.pdf")
        fake_now = datetime(2026, 4, 13, 14, 25, 30)
        second = resolve_output_dir(tmp_output_root, "same.pdf", now=fake_now)
        assert first.exists()  # preserved
        assert second == tmp_output_root / "same" / "20260413-142530"
        assert second.is_dir()

    def test_collision_with_force_overwrites_in_place(
        self, tmp_output_root: Path
    ) -> None:
        first = resolve_output_dir(tmp_output_root, "same.pdf")
        (first / "marker.txt").write_text("prior run", encoding="utf-8")
        second = resolve_output_dir(tmp_output_root, "same.pdf", force=True)
        assert second == first
        assert not (second / "marker.txt").exists()

    def test_two_pdfs_with_same_basename_do_not_collide_across_slugs(
        self, tmp_output_root: Path
    ) -> None:
        a = resolve_output_dir(tmp_output_root, "alpha.pdf")
        b = resolve_output_dir(tmp_output_root, "beta.pdf")
        assert a != b
        assert a.is_dir() and b.is_dir()


class TestTimestamp:
    def test_format(self) -> None:
        assert timestamp(datetime(2026, 1, 2, 3, 4, 5)) == "20260102-030405"
