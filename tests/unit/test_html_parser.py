"""Unit tests for the marker HTML → ExtractedContent parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2learn.extract.html_parser import parse_marker_html
from pdf2learn.models import (
    CodeBlock,
    FigureRef,
    ListBlock,
    MathBlock,
    ParagraphBlock,
    TableBlock,
)


def test_simple_heading_and_paragraph() -> None:
    html = "<h1>Intro</h1><p>Hello world.</p>"
    content = parse_marker_html(html, figure_asset_map={}, document_stem="doc")
    assert len(content.sections) == 1
    section = content.sections[0]
    assert section.heading == "Intro"
    assert section.id == "intro"
    assert section.level == 1
    assert isinstance(section.blocks[0], ParagraphBlock)
    assert section.blocks[0].text == "Hello world."


def test_duplicate_headings_get_unique_ids() -> None:
    html = "<h2>Notes</h2><p>a</p><h2>Notes</h2><p>b</p>"
    content = parse_marker_html(html, figure_asset_map={}, document_stem="doc")
    ids = [s.id for s in content.sections]
    assert ids == ["notes", "notes-2"]


def test_list_and_code_and_table() -> None:
    html = """
    <h1>Mix</h1>
    <ul><li>one</li><li>two</li></ul>
    <pre><code class="language-python">print('hi')</code></pre>
    <table>
        <thead><tr><th>a</th><th>b</th></tr></thead>
        <tbody><tr><td>1</td><td>2</td></tr></tbody>
    </table>
    """
    content = parse_marker_html(html, figure_asset_map={}, document_stem="doc")
    blocks = content.sections[0].blocks
    assert any(isinstance(b, ListBlock) and b.items == ["one", "two"] for b in blocks)
    code_block = next(b for b in blocks if isinstance(b, CodeBlock))
    assert code_block.language == "python"
    assert "print('hi')" in code_block.code
    table_block = next(b for b in blocks if isinstance(b, TableBlock))
    assert table_block.header == ["a", "b"]
    assert table_block.rows == [["1", "2"]]


def test_display_math_is_split_from_paragraph() -> None:
    html = r"<h1>Math</h1><p>Consider \[x^2 + y^2 = z^2\] this equation.</p>"
    content = parse_marker_html(html, figure_asset_map={}, document_stem="doc")
    blocks = content.sections[0].blocks
    kinds = [type(b).__name__ for b in blocks]
    assert "MathBlock" in kinds
    math_block = next(b for b in blocks if isinstance(b, MathBlock))
    assert "x^2" in math_block.latex


def test_figure_resolves_from_asset_map(tmp_path: Path) -> None:
    fig = tmp_path / "lecture_p3_fig1.png"
    fig.write_bytes(b"\x89PNG\r\n\x1a\nstub")
    html = '<h1>Pic</h1><figure><img src="lecture_p3_fig1.png" alt="a diagram"><figcaption>a diagram</figcaption></figure>'
    content = parse_marker_html(
        html,
        figure_asset_map={"lecture_p3_fig1.png": fig},
        document_stem="lecture",
    )
    assert len(content.figures) == 1
    assert content.figures[0].asset_path == fig
    assert content.figures[0].mime == "image/png"
    assert content.figures[0].page == 3
    figure_ref = next(b for b in content.sections[0].blocks if isinstance(b, FigureRef))
    assert figure_ref.figure_id == content.figures[0].id


def test_empty_document_produces_empty_sections() -> None:
    content = parse_marker_html("", figure_asset_map={}, document_stem="doc")
    assert content.sections == []
    assert content.figures == []
    assert content.total_text_length == 0
