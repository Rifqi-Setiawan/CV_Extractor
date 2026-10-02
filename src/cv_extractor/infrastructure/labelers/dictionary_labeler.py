"""Heading -> label using the alias dictionary and fuzzy string matching (rapidfuzz)."""
from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz, process

from cv_extractor.application.ports import LabelResult
from cv_extractor.domain.section_labels import SECTION_ALIASES
from cv_extractor.services.text_cleaning import normalize_heading

_CONTAINS_SCORE = 88.0


class DictionaryLabeler:
    def __init__(self, aliases: dict[str, list[str]] | None = None, min_score: float = 75.0):
        aliases = aliases or SECTION_ALIASES
        self._alias_to_label = {alias: label for label, items in aliases.items() for alias in items}
        self._aliases = list(self._alias_to_label)
        self._min_score = min_score

    def label(self, heading_text: str) -> Optional[LabelResult]:
        text = normalize_heading(heading_text)
        if not text:
            return None

        best_alias, best_score = None, 0.0
        hit = process.extractOne(text, self._aliases, scorer=fuzz.ratio)
        if hit:
            best_alias, best_score = hit[0], float(hit[1])

        # "Pengalaman Kerja & Magang" contains the alias "pengalaman kerja" plus one extra word.
        if best_score < _CONTAINS_SCORE:
            words = set(text.replace("&", " ").split())
            for alias in self._aliases:
                alias_words = alias.replace("&", " ").split()
                if set(alias_words) <= words and len(words) <= len(alias_words) + 1:
                    best_alias, best_score = alias, _CONTAINS_SCORE
                    break

        if best_alias is None or best_score < self._min_score:
            return None
        return LabelResult(self._alias_to_label[best_alias], best_score, "dictionary")
