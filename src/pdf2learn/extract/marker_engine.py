"""Marker-pdf wrapper: run conversion, return a parsed ``ExtractedContent``.

Marker is imported lazily so unit tests and ``--help`` work without the
heavy ML dependency installed. The raw HTML emitted by marker is parsed
into our document model (``Section``, ``Block``, ``Figure``) via
``html_parser`` — callers never see marker's output shape directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..models import ExtractedContent
from .html_parser import parse_marker_html

log = logging.getLogger(__name__)


class ExtractionError(RuntimeError):
    """Raised when marker fails outright (corrupt/encrypted PDF, etc.)."""


class ImageOnlyPDFError(RuntimeError):
    """Raised when the PDF has no extractable text (FR-015)."""


def extract(
    pdf_path: Path,
    *,
    asset_dir: Path,
    image_only_text_threshold: int = 200,
    force_ocr: bool = False,
) -> ExtractedContent:
    """Run marker-pdf on ``pdf_path`` and return an ``ExtractedContent``.

    Side effects:
      - Creates ``asset_dir`` if needed.
      - Writes each extracted figure to ``asset_dir`` as
        ``<stem>_p{page}_fig{n}.{ext}`` (constitution X, FR-009).

    Raises:
      - ``ImageOnlyPDFError`` if total extracted text falls below
        ``image_only_text_threshold`` — orchestrator maps this to exit 3.
      - ``ExtractionError`` for other marker failures — orchestrator maps to exit 4.
    """
    try:
        from marker.converters.pdf import PdfConverter  # type: ignore[import-not-found]
        from marker.models import create_model_dict  # type: ignore[import-not-found]
        from marker.output import text_from_rendered  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise ExtractionError(
            "marker-pdf is not installed. Install it with `pip install marker-pdf`."
        ) from exc

    marker_config = {
        "output_format": "html",
        "redo_inline_math": True,
        "disable_image_extraction": False,
        "force_ocr": force_ocr,
    }
    log.info("extracting %s (force_ocr=%s)", pdf_path.name, force_ocr)
    try:
        converter = PdfConverter(
            artifact_dict=create_model_dict(),
            config=marker_config,
        )
        rendered = converter(str(pdf_path))
        raw_html, _metadata, images = text_from_rendered(rendered)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"marker-pdf failed on {pdf_path.name}: {exc}") from exc

    asset_dir.mkdir(parents=True, exist_ok=True)
    figure_asset_map = _persist_images(images, asset_dir, stem=pdf_path.stem)

    content = parse_marker_html(
        raw_html,
        figure_asset_map=figure_asset_map,
        document_stem=pdf_path.stem,
    )

    if content.total_text_length < image_only_text_threshold:
        raise ImageOnlyPDFError(
            f"{pdf_path.name}: extracted text ({content.total_text_length} chars) "
            f"is below the image-only threshold ({image_only_text_threshold}). "
            f"OCR is out of scope for v1."
        )

    log.info(
        "extracted %d section(s), %d figure(s), %d page(s)",
        len(content.sections),
        len(content.figures),
        content.page_count,
    )
    return content


def _persist_images(images: dict, asset_dir: Path, *, stem: str) -> dict[str, Path]:
    """Write PIL images from marker to disk and return ``{original_name: path}``.

    Marker returns ``dict[str, PIL.Image.Image]``. We preserve the original key
    as the lookup used by ``html_parser`` to associate ``<img src=...>`` with
    the saved file, but normalize the on-disk filename.
    """
    mapping: dict[str, Path] = {}
    for idx, (name, image) in enumerate(sorted(images.items()), start=1):
        ext = _infer_image_ext(name, image)
        dest = asset_dir / f"{stem}_fig{idx:03d}.{ext}"
        try:
            image.save(dest)
        except Exception as exc:  # noqa: BLE001
            log.warning("failed to save image %s: %s", name, exc)
            continue
        mapping[name] = dest
    return mapping


def _infer_image_ext(name: str, image) -> str:
    """Best-effort filename extension: use the marker-provided name, else PIL format."""
    suffix = Path(name).suffix.lstrip(".").lower()
    if suffix in {"png", "jpg", "jpeg", "gif", "webp", "bmp"}:
        return "jpg" if suffix == "jpeg" else suffix
    fmt = getattr(image, "format", None)
    if fmt:
        return fmt.lower()
    return "png"
