"""Unit tests for the HTML renderer."""

from __future__ import annotations

from pathlib import Path

from pdf2learn.models import ExtractedContent, ParagraphBlock, Section
from pdf2learn.render.renderer import render


def _tiny_content() -> ExtractedContent:
    section = Section(
        id="hello",
        level=1,
        heading="Hello",
        blocks=[ParagraphBlock(text="World.")],
    )
    return ExtractedContent(title="Test Doc", sections=[section])


def test_renderer_writes_html_and_copies_assets(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    result = render(_tiny_content(), output_dir=out, document_stem="test")

    assert result.html_path == out / "index.html"
    html = result.html_path.read_text(encoding="utf-8")

    # Basic structure
    assert "<!doctype html>" in html.lower()
    assert '<title>Test Doc</title>' in html
    assert 'id="hello"' in html
    assert 'href="#hello"' in html  # TOC anchor
    assert "World." in html

    # Static assets copied into per-job asset dir
    assert (out / "assets" / "style.css").is_file()
    assert (out / "assets" / "toggle.js").is_file()


def test_toc_contains_only_headed_sections(tmp_path: Path) -> None:
    from pdf2learn.models import Section as S

    content = ExtractedContent(
        title="Doc",
        sections=[
            S(id="one", level=1, heading="One", blocks=[ParagraphBlock(text="a")]),
            S(id="anon", level=2, heading="", blocks=[ParagraphBlock(text="b")]),
            S(id="two", level=1, heading="Two", blocks=[ParagraphBlock(text="c")]),
        ],
    )
    result = render(content, output_dir=tmp_path, document_stem="test")
    assert {e.id for e in result.toc} == {"one", "two"}


def test_renderer_escapes_untrusted_text(tmp_path: Path) -> None:
    section = Section(
        id="xss",
        level=1,
        heading="<script>alert(1)</script>",
        blocks=[ParagraphBlock(text="<b>bold</b>")],
    )
    content = ExtractedContent(title="x", sections=[section])
    result = render(content, output_dir=tmp_path, document_stem="t")
    html = result.html_path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
