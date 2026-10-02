"""Ports (interfaces) the application layer depends on.

Infrastructure adapters implement these; the pipeline never imports a concrete library.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from cv_extractor.domain.models import PageInfo, TextLine


@dataclass
class RawPage:
    """What a document reader returns per page."""

    info: PageInfo
    lines: list[TextLine]


class DocumentReader(Protocol):
    """Turns a document (bytes) into pages of normalized text lines (text layer or OCR)."""

    def read(self, data: bytes) -> list[RawPage]: ...


class OcrEngine(Protocol):
    """Recognizes text lines on a rendered page image."""

    name: str

    def recognize(self, image_rgb, page_number: int, scale: float) -> list[TextLine]:
        """`scale` converts image pixels back to PDF points (72 / dpi)."""
        ...


@dataclass
class LabelResult:
    label: str
    score: float
    source: str  # "dictionary" | "llm"


class HeadingLabeler(Protocol):
    """Maps a heading text (any language) to a canonical section label."""

    def label(self, heading_text: str) -> Optional[LabelResult]: ...


class HeadingAdvisor(Protocol):
    """Fallback that decides which candidate lines are section headings (e.g. a local LLM).

    Receives candidate lines with their style and returns {candidate_index: label}.
    """

    def detect(self, candidates: Sequence[TextLine]) -> dict[int, str]: ...
