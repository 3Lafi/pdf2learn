"""Conversion orchestration.

Takes a resolved :class:`ConversionJob`, runs extraction + rendering, and
manages logging and exit codes. Directory / batch handling lives here;
``cli.py`` is a thin argparse-alike shell on top.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .config import Config
from .extract.marker_engine import ExtractionError, ImageOnlyPDFError
from .logging_ import job_logging
from .models import ConversionJob
from .paths import resolve_output_dir
from .render.renderer import render

log = logging.getLogger("pdf2learn")


def extract(pdf_path: Path, *, config: Config, asset_dir: Path) -> "ExtractedContent":  # type: ignore[name-defined]
    """Engine-dispatching extraction facade.

    Tests monkeypatch this symbol (``pdf2learn.orchestrator.extract``) so
    batch/integration tests don't require the real extraction backend.
    """
    engine = (config.engine or "llamaparse").lower()
    if engine == "llamaparse":
        from .extract.llamaparse_engine import extract as _extract
        return _extract(
            pdf_path,
            asset_dir=asset_dir,
            image_only_text_threshold=config.image_only_text_threshold,
            mode=config.quality if config.quality in {"fast", "cost_effective", "agentic", "agentic_plus"} else "cost_effective",
        )
    if engine == "docling":
        from .extract.docling_engine import extract as _extract
        return _extract(
            pdf_path,
            asset_dir=asset_dir,
            image_only_text_threshold=config.image_only_text_threshold,
            quality=config.quality,
        )
    if engine == "marker":
        from .extract.marker_engine import extract as _extract
        return _extract(
            pdf_path,
            asset_dir=asset_dir,
            image_only_text_threshold=config.image_only_text_threshold,
        )
    raise ValueError(f"unknown engine {engine!r}; pick 'llamaparse', 'docling', or 'marker'")


def iter_pdfs(input_path: Path, *, recursive: bool) -> list[Path]:
    """Enumerate PDF files from either a file path or a directory.

    Raises ``FileNotFoundError`` if ``input_path`` does not exist and
    ``ValueError`` if it is neither a PDF file nor a directory.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"not a PDF file: {input_path}")
        return [input_path]
    if input_path.is_dir():
        pattern = "**/*.pdf" if recursive else "*.pdf"
        found = sorted(p for p in input_path.glob(pattern) if p.is_file())
        if not found:
            raise ValueError(f"no .pdf files under {input_path}")
        return found
    raise ValueError(f"unsupported input: {input_path}")


def run_job(pdf_path: Path, *, config: Config) -> ConversionJob:
    """Execute one conversion end-to-end. Always returns the job with a populated status."""
    job = ConversionJob(
        input_path=pdf_path,
        output_root=config.output_root,
        force=config.force,
        started_at=datetime.now(),
    )
    output_dir = resolve_output_dir(
        config.output_root,
        pdf_path.name,
        force=config.force,
        now=job.started_at,
    )
    job.output_dir = output_dir
    job.log_path = output_dir / "conversion.log"

    with job_logging(job.log_path, quiet=config.quiet) as logger:
        job.status = "running"
        logger.info("input: %s", pdf_path)
        logger.info("output: %s", output_dir)
        try:
            content = extract(
                pdf_path,
                config=config,
                asset_dir=output_dir / "assets",
            )
            logger.info(
                "%d page(s), %d figure(s), %d section(s)",
                content.page_count,
                len(content.figures),
                len(content.sections),
            )
            rendered = render(
                content,
                output_dir=output_dir,
                document_stem=pdf_path.stem,
            )
            logger.info("wrote %s", rendered.html_path)
            for warning in content.warnings:
                logger.warning(warning)
            job.status = "succeeded"
            job.exit_code = 0
        except ImageOnlyPDFError as exc:
            logger.error(str(exc))
            job.status = "failed"
            job.exit_code = 3
        except (ExtractionError, ValueError, FileNotFoundError) as exc:
            logger.error(str(exc))
            job.status = "failed"
            job.exit_code = 2 if isinstance(exc, (ValueError, FileNotFoundError)) else 4
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected failure: %s", exc)
            job.status = "failed"
            job.exit_code = 4

    return job


def run_batch(paths: list[Path], *, config: Config) -> int:
    """Run a list of PDFs sequentially. Returns the worst exit code seen."""
    worst = 0
    for pdf_path in paths:
        job = run_job(pdf_path, config=config)
        if job.exit_code > worst:
            worst = job.exit_code
    return worst
