"""Docling-based extraction engine (CPU-friendly default).

Docling runs on CPU in seconds/page with strong table accuracy and built-in
OCR + formula enrichment. This engine is the default for pdf2learn; the
marker-pdf engine remains available via ``--engine marker``.

Auto-scan detection
-------------------
Docling is invoked twice when the first pass returns very little text: once
without OCR (fast path) and, if the result looks image-only, once more with
``force_full_page_ocr=True``. Users never have to flag scanned PDFs.

Lazy imports keep ``pdf2learn --help`` and unit tests functional even when
docling itself isn't installed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..models import ExtractedContent
from .html_parser import parse_marker_html  # reused — it handles semantic HTML
from .marker_engine import ExtractionError, ImageOnlyPDFError

log = logging.getLogger(__name__)

QUALITY_PRESETS = ("fast", "rich", "scanned")


def extract(
    pdf_path: Path,
    *,
    asset_dir: Path,
    image_only_text_threshold: int = 200,
    quality: str = "rich",
) -> ExtractedContent:
    """Run docling on ``pdf_path`` and return an ``ExtractedContent``.

    ``quality``:
      * ``"fast"``    — no OCR, no enrichment. Best for text-native slides.
      * ``"rich"``    — formula + code enrichment on. Default.
      * ``"scanned"`` — rich + force full-page OCR. Slowest but robust.

    Auto-upgrades ``fast``/``rich`` to ``scanned`` when the first pass returns
    text below ``image_only_text_threshold``, so messy/scanned PDFs
    self-heal without a user flag.
    """
    if quality not in QUALITY_PRESETS:
        raise ValueError(f"invalid quality preset {quality!r}; pick one of {QUALITY_PRESETS}")

    try:
        from docling.datamodel.base_models import InputFormat  # type: ignore[import-not-found]
        from docling.datamodel.pipeline_options import (  # type: ignore[import-not-found]
            PdfPipelineOptions,
        )
        from docling.document_converter import (  # type: ignore[import-not-found]
            DocumentConverter,
            PdfFormatOption,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise ExtractionError(
            "docling is not installed. Install it with `pip install docling`."
        ) from exc

    asset_dir.mkdir(parents=True, exist_ok=True)

    content = _run_once(
        pdf_path,
        asset_dir=asset_dir,
        quality=quality,
        InputFormat=InputFormat,
        PdfPipelineOptions=PdfPipelineOptions,
        DocumentConverter=DocumentConverter,
        PdfFormatOption=PdfFormatOption,
    )

    # Self-heal: retry with OCR when the first pass looks image-only.
    if (
        content.total_text_length < image_only_text_threshold
        and quality != "scanned"
    ):
        log.info(
            "first pass yielded %d chars (threshold %d); retrying with full-page OCR",
            content.total_text_length,
            image_only_text_threshold,
        )
        content.warnings.append(
            f"Auto-upgraded to scanned mode: first pass returned only "
            f"{content.total_text_length} chars of text."
        )
        content = _run_once(
            pdf_path,
            asset_dir=asset_dir,
            quality="scanned",
            InputFormat=InputFormat,
            PdfPipelineOptions=PdfPipelineOptions,
            DocumentConverter=DocumentConverter,
            PdfFormatOption=PdfFormatOption,
        )

    if content.total_text_length < image_only_text_threshold:
        raise ImageOnlyPDFError(
            f"{pdf_path.name}: extracted {content.total_text_length} chars even "
            f"with OCR (threshold {image_only_text_threshold}). "
            f"PDF appears to be empty or unreadable."
        )

    log.info(
        "extracted %d section(s), %d figure(s), %d page(s)",
        len(content.sections),
        len(content.figures),
        content.page_count,
    )
    return content


def _run_once(
    pdf_path: Path,
    *,
    asset_dir: Path,
    quality: str,
    InputFormat,
    PdfPipelineOptions,
    DocumentConverter,
    PdfFormatOption,
) -> ExtractedContent:
    """Single docling pass. Lazy-imported deps passed in so callers share the import block."""
    opts = PdfPipelineOptions()
    opts.do_table_structure = True
    opts.generate_picture_images = True

    if quality != "fast":
        # Enrichments — equations to LaTeX, code blocks language-tagged.
        for attr in ("do_formula_enrichment", "do_code_enrichment", "do_picture_classification"):
            if hasattr(opts, attr):
                setattr(opts, attr, True)

    if quality == "scanned":
        opts.do_ocr = True
        if hasattr(opts, "ocr_options") and hasattr(opts.ocr_options, "force_full_page_ocr"):
            opts.ocr_options.force_full_page_ocr = True
    else:
        opts.do_ocr = False  # fast/rich skip OCR; retry loop upgrades on empty text

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )

    log.info("docling extracting %s (quality=%s)", pdf_path.name, quality)
    try:
        result = converter.convert(str(pdf_path))
        document = result.document
        raw_html = document.export_to_html()
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"docling failed on {pdf_path.name}: {exc}") from exc

    figure_asset_map = _persist_docling_pictures(document, asset_dir, stem=pdf_path.stem)

    return parse_marker_html(
        raw_html,
        figure_asset_map=figure_asset_map,
        document_stem=pdf_path.stem,
    )


def _persist_docling_pictures(document, asset_dir: Path, *, stem: str) -> dict[str, Path]:
    """Write each picture in the docling document to disk; return ``{ref: path}``."""
    mapping: dict[str, Path] = {}
    pictures = getattr(document, "pictures", None) or []
    for idx, picture in enumerate(pictures, start=1):
        pil_image = None
        # Docling exposes images in different shapes depending on version; be defensive.
        get_image = getattr(picture, "get_image", None)
        if callable(get_image):
            try:
                pil_image = get_image(document)
            except Exception:  # noqa: BLE001
                pil_image = None
        if pil_image is None:
            pil_image = getattr(picture, "image", None)
        if pil_image is None:
            continue

        fmt = (getattr(pil_image, "format", None) or "png").lower()
        dest = asset_dir / f"{stem}_fig{idx:03d}.{fmt}"
        try:
            pil_image.save(dest)
        except Exception as exc:  # noqa: BLE001
            log.warning("failed to save picture %d: %s", idx, exc)
            continue

        # Record under any ref/name docling uses, plus a positional fallback.
        ref = getattr(picture, "self_ref", None) or getattr(picture, "ref", None)
        if ref:
            mapping[str(ref)] = dest
        mapping[f"#/pictures/{idx - 1}"] = dest
    return mapping
