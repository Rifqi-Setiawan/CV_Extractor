"""Section heading detection that adapts to each CV's own template.

Idea: inside one CV every section heading is typeset the same way (same size, weight,
capitalization). We therefore:

1. collect *candidates* (short lines that could be headings);
2. pick *anchors*: candidates the dictionary recognizes with high confidence;
3. learn the heading *style signature* from the anchors (majority style);
4. accept every candidate that has the same signature — even if its text is unknown
   (e.g. "ACTIVITIES", "DESKRIPSI", "INFORMASI TAMBAHAN");
5. demote anchors whose style is smaller than the signature (they are sub-headings,
   e.g. "SOFT SKILL" inside "KEMAMPUAN").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Optional

from cv_extractor.application.ports import HeadingLabeler, LabelResult
from cv_extractor.domain.models import TextLine, TextSource
from cv_extractor.services.text_cleaning import alnum_count, heading_display_text

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_KEY_VALUE = re.compile(r"\w\s*:\s*\w")
_CONTACT = re.compile(r"@|https?://|www\.|\d{6,}")

ANCHOR_SCORE = 90.0
ANCHOR_SCORE_STYLED = 84.0


@dataclass(frozen=True)
class StyleSignature:
    size: float
    bold: Optional[bool]
    caps: bool
    source: TextSource

    def matches(self, line: TextLine) -> bool:
        if not _size_compatible(self.size, line.size, self.source):
            return False
        if self.bold is not None and line.bold is not None and self.bold != line.bold:
            return False
        return self.caps == _caps(line)


@dataclass
class DetectedHeading:
    index: int                 # position in the ordered line list
    text: str                  # cleaned heading text (without URLs)
    label: Optional[str]       # None = not recognized yet
    label_source: str          # dictionary | style | llm
    score: float


@dataclass
class HeadingDetection:
    headings: list[DetectedHeading]
    strategy: str              # "style_signature" | "dictionary_only" | "none" | "llm"
    signature: Optional[StyleSignature]
    candidates: list[int]      # indices of candidate lines (useful for an LLM fallback)


class HeadingDetector:
    def __init__(self, labeler: HeadingLabeler):
        self._labeler = labeler

    def detect(self, lines: list[TextLine]) -> HeadingDetection:
        if not lines:
            return HeadingDetection([], "none", None, [])

        body_size = body_font_size(lines)
        candidates = [i for i, l in enumerate(lines) if is_heading_candidate(l)]

        anchors: dict[int, LabelResult] = {}
        for i in candidates:
            result = self._labeler.label(heading_display_text(lines[i].text))
            if result is None:
                continue
            prominent = is_prominent(lines[i], body_size)
            if result.score >= ANCHOR_SCORE or (result.score >= ANCHOR_SCORE_STYLED and prominent):
                anchors[i] = result

        signature = self._learn_signature(lines, anchors, body_size)
        if signature is None:
            headings = [self._to_heading(lines, i, r) for i, r in sorted(anchors.items())]
            strategy = "dictionary_only" if headings else "none"
            return HeadingDetection(headings, strategy, None, candidates)

        reference_gap = _reference_gap(lines, anchors)
        first_anchor_per_column = _first_anchor_on_first_page(lines, anchors)
        headings: list[DetectedHeading] = []
        for i in candidates:
            line = lines[i]
            if i in anchors:
                if signature.matches(line) or not _smaller_than(line, signature):
                    headings.append(self._to_heading(lines, i, anchors[i]))
                continue  # anchor with a smaller style -> sub-heading, keep as content
            if _in_header_zone(i, line, first_anchor_per_column):
                continue  # e.g. "SAP PP-QM CONSULTANT" under the name: a headline, not a section
            if signature.matches(line) and _enough_space_above(line, reference_gap):
                headings.append(DetectedHeading(i, heading_display_text(line.text), None, "style", 0.0))
        return HeadingDetection(headings, "style_signature", signature, candidates)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _to_heading(lines: list[TextLine], i: int, result: LabelResult) -> DetectedHeading:
        return DetectedHeading(i, heading_display_text(lines[i].text), result.label, result.source, result.score)

    @staticmethod
    def _learn_signature(
        lines: list[TextLine], anchors: dict[int, LabelResult], body_size: float
    ) -> Optional[StyleSignature]:
        """Majority style among anchors (>= 2 agreeing anchors), or the style of a single
        anchor when it is clearly prominent (bigger than body text, or bold + caps)."""
        if not anchors:
            return None
        if len(anchors) == 1:
            line = lines[next(iter(anchors))]
            clearly_prominent = line.size >= body_size * 1.1 or (bool(line.bold) and _caps(line))
            if not clearly_prominent:
                return None
            return StyleSignature(line.size, line.bold, _caps(line), line.source)
        groups: list[list[TextLine]] = []
        for i in anchors:
            line = lines[i]
            for group in groups:
                ref = group[0]
                if (
                    _size_compatible(ref.size, line.size, line.source)
                    and _caps(ref) == _caps(line)
                    and (ref.bold is None or line.bold is None or ref.bold == line.bold)
                ):
                    group.append(line)
                    break
            else:
                groups.append([line])

        best = max(groups, key=lambda g: (len(g), median(l.size for l in g)))
        if len(best) < 2:
            return None
        sample = best[0]
        bold_values = [l.bold for l in best if l.bold is not None]
        signature = StyleSignature(
            size=median(l.size for l in best),
            bold=(sum(bold_values) > len(bold_values) / 2) if bold_values else None,
            caps=_caps(sample),
            source=sample.source,
        )
        # A signature identical to plain body text would match every short line: refuse it.
        if not (signature.caps or signature.bold or signature.size >= body_size * 1.1):
            return None
        return signature


# ------------------------------------------------------------------ public helpers


def body_font_size(lines: list[TextLine]) -> float:
    """Font size weighted by number of characters — i.e. the size of the body text."""
    weighted = sorted((l.size, len(l.text)) for l in lines)
    total = sum(n for _, n in weighted)
    acc = 0
    for size, n in weighted:
        acc += n
        if acc >= total / 2:
            return size
    return weighted[-1][0]


def is_heading_candidate(line: TextLine) -> bool:
    raw = line.text.strip()
    text = heading_display_text(raw)
    words = text.split()
    if not 1 <= len(words) <= 6 or len(text) > 48 or alnum_count(text) < 3:
        return False
    if raw[-1:] in ".,;" or (raw[-1:] == ":" and len(words) > 3):
        return False
    first_alpha = next((c for c in text if c.isalpha()), "")
    if not first_alpha or first_alpha.islower():
        return False
    if _YEAR.search(text) or _CONTACT.search(text) or _KEY_VALUE.search(text):
        return False
    return True


def is_prominent(line: TextLine, body_size: float) -> bool:
    return bool(line.bold) or _caps(line) or line.size >= body_size * 1.1


# ------------------------------------------------------------------ private helpers


def _caps(line: TextLine) -> bool:
    letters = [c for c in heading_display_text(line.text) if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def _size_compatible(a: float, b: float, source: TextSource) -> bool:
    if source == TextSource.OCR:
        return abs(a - b) <= max(a, b) * 0.18
    return abs(a - b) <= 0.6


def _smaller_than(line: TextLine, signature: StyleSignature) -> bool:
    return line.size < signature.size and not _size_compatible(line.size, signature.size, line.source)


def _reference_gap(lines: list[TextLine], anchors: dict[int, LabelResult]) -> Optional[float]:
    gaps = [lines[i].gap_above for i in anchors if lines[i].gap_above is not None]
    return min(gaps) if gaps else None


def _first_anchor_on_first_page(lines: list[TextLine], anchors: dict[int, LabelResult]) -> dict[int, int]:
    """Index of the first anchor heading per column on page 1."""
    first: dict[int, int] = {}
    for i in sorted(anchors):
        if lines[i].page == 0:
            first.setdefault(lines[i].column, i)
    return first


def _in_header_zone(index: int, line: TextLine, first_anchor_per_column: dict[int, int]) -> bool:
    """Lines above the first recognized heading of their column on page 1 belong to the
    CV header (name, job title, contact) and are never promoted to headings by style."""
    if line.page != 0:
        return False
    first = first_anchor_per_column.get(line.column)
    if first is None:
        first = min(first_anchor_per_column.values(), default=None)
    return first is not None and index < first


def _enough_space_above(line: TextLine, reference_gap: Optional[float]) -> bool:
    """Section headings are separated from the previous block by whitespace."""
    if line.gap_above is None or reference_gap is None:
        return True
    return line.gap_above >= reference_gap * 0.6
