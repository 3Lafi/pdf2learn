"""WCAG AA contrast check on body text in both themes (T051, SC-005)."""

from __future__ import annotations

import re
from pathlib import Path


def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _rel_luminance(rgb: tuple[float, float, float]) -> float:
    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    l1 = _rel_luminance(_hex_to_rgb(fg))
    l2 = _rel_luminance(_hex_to_rgb(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _extract_vars(block: str) -> dict[str, str]:
    return dict(re.findall(r"--(\w+):\s*(#[0-9a-fA-F]+)\s*;", block))


def test_body_text_meets_wcag_aa_in_both_themes() -> None:
    css = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "pdf2learn"
        / "assets"
        / "style.css"
    ).read_text(encoding="utf-8")

    # :root = light defaults; html[data-theme="dark"] = dark overrides.
    light_block = re.search(r":root\s*\{([^}]+)\}", css).group(1)  # type: ignore[union-attr]
    dark_block = re.search(
        r'html\[data-theme="dark"\]\s*\{([^}]+)\}', css
    ).group(1)  # type: ignore[union-attr]

    light = _extract_vars(light_block)
    dark = _extract_vars(dark_block)

    # WCAG AA for normal text = 4.5:1.
    assert _contrast(light["fg"], light["bg"]) >= 4.5
    assert _contrast(dark["fg"], dark["bg"]) >= 4.5
