"""Parse marker-pdf's HTML output into our ``ExtractedContent`` model.

Marker emits semantic HTML: headings (``<h1>``..``<h6>``), paragraphs,
lists (``<ul>``/``<ol>``), tables, ``<pre><code>`` blocks, and
``<img>`` references. Math is left inline as LaTeX in ``\\(...\\)`` /
``\\[...\\]`` which we preserve verbatim inside paragraph text.

The parser is deliberately forgiving — unknown tags fall through as
paragraph text so we never drop content.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from ..models import (
    Block,
    CodeBlock,
    ExtractedContent,
    Figure,
    FigureRef,
    ListBlock,
    MathBlock,
    ParagraphBlock,
    Section,
    TableBlock,
)

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SLUG_STRIP = re.compile(r"[^\w\s-]", flags=re.UNICODE)
_SLUG_SPACE = re.compile(r"[\s_]+")
_DISPLAY_MATH = re.compile(r"\\\[(.+?)\\\]", flags=re.DOTALL)


def parse_marker_html(
    raw_html: str,
    *,
    figure_asset_map: dict[str, Path],
    document_stem: str,
) -> ExtractedContent:
    soup = BeautifulSoup(raw_html, "html.parser")

    title = _infer_title(soup)
    sections: list[Section] = []
    figures: list[Figure] = []
    used_ids: set[str] = set()
    figure_counter = 0

    current: Section | None = None

    def ensure_section() -> Section:
        nonlocal current
        if current is None:
            current = Section(id=_unique_slug("content", used_ids), level=1, heading="")
            sections.append(current)
        return current

    for element in _iter_top_level(soup):
        if not isinstance(element, Tag):
            continue

        if element.name in _HEADING_TAGS:
            heading_text = _clean_text(element.get_text(" ", strip=True))
            if not heading_text:
                continue
            level = int(element.name[1])
            current = Section(
                id=_unique_slug(heading_text, used_ids),
                level=level,
                heading=heading_text,
            )
            sections.append(current)
            continue

        section = ensure_section()
        blocks, new_figures = _element_to_blocks(
            element,
            figure_asset_map=figure_asset_map,
            figure_counter=figure_counter,
            document_stem=document_stem,
        )
        for block in blocks:
            section.blocks.append(block)
        figures.extend(new_figures)
        figure_counter += len(new_figures)

    page_count = _count_pages(soup)

    return ExtractedContent(
        title=title,
        sections=sections,
        figures=figures,
        page_count=page_count,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_top_level(soup: BeautifulSoup):
    """Yield content-bearing elements, preferring ``<body>`` when present."""
    body = soup.body or soup
    yield from body.children


def _infer_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip() or None
    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text(" ", strip=True)) or None
    return None


def _element_to_blocks(
    element: Tag,
    *,
    figure_asset_map: dict[str, Path],
    figure_counter: int,
    document_stem: str,
) -> tuple[list[Block], list[Figure]]:
    name = element.name
    new_figures: list[Figure] = []

    if name == "p":
        # Split out display math as its own MathBlock; keep rest as paragraph.
        return _split_paragraph_math(element), new_figures

    if name in {"ul", "ol"}:
        items = [_clean_text(li.get_text(" ", strip=True)) for li in element.find_all("li", recursive=False)]
        items = [i for i in items if i]
        if items:
            return [ListBlock(items=items, ordered=(name == "ol"))], new_figures
        return [], new_figures

    if name == "pre":
        code_el = element.find("code")
        code_text = (code_el or element).get_text()
        language = None
        if code_el and code_el.get("data-lang"):
            language = str(code_el["data-lang"])
        elif code_el and code_el.get("class"):
            for cls in code_el.get("class") or []:
                if cls.startswith("language-"):
                    language = cls[len("language-"):]
                    break
        return [CodeBlock(code=code_text.rstrip("\n"), language=language)], new_figures

    if name == "table":
        header, rows = _parse_table(element)
        return [TableBlock(header=header, rows=rows)], new_figures

    if name == "figure":
        img = element.find("img")
        caption_el = element.find("figcaption")
        caption = _clean_text(caption_el.get_text(" ", strip=True)) if caption_el else None
        if img and img.get("src"):
            figure = _make_figure(
                src=str(img["src"]),
                alt=img.get("alt") or caption or "figure",
                page=_infer_page_from_src(str(img["src"])),
                figure_asset_map=figure_asset_map,
                figure_index=figure_counter + 1,
                document_stem=document_stem,
            )
            if figure is not None:
                new_figures.append(figure)
                return [FigureRef(figure_id=figure.id, caption=caption)], new_figures
        return [], new_figures

    if name == "img":
        figure = _make_figure(
            src=str(element.get("src", "")),
            alt=element.get("alt") or "figure",
            page=_infer_page_from_src(str(element.get("src", ""))),
            figure_asset_map=figure_asset_map,
            figure_index=figure_counter + 1,
            document_stem=document_stem,
        )
        if figure is not None:
            new_figures.append(figure)
            return [FigureRef(figure_id=figure.id, caption=None)], new_figures
        return [], new_figures

    # Unknown / wrapper tags → treat as paragraph.
    text = _clean_text(element.get_text(" ", strip=True))
    if text:
        return [ParagraphBlock(text=text)], new_figures
    return [], new_figures


def _split_paragraph_math(paragraph: Tag) -> list[Block]:
    html_text = paragraph.decode_contents()
    pieces = _DISPLAY_MATH.split(html_text)
    # re.split with a capturing group yields: [before, match, after, match, ...]
    if len(pieces) == 1:
        text = _clean_text(paragraph.get_text(" ", strip=True))
        return [ParagraphBlock(text=text)] if text else []

    blocks: list[Block] = []
    for idx, chunk in enumerate(pieces):
        if idx % 2 == 1:
            latex = chunk.strip()
            if latex:
                blocks.append(MathBlock(latex=latex))
        else:
            sub = BeautifulSoup(chunk, "html.parser")
            text = _clean_text(sub.get_text(" ", strip=True))
            if text:
                blocks.append(ParagraphBlock(text=text))
    return blocks


def _parse_table(table: Tag) -> tuple[list[str], list[list[str]]]:
    header: list[str] = []
    rows: list[list[str]] = []

    thead = table.find("thead")
    if thead:
        head_row = thead.find("tr")
        if head_row:
            header = [_clean_text(c.get_text(" ", strip=True)) for c in head_row.find_all(["th", "td"])]

    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = [_clean_text(c.get_text(" ", strip=True)) for c in cells]
        if not header and all(c.name == "th" for c in cells):
            header = row
            continue
        rows.append(row)

    return header, rows


def _make_figure(
    *,
    src: str,
    alt: str,
    page: int,
    figure_asset_map: dict[str, Path],
    figure_index: int,
    document_stem: str,
) -> Figure | None:
    src_key = src.split("/")[-1]  # marker uses bare filenames
    asset_path = figure_asset_map.get(src_key) or figure_asset_map.get(src)
    if asset_path is None:
        return None
    suffix = asset_path.suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")
    fig_id = f"{document_stem}_p{page}_fig{figure_index}"
    return Figure(id=fig_id, asset_path=asset_path, mime=mime, alt=alt, page=page)


_PAGE_FROM_SRC = re.compile(r"p(?:age)?[-_]?(\d+)", flags=re.IGNORECASE)


def _infer_page_from_src(src: str) -> int:
    match = _PAGE_FROM_SRC.search(src)
    return int(match.group(1)) if match else 0


def _count_pages(soup: BeautifulSoup) -> int:
    sections = soup.find_all(attrs={"data-page": True})
    if sections:
        try:
            return max(int(s["data-page"]) for s in sections)
        except (ValueError, TypeError):
            pass
    return 0


def _clean_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _unique_slug(text: str, used: set[str]) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    slug = _SLUG_STRIP.sub("", normalized)
    slug = _SLUG_SPACE.sub("-", slug).strip("-") or "section"
    candidate = slug
    n = 2
    while candidate in used:
        candidate = f"{slug}-{n}"
        n += 1
    used.add(candidate)
    return candidate
