"""In-memory data model shared across extract / render / orchestrator.

Mirrors `specs/011-pdf-html-learning/data-model.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# Content blocks (sum type via dataclasses + isinstance checks)
# ---------------------------------------------------------------------------


@dataclass
class ParagraphBlock:
    text: str


@dataclass
class ListBlock:
    items: list[str]
    ordered: bool = False


@dataclass
class CodeBlock:
    code: str
    language: str | None = None


@dataclass
class TableBlock:
    header: list[str]
    rows: list[list[str]]


@dataclass
class MathBlock:
    latex: str


@dataclass
class FigureRef:
    figure_id: str
    caption: str | None = None


Block = ParagraphBlock | ListBlock | CodeBlock | TableBlock | MathBlock | FigureRef


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


@dataclass
class Section:
    id: str
    level: int
    heading: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Figure:
    id: str
    asset_path: Path
    mime: str
    alt: str
    page: int


@dataclass
class ExtractedContent:
    title: str | None
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_text_length(self) -> int:
        """Sum of text content across paragraphs, list items, code, table cells."""
        total = 0
        for section in self.sections:
            total += len(section.heading)
            for block in section.blocks:
                if isinstance(block, ParagraphBlock):
                    total += len(block.text)
                elif isinstance(block, ListBlock):
                    total += sum(len(item) for item in block.items)
                elif isinstance(block, CodeBlock):
                    total += len(block.code)
                elif isinstance(block, TableBlock):
                    total += sum(len(c) for row in block.rows for c in row)
                    total += sum(len(c) for c in block.header)
                elif isinstance(block, MathBlock):
                    total += len(block.latex)
        return total


# ---------------------------------------------------------------------------
# Job + rendered output
# ---------------------------------------------------------------------------

JobStatus = Literal["pending", "running", "succeeded", "failed"]


@dataclass
class ConversionJob:
    input_path: Path
    output_root: Path
    force: bool = False
    output_dir: Path | None = None
    started_at: datetime | None = None
    status: JobStatus = "pending"
    exit_code: int = 0
    log_path: Path | None = None


@dataclass
class TocEntry:
    id: str
    heading: str
    level: int


@dataclass
class RenderedDocument:
    html_path: Path
    asset_dir: Path
    toc: list[TocEntry] = field(default_factory=list)
