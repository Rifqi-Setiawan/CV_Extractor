"""Turns ordered lines + detected headings into sections, and parses the CV header.

The header is everything that appears before the first heading of its column on page 1
(name, headline, contact line, and often an un-titled summary paragraph).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cv_extractor.domain.models import Section, TextLine
from cv_extractor.domain.section_labels import SUMMARY_LABEL, UNKNOWN_LABEL
from cv_extractor.services.contact_extractor import EMAIL_RE, looks_like_contact_line
from cv_extractor.services.heading_detector import DetectedHeading

HEADER_LABEL = "header"
_MIN_SUMMARY_WORDS = 15


@dataclass
class HeaderParts:
    name: Optional[str]
    headline: Optional[str]
    contact_lines: list[str]
    summary_lines: list[TextLine]
    other_lines: list[TextLine]


def split_into_sections(
    lines: list[TextLine], headings: list[DetectedHeading]
) -> tuple[list[TextLine], list[Section]]:
    """Return (header_lines, sections). Section text is copied verbatim from `lines`."""
    by_index = {h.index: h for h in headings}
    header: list[TextLine] = []
    sections: list[Section] = []
    current: Optional[Section] = None
    prev_column: Optional[int] = None

    for i, line in enumerate(lines):
        # On page 1, a new column starts "fresh": the right column of a 2-column CV often
        # begins with the name/title before its first heading.
        if line.page == 0 and prev_column is not None and line.column != prev_column and line.column == 2:
            current = None
        prev_column = line.column

        heading = by_index.get(i)
        if heading is not None and current is not None and _is_sub_heading(heading, current):
            # "KEMAMPUAN" > "TEKNIK SKILL" > "SOFT SKILL": same label in a row means the
            # later ones are sub-headings. Keep them as content of the open section.
            current.lines.append(line)
            continue
        if heading is not None:
            current = Section(
                label=heading.label or UNKNOWN_LABEL,
                raw_heading=heading.text,
                lines=[],
                label_source=heading.label_source if heading.label else "unknown",
                heading_line=line,
            )
            sections.append(current)
            continue

        if current is None:
            if line.page == 0:
                header.append(line)
            elif sections:  # continuation on a later page before any new heading
                sections[-1].lines.append(line)
            else:
                header.append(line)
        else:
            current.lines.append(line)

    return header, [s for s in sections if s.lines or s.raw_heading]


def parse_header(header: list[TextLine]) -> HeaderParts:
    if not header:
        return HeaderParts(None, None, [], [], [])

    name_line = _pick_name(header)
    remaining = [l for l in header if l is not name_line]

    headline_line = None
    if name_line is not None:
        after_name = [l for l in remaining if l.page == name_line.page and l.bbox.y0 >= name_line.bbox.y0]
        after_name.sort(key=lambda l: l.bbox.y0)
        if after_name and _is_headline(after_name[0]):
            headline_line = after_name[0]
            remaining = [l for l in remaining if l is not headline_line]

    contact_lines = [l for l in remaining if looks_like_contact_line(l.text)]
    rest = [l for l in remaining if not any(l is c for c in contact_lines)]

    # An un-titled summary is the block of prose that starts at the first long line and
    # runs to the end of the header (its last line can be short: "support decision-making.").
    start = next((k for k, l in enumerate(rest) if len(l.text.split()) >= 6), None)
    summary_lines: list[TextLine] = []
    if start is not None and sum(len(l.text.split()) for l in rest[start:]) >= _MIN_SUMMARY_WORDS:
        summary_lines = rest[start:]
    other_lines = rest[:start] if summary_lines else rest

    return HeaderParts(
        name=_title_case(name_line.text) if name_line else None,
        headline=headline_line.text if headline_line else None,
        contact_lines=[l.text for l in contact_lines],
        summary_lines=summary_lines,
        other_lines=other_lines,
    )


def build_header_sections(parts: HeaderParts) -> list[Section]:
    """Sections that come from the header itself (no visible heading)."""
    out = []
    if parts.summary_lines:
        out.append(Section(SUMMARY_LABEL, None, parts.summary_lines, inferred=True, label_source="inferred"))
    if parts.other_lines:
        out.append(Section(HEADER_LABEL, None, parts.other_lines, inferred=True, label_source="inferred"))
    return out


# ------------------------------------------------------------------ helpers


def _is_sub_heading(heading: DetectedHeading, current: Section) -> bool:
    return heading.label is not None and heading.label != UNKNOWN_LABEL and heading.label == current.label


def _pick_name(header: list[TextLine]) -> Optional[TextLine]:
    first_page = [l for l in header if l.page == 0] or header
    candidates = [l for l in first_page if _looks_like_name(l.text)]
    if not candidates:
        return None
    return max(candidates, key=lambda l: (round(l.size, 1), -l.bbox.y0))


def _looks_like_name(text: str) -> bool:
    if EMAIL_RE.search(text) or "http" in text.lower() or "www." in text.lower() or ".com" in text.lower():
        return False
    if sum(c.isdigit() for c in text) > 0:
        return False
    core = text.split(",")[0]  # "Andika Rafika Ningsih, S.Pd" -> name part
    words = [w for w in core.split() if any(c.isalpha() for c in w)]
    return 2 <= len(words) <= 6 and len(text) <= 60


def _is_headline(line: TextLine) -> bool:
    words = line.text.split()
    return 1 <= len(words) <= 8 and not looks_like_contact_line(line.text) and not line.text.endswith(".")


def _title_case(text: str) -> str:
    """Normalize ALL-CAPS names; keep mixed-case names (and academic titles) as written."""
    return text.title() if text.isupper() else text
