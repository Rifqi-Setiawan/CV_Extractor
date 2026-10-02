"""Draw detected sections on top of the page images (visual debugging in the UI)."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from cv_extractor.domain.models import ParsedCV, TextLine

# One color per label (RGB). Unlisted labels fall back to grey.
LABEL_COLORS: dict[str, tuple[int, int, int]] = {
    "summary": (99, 102, 241),
    "experience": (37, 99, 235),
    "education": (22, 163, 74),
    "skills": (234, 88, 12),
    "projects": (219, 39, 119),
    "training": (13, 148, 136),
    "certifications": (202, 138, 4),
    "organizations": (147, 51, 234),
    "awards": (225, 29, 72),
    "languages": (8, 145, 178),
    "contact": (100, 116, 139),
    "personal_info": (120, 113, 108),
    "additional_info": (101, 163, 13),
    "header": (148, 163, 184),
    "other": (220, 38, 38),
}
_DEFAULT = (148, 163, 184)


def color_for(label: str) -> tuple[int, int, int]:
    return LABEL_COLORS.get(label, _DEFAULT)


def hex_color(label: str) -> str:
    return "#%02x%02x%02x" % color_for(label)


def annotate_pages(cv: ParsedCV, page_images: list[np.ndarray], dpi: int) -> list[Image.Image]:
    """Tint every section's lines in its color and outline its heading."""
    scale = dpi / 72
    canvases = [Image.fromarray(img).convert("RGBA") for img in page_images]
    overlays = [Image.new("RGBA", c.size, (0, 0, 0, 0)) for c in canvases]
    draws = [ImageDraw.Draw(o) for o in overlays]

    def box(line: TextLine) -> list[float]:
        b = line.bbox
        return [b.x0 * scale - 2, b.y0 * scale - 1, b.x1 * scale + 2, b.y1 * scale + 1]

    for section in cv.sections:
        r, g, b = color_for(section.label)
        for line in section.lines:
            if line.page < len(draws):
                draws[line.page].rectangle(box(line), fill=(r, g, b, 45))
        heading = section.heading_line
        if heading is not None and heading.page < len(draws):
            draws[heading.page].rectangle(box(heading), outline=(r, g, b, 255), width=3, fill=(r, g, b, 80))

    return [Image.alpha_composite(c, o).convert("RGB") for c, o in zip(canvases, overlays)]
