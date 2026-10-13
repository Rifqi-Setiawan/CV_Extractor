"""Layout analysis: column detection, same-row merging, reading order and noise removal.

All functions are pure: they take TextLine objects and return new lists.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Optional

from cv_extractor.domain.models import BBox, TextLine

_PAGE_NUMBER = re.compile(r"^(?:page|halaman|hal\.?)?\s*\d{1,2}\s*(?:/|of|dari)?\s*\d{0,2}$", re.I)

# ------------------------------------------------------------------ column detection


def find_column_split(lines: list[TextLine], page_width: float) -> Optional[float]:
    """Return the x coordinate separating two columns, or None for a single-column page.

    A split is accepted only if (almost) no line crosses it and *both* sides carry a real
    share of the text. The text-share guard prevents two false positives seen in practice:
    right-aligned dates ("Jan 2024 - Apr 2025") and a narrow "label column" where only
    headings sit on the left ("TENTANG SAYA" + indented paragraph on the right).
    """
    if len(lines) < 8:
        return None

    total_chars = sum(len(line.text) for line in lines) or 1
    best: Optional[tuple[int, float]] = None
    step = 3.0
    x = page_width * 0.22
    while x < page_width * 0.78:
        crossing = sum(1 for l in lines if l.bbox.x0 < x - 2 and l.bbox.x1 > x + 2)
        left = [l for l in lines if l.bbox.x1 <= x + 2]
        right = [l for l in lines if l.bbox.x0 >= x - 2]
        left_share = sum(len(l.text) for l in left) / total_chars
        right_share = sum(len(l.text) for l in right) / total_chars
        if (
            len(left) >= 0.15 * len(lines)
            and len(right) >= 0.15 * len(lines)
            and left_share >= 0.12
            and right_share >= 0.12
            and _has_body_text(left)
            and _has_body_text(right)
        ):
            if best is None or crossing < best[0]:
                best = (crossing, x)
        x += step

    if best and best[0] <= 0.08 * len(lines):
        return best[1]
    return None


def _has_body_text(lines: list[TextLine]) -> bool:
    """A real column holds more than headings and dates: at least a few multi-word lines."""
    return sum(1 for l in lines if len(l.text.split()) >= 3) >= 3


def assign_columns(lines: list[TextLine], split: Optional[float]) -> list[TextLine]:
    if split is None:
        return [replace(l, column=0) for l in lines]
    out = []
    for l in lines:
        if l.bbox.x1 <= split + 2:
            col = 1
        elif l.bbox.x0 >= split - 2:
            col = 2
        else:
            col = 0
        out.append(replace(l, column=col))
    return out


# ------------------------------------------------------------------ same-row merging


def merge_same_row(lines: list[TextLine], max_gap_ratio: float = 30.0) -> list[TextLine]:
    """Merge fragments that sit on the same visual row within the same column.

    Example: "Technical Leader" (x=38) and "Januari 2024 - April 2025" (x=418) become
    one line, so the date stays attached to its job title.
    """
    from cv_extractor.domain.section_labels import SECTION_ALIASES
    from cv_extractor.services.text_cleaning import normalize_heading
    known_section_aliases = {normalize_heading(a) for aliases in SECTION_ALIASES.values() for a in aliases}

    rows: list[list[TextLine]] = []
    for line in sorted(lines, key=lambda l: (l.column, l.bbox.y_center, l.bbox.x0)):
        if rows and _same_row(rows[-1][-1], line):
            rows[-1].append(line)
        else:
            rows.append([line])

    merged = []
    for row in rows:
        row.sort(key=lambda l: l.bbox.x0)
        if len(row) == 1:
            merged.append(row[0])
            continue

        # If the first item on the row is an anchor section heading separated by a noticeable gap,
        # preserve it as its own line instead of merging into body text.
        first_norm = normalize_heading(row[0].text)
        if first_norm in known_section_aliases and (row[1].bbox.x0 - row[0].bbox.x1) > row[0].size * 1.8:
            merged.append(row[0])
            row = row[1:]
            if len(row) == 1:
                merged.append(row[0])
                continue

        first = row[0]
        text = row[0].text
        for prev, cur in zip(row, row[1:]):
            gap = cur.bbox.x0 - prev.bbox.x1
            text += "   " + cur.text if gap > first.size * 1.5 else " " + cur.text
        bold_values = [l.bold for l in row if l.bold is not None]
        merged.append(
            replace(
                first,
                text=text,
                bbox=BBox(
                    min(l.bbox.x0 for l in row),
                    min(l.bbox.y0 for l in row),
                    max(l.bbox.x1 for l in row),
                    max(l.bbox.y1 for l in row),
                ),
                size=max(l.size for l in row),
                # bold only if every fragment is bold (a bold title + regular date is not a heading)
                bold=all(bold_values) if bold_values else None,
                confidence=min(l.confidence for l in row),
            )
        )
    return merged


def _same_row(a: TextLine, b: TextLine) -> bool:
    if a.column != b.column or a.page != b.page:
        return False
    overlap = min(a.bbox.y1, b.bbox.y1) - max(a.bbox.y0, b.bbox.y0)
    min_height = max(min(a.bbox.height, b.bbox.height), 1.0)
    horizontally_apart = b.bbox.x0 >= a.bbox.x1 - 1 or a.bbox.x0 >= b.bbox.x1 - 1
    return overlap / min_height > 0.5 and horizontally_apart


# ------------------------------------------------------------------ reading order


def reading_order(lines: list[TextLine]) -> list[TextLine]:
    """Order lines as a human reads them.

    Full-width lines (column 0) act as band separators. Inside each band the left column is
    read completely before the right column.
    """
    spanning = sorted((l for l in lines if l.column == 0), key=lambda l: l.bbox.y0)
    columns = [l for l in lines if l.column != 0]
    if not columns:
        return _with_gaps(spanning)

    ordered: list[TextLine] = []
    boundaries = [-1.0] + [l.bbox.y0 for l in spanning] + [float("inf")]
    for i in range(len(boundaries) - 1):
        top, bottom = boundaries[i], boundaries[i + 1]
        band = [l for l in columns if top <= l.bbox.y0 < bottom]
        for col in (1, 2):
            ordered.extend(sorted((l for l in band if l.column == col), key=lambda l: l.bbox.y0))
        if i < len(spanning):
            ordered.append(spanning[i])
    return _with_gaps(ordered)


def _with_gaps(lines: list[TextLine]) -> list[TextLine]:
    """Fill `gap_above` = whitespace between a line and the previous line of its column."""
    last_bottom: dict[int, float] = {}
    out = []
    for l in lines:
        key = l.column
        gap = l.bbox.y0 - last_bottom[key] if key in last_bottom else None
        out.append(replace(l, gap_above=gap))
        last_bottom[key] = l.bbox.y1
        if key == 0:  # a full-width line closes both columns
            last_bottom[1] = last_bottom[2] = l.bbox.y1
    return out


# ------------------------------------------------------------------ noise removal


def remove_page_noise(pages: list[list[TextLine]], page_heights: list[float]) -> list[list[TextLine]]:
    """Drop page numbers and headers/footers repeated on several pages."""
    if len(pages) < 2:
        return [[l for l in page if not _PAGE_NUMBER.match(l.text)] for page in pages]

    def in_margin(line: TextLine) -> bool:
        h = page_heights[line.page]
        return line.bbox.y0 < h * 0.07 or line.bbox.y1 > h * 0.93

    repeated = Counter(
        l.text.lower() for page in pages for l in {x.text.lower(): x for x in page if in_margin(x)}.values()
    )
    noise = {t for t, n in repeated.items() if n >= 2}
    return [
        [l for l in page if not _PAGE_NUMBER.match(l.text) and not (in_margin(l) and l.text.lower() in noise)]
        for page in pages
    ]
