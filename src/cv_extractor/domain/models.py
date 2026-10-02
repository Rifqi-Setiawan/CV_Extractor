"""Core entities of the domain. Pure data — no I/O, no third-party imports."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class TextSource(str, Enum):
    TEXT_LAYER = "text_layer"
    OCR = "ocr"


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class TextLine:
    """One visual line of text, normalized so that text-layer and OCR output look the same.

    `size` is the font size in PDF points (text layer) or the estimated glyph height (OCR).
    `bold` is None when it is unknown.
    """

    text: str
    bbox: BBox
    size: float
    page: int
    source: TextSource
    bold: Optional[bool] = None
    confidence: float = 1.0
    column: int = 0  # 0 = full width / single column, 1 = left, 2 = right
    gap_above: Optional[float] = None  # vertical whitespace to the previous line in the same column

    @property
    def is_caps(self) -> bool:
        letters = [c for c in self.text if c.isalpha()]
        return len(letters) >= 2 and all(c.isupper() for c in letters)


@dataclass
class PageInfo:
    number: int
    width: float
    height: float
    source: TextSource
    columns: int
    line_count: int


@dataclass
class ContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    linkedin: Optional[str] = None
    urls: list[str] = field(default_factory=list)
    location: Optional[str] = None


@dataclass
class Section:
    label: str                    # canonical label, e.g. "experience"
    raw_heading: Optional[str]    # heading text exactly as written in the CV (None if inferred)
    lines: list[TextLine]
    inferred: bool = False        # True when the section had no visible heading (e.g. top summary)
    label_source: str = "dictionary"  # dictionary | llm | inferred | unknown
    heading_line: Optional[TextLine] = None  # where the heading sits on the page

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def pages(self) -> list[int]:
        return sorted({line.page for line in self.lines})


@dataclass
class ExtractionMeta:
    file_name: str
    pages: list[PageInfo]
    seconds: float
    confidence: float
    needs_review: bool
    heading_strategy: str
    llm_used: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedCV:
    name: Optional[str]
    headline: Optional[str]
    contact: ContactInfo
    sections: list[Section]
    meta: ExtractionMeta

    def section(self, label: str) -> Optional[Section]:
        return next((s for s in self.sections if s.label == label), None)

    def to_dict(self) -> dict:
        """Serializable representation used for JSON output."""
        return {
            "name": self.name,
            "headline": self.headline,
            "contact": asdict(self.contact),
            "sections": [
                {
                    "label": s.label,
                    "raw_heading": s.raw_heading,
                    "inferred": s.inferred,
                    "label_source": s.label_source,
                    "pages": [p + 1 for p in s.pages],
                    "text": s.text,
                }
                for s in self.sections
            ],
            "meta": {
                "file_name": self.meta.file_name,
                "seconds": round(self.meta.seconds, 2),
                "confidence": round(self.meta.confidence, 2),
                "needs_review": self.meta.needs_review,
                "heading_strategy": self.meta.heading_strategy,
                "llm_used": self.meta.llm_used,
                "warnings": self.meta.warnings,
                "pages": [
                    {
                        "page": p.number + 1,
                        "source": p.source.value,
                        "columns": p.columns,
                        "lines": p.line_count,
                    }
                    for p in self.meta.pages
                ],
            },
        }
