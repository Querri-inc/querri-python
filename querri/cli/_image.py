"""Terminal image rendering using Unicode half-block characters.

Downloads images to ``~/.querri/cache/images/`` and renders them as colored
ANSI art using the ``Pillow`` library and Unicode half-block characters (``\\u2580``
upper, ``\\u2584`` lower). Each character cell encodes two vertical pixels,
doubling the effective vertical resolution.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger("querri")

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".querri" / "cache" / "images"

# ANSI 256-color palette breakpoints for the 6x6x6 RGB cube (indices 16-231).
_PALETTE = [0, 95, 135, 175, 215, 255]


def _nearest_palette_index(value: int) -> int:
    """Find the nearest index in the 6-level palette for a single channel."""
    best = 0
    best_dist = abs(value - _PALETTE[0])
    for i in range(1, 6):
        dist = abs(value - _PALETTE[i])
        if dist < best_dist:
            best_dist = dist
            best = i
    return best


def _rgb_to_ansi256(r: int, g: int, b: int) -> int:
    """Convert an RGB triplet to the nearest ANSI 256 color index."""
    ri = _nearest_palette_index(r)
    gi = _nearest_palette_index(g)
    bi = _nearest_palette_index(b)
    return 16 + ri * 36 + gi * 6 + bi


# ---------------------------------------------------------------------------
# Download + cache
# ---------------------------------------------------------------------------


def _cache_path(url: str) -> Path:
    """Deterministic cache path for a URL."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    suffix = Path(url.split("?")[0]).suffix or ".png"
    return CACHE_DIR / f"{h}{suffix}"


def download_image(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    retries: int = 2,
) -> Path | None:
    """Download an image to the local cache. Returns the path or None on error.

    Retries on failure (useful when the file was just created and may
    not be immediately available from the storage backend).

    Args:
        url: Image URL to download.
        headers: Optional auth headers for authenticated endpoints.
        retries: Number of retry attempts on failure.
    """
    import time

    import httpx

    cached = _cache_path(url)
    if cached.exists():
        return cached

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries + 1):
        try:
            resp = httpx.get(
                url,
                headers=headers or {},
                follow_redirects=True,
                timeout=15.0,
            )
            resp.raise_for_status()
            cached.write_bytes(resp.content)
            return cached
        except Exception as exc:
            logger.debug(
                "Image download attempt %d/%d failed for %s: %s",
                attempt + 1,
                retries + 1,
                url,
                exc,
            )
            if attempt < retries:
                time.sleep(1.0)

    return None


# ---------------------------------------------------------------------------
# Half-block renderer
# ---------------------------------------------------------------------------


def render_image(
    path: Path,
    *,
    max_width: int = 60,
    max_height: int = 30,
) -> str | None:
    """Render an image file as ANSI-colored Unicode half-block art.

    Each character cell uses upper-half-block (``\\u2580``) with foreground for
    the top pixel and background for the bottom pixel, giving 2x vertical
    resolution.

    Args:
        path: Path to an image file (PNG, JPEG, etc.).
        max_width: Maximum character width for the output.
        max_height: Maximum character height (each char = 2 pixel rows).

    Returns:
        A string with ANSI escape codes, or None if rendering fails.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.debug("Pillow not installed — cannot render image")
        return None

    try:
        img = Image.open(path).convert("RGB")
    except Exception as exc:
        logger.debug("Failed to open image %s: %s", path, exc)
        return None

    # Resize to fit terminal — height is doubled because each char = 2 rows
    w, h = img.size
    scale_w = max_width / w
    scale_h = (max_height * 2) / h  # 2 pixel rows per char row
    scale = min(scale_w, scale_h, 1.0)  # never upscale

    new_w = max(1, int(w * scale))
    new_h = max(2, int(h * scale))
    # Ensure even height for half-block pairing
    if new_h % 2 != 0:
        new_h += 1

    img = img.resize((new_w, new_h), Image.LANCZOS)
    pixels = img.load()

    lines: list[str] = []
    for y in range(0, new_h, 2):
        line_parts: list[str] = []
        for x in range(new_w):
            # Top pixel = foreground, bottom pixel = background
            r1, g1, b1 = pixels[x, y]
            if y + 1 < new_h:
                r2, g2, b2 = pixels[x, y + 1]
            else:
                r2, g2, b2 = r1, g1, b1

            fg = _rgb_to_ansi256(r1, g1, b1)
            bg = _rgb_to_ansi256(r2, g2, b2)
            # \u2580 = upper half block — fg colors top, bg colors bottom
            line_parts.append(f"\033[38;5;{fg}m\033[48;5;{bg}m\u2580")

        lines.append("".join(line_parts) + "\033[0m")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rich integration
# ---------------------------------------------------------------------------


def render_image_rich(
    url: str,
    *,
    caption: str = "",
    max_width: int = 60,
    max_height: int = 24,
    headers: dict[str, str] | None = None,
) -> object:
    """Download and render an image as a Rich Panel with ANSI art.

    Falls back to a clickable link if rendering fails.

    Args:
        url: Image URL to download and render.
        caption: Optional caption text to show below the image.
        max_width: Maximum character width.
        max_height: Maximum character height.

    Returns:
        A Rich renderable (Panel or Text).
    """
    from rich.text import Text

    path = download_image(url, headers=headers)
    ansi_art = (
        render_image(path, max_width=max_width, max_height=max_height) if path else None
    )

    if ansi_art:
        # Rich Text.from_ansi parses ANSI escape codes into styled text
        art = Text.from_ansi(ansi_art)
        parts = [art]
        if caption:
            parts.append(Text(f"\n{caption}", style="italic"))
        # Clickable link hint below
        parts.append(
            Text.from_markup(f"\n[dim][link={url}]Open full image[/link][/dim]")
        )
        return Text("\n").join(parts)
    else:
        # Fallback: clickable link + hint
        return Text.from_markup(
            f"  [link={url}][bold #f15a24]View chart[/bold #f15a24][/link]"
            f"  [dim]{url}[/dim]\n"
            f"  [dim]Run [bold]querri chat show[/bold] to render inline[/dim]"
        )
