"""Layering check (T041, T044).

Enforces the module boundaries documented in ``docs/architecture.md``:

* ``pdf2learn.extract`` and ``pdf2learn.render`` must not import each other.
* ``pdf2learn.extract`` / ``pdf2learn.render`` must not import
  ``pdf2learn.orchestrator`` or ``pdf2learn.cli`` (one-way data flow).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "pdf2learn"

FORBIDDEN = {
    "extract": {"pdf2learn.render", "pdf2learn.orchestrator", "pdf2learn.cli"},
    "render": {"pdf2learn.extract", "pdf2learn.orchestrator", "pdf2learn.cli"},
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            prefix = "." * (node.level or 0)
            names.add(prefix + node.module)
    return names


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_has_no_forbidden_imports(layer: str) -> None:
    layer_dir = SRC / layer
    for py in layer_dir.rglob("*.py"):
        imports = _imports(py)
        resolved = {
            f"pdf2learn.{layer}.{name.lstrip('.')}" if name.startswith(".") else name
            for name in imports
        }
        bad = resolved & FORBIDDEN[layer]
        assert not bad, f"{py.relative_to(SRC)} imports forbidden modules: {bad}"
