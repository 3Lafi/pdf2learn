"""Typer-based CLI entry point.

See ``specs/011-pdf-html-learning/contracts/cli.md`` for the contract.
"""

from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .config import load_config
from .orchestrator import iter_pdfs, run_batch

app = typer.Typer(
    name="pdf2learn",
    help="Convert any PDF into a self-contained, learning-optimized HTML document.",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pdf2learn {__version__}")
        raise typer.Exit(code=0)


@app.command()
def main(
    input: Path = typer.Argument(
        ...,
        exists=False,
        help="A .pdf file or a directory of PDFs.",
    ),
    output_dir: Path = typer.Option(
        Path("output"),
        "--output-dir",
        "-o",
        help="Root directory that holds per-PDF subdirectories.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="When <input> is a directory, descend into subdirectories.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite a pre-existing per-PDF output directory in place.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress stdout progress lines (conversion.log still written).",
    ),
    engine: str = typer.Option(
        "docling",
        "--engine",
        "-e",
        help="Extraction backend: 'docling' (CPU default) or 'marker' (GPU).",
    ),
    quality: str = typer.Option(
        "rich",
        "--quality",
        help="docling preset: 'fast' | 'rich' | 'scanned'. Auto-upgrades on image-only PDFs.",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to an optional YAML config file.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    config = load_config(config_path)
    config.output_root = output_dir
    config.recursive = recursive
    config.force = force
    config.quiet = quiet
    config.engine = engine
    config.quality = quality

    try:
        pdfs = iter_pdfs(input, recursive=recursive)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"[pdf2learn:error] {exc}", err=True)
        raise typer.Exit(code=2) from exc

    exit_code = run_batch(pdfs, config=config)
    raise typer.Exit(code=exit_code)


if __name__ == "__main__":  # pragma: no cover
    app()
