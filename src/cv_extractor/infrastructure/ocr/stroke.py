"""Estimate whether OCR'd lines are bold, from the image itself.

OCR engines don't report font weight, but bold text has thicker strokes. For every line we
measure the average horizontal run length of dark pixels (≈ stroke width) relative to the
line height, then call a line bold when it is clearly thicker than the page's typical line.
"""
from __future__ import annotations

from statistics import median

import numpy as np

from cv_extractor.domain.models import TextLine

_BOLD_RATIO = 1.3


def mark_bold(lines: list[TextLine], gray: np.ndarray, scale: float) -> list[TextLine]:
    """`gray` is the page image (H, W) uint8; `scale` converts pixels to PDF points."""
    widths = [_stroke_width(gray, line, scale) for line in lines]
    valid = [w for w in widths if w is not None]
    if len(valid) < 5:
        return lines
    typical = median(valid)
    for line, width in zip(lines, widths):
        line.bold = width is not None and width >= typical * _BOLD_RATIO
    return lines


def _stroke_width(gray: np.ndarray, line: TextLine, scale: float) -> float | None:
    x0, y0 = int(line.bbox.x0 / scale), int(line.bbox.y0 / scale)
    x1, y1 = int(line.bbox.x1 / scale), int(line.bbox.y1 / scale)
    crop = gray[max(y0, 0):y1, max(x0, 0):x1]
    if crop.size == 0 or crop.shape[0] < 4:
        return None
    # Text may be dark-on-light or light-on-dark (e.g. white text on a colored pill).
    threshold = (int(crop.min()) + int(crop.max())) / 2
    ink = crop < threshold
    if ink.mean() > 0.5:
        ink = ~ink
    runs = np.diff(ink.astype(np.int8), axis=1)
    starts = (runs == 1).sum()
    if starts == 0:
        return None
    return float(ink.sum()) / starts / max(crop.shape[0], 1)
