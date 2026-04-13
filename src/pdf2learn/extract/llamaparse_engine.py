"""LlamaParse-based extraction engine (hosted API, CPU-free).

LlamaParse runs in the cloud, so no local models, no GPU, no multi-GB
downloads. Handles scanned PDFs + math/tables reliably. Free tier:
10,000 credits/month ≈ 3,300 pages in "cost_effective" mode.

Requires a LlamaCloud API key:
    https://cloud.llamaindex.ai/  (free signup)

Set it via env var before running:
    Windows:  setx LLAMA_CLOUD_API_KEY "llx-..."
    macOS:    export LLAMA_CLOUD_API_KEY=llx-...
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..models import ExtractedContent
from .html_parser import parse_marker_html
from .marker_engine import ExtractionError, ImageOnlyPDFError

log = logging.getLogger(__name__)


def extract(
    pdf_path: Path,
    *,
    asset_dir: Path,
    image_only_text_threshold: int = 200,
    mode: str = "cost_effective",
) -> ExtractedContent:
    """Send ``pdf_path`` to LlamaParse and return a parsed ``ExtractedContent``.

    ``mode`` maps to LlamaParse v2 tiers: ``fast`` | ``cost_effective`` |
    ``agentic`` | ``agentic_plus`` (more accurate, more credits).
    """
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ExtractionError(
            "LLAMA_CLOUD_API_KEY not set. Get a free key at "
            "https://cloud.llamaindex.ai/ then set it in your environment."
        )

    try:
        from llama_cloud_services import LlamaParse  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "llama-cloud-services is not installed. "
            "Install it with `pip install llama-cloud-services`."
        ) from exc

    asset_dir.mkdir(parents=True, exist_ok=True)
    log.info("llamaparse extracting %s (mode=%s)", pdf_path.name, mode)

    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",
        parse_mode=mode,
        verbose=False,
    )

    try:
        result = parser.parse(str(pdf_path))
        markdown = _result_to_markdown(result)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"llamaparse failed on {pdf_path.name}: {exc}") from exc

    # Download images if the SDK surfaces them (it does for most PDFs).
    figure_asset_map = _save_images_from_result(result, asset_dir, stem=pdf_path.stem)

    html = _markdown_to_html(markdown)
    content = parse_marker_html(
        html,
        figure_asset_map=figure_asset_map,
        document_stem=pdf_path.stem,
    )

    if content.total_text_length < image_only_text_threshold:
        raise ImageOnlyPDFError(
            f"{pdf_path.name}: LlamaParse returned only "
            f"{content.total_text_length} chars. PDF appears empty."
        )

    log.info(
        "extracted %d section(s), %d figure(s), %d page(s)",
        len(content.sections),
        len(content.figures),
        content.page_count,
    )
    return content


def _result_to_markdown(result) -> str:
    """LlamaParse returns either a Document or list of Documents."""
    if hasattr(result, "get_markdown_documents"):
        docs = result.get_markdown_documents(split_by_page=False)
        if docs:
            return "\n\n".join(getattr(d, "text", "") or getattr(d, "md", "") for d in docs)
    if isinstance(result, list):
        return "\n\n".join(getattr(d, "text", "") or "" for d in result)
    text = getattr(result, "text", None) or getattr(result, "md", None)
    if text:
        return text
    raise ExtractionError("unexpected LlamaParse result shape")


def _save_images_from_result(result, asset_dir: Path, *, stem: str) -> dict[str, Path]:
    """Try to persist any inline images the SDK exposed. Best-effort."""
    mapping: dict[str, Path] = {}
    get_images = getattr(result, "get_image_documents", None)
    if not callable(get_images):
        return mapping
    try:
        images = get_images(download_path=str(asset_dir))
    except Exception:  # noqa: BLE001
        return mapping
    for idx, img in enumerate(images or [], start=1):
        path = getattr(img, "image_path", None) or getattr(img, "path", None)
        if path:
            p = Path(path)
            mapping[p.name] = p
            mapping[f"#/pictures/{idx - 1}"] = p
    return mapping


def _markdown_to_html(markdown: str) -> str:
    """Minimal markdown→HTML: headings, paragraphs, lists, fenced code, tables.

    Avoids adding a heavy dep; LlamaParse's markdown is already clean and
    our renderer tolerates simple HTML well.
    """
    import re

    lines = markdown.splitlines()
    out: list[str] = ["<html><body>"]
    in_code = False
    in_list = False
    in_table = False
    table_rows: list[str] = []
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + " ".join(para).strip() + "</p>")
            para.clear()

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_table() -> None:
        nonlocal in_table, table_rows
        if in_table and table_rows:
            out.append("<table>" + "".join(table_rows) + "</table>")
        table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_para(); flush_list(); flush_table()
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(line)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            flush_para(); flush_list(); flush_table()
            level = len(m.group(1))
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue

        if stripped.startswith(("- ", "* ")):
            flush_para(); flush_table()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{stripped[2:]}</li>")
            continue

        if "|" in stripped and stripped.startswith("|"):
            flush_para(); flush_list()
            in_table = True
            if re.match(r"^\|?[\s:\-|]+\|?$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            tag = "th" if not table_rows else "td"
            row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            table_rows.append(f"<tr>{row}</tr>")
            continue
        else:
            flush_table()

        if not stripped:
            flush_para(); flush_list()
            continue

        img = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if img:
            flush_para(); flush_list()
            alt, src = img.group(1), img.group(2)
            out.append(f'<figure><img src="{src}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
            continue

        para.append(stripped)

    flush_para(); flush_list(); flush_table()
    out.append("</body></html>")
    return "\n".join(out)
