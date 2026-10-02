"""Shared helpers: build synthetic TextLine objects so tests need no PDF files."""
from __future__ import annotations

import pytest

from cv_extractor.domain.models import BBox, TextLine, TextSource


def make_line(
    text: str,
    y: float,
    x: float = 50,
    size: float = 10,
    bold: bool | None = False,
    page: int = 0,
    column: int = 0,
    width: float | None = None,
    source: TextSource = TextSource.TEXT_LAYER,
    gap_above: float | None = None,
) -> TextLine:
    width = width if width is not None else len(text) * size * 0.5
    return TextLine(
        text=text,
        bbox=BBox(x, y, x + width, y + size * 1.2),
        size=size,
        page=page,
        source=source,
        bold=bold,
        column=column,
        gap_above=gap_above,
    )


@pytest.fixture
def line():
    return make_line
