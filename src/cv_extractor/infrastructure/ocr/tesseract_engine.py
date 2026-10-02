"""OCR adapter for Tesseract (via pytesseract)."""
from __future__ import annotations

import os
from statistics import median

import numpy as np
import pytesseract
from PIL import Image

from cv_extractor.domain.models import BBox, TextLine, TextSource
from cv_extractor.infrastructure.ocr.stroke import mark_bold
from cv_extractor.services.text_cleaning import alnum_count, clean_line

_MIN_WORD_CONF = 30
_COLUMN_GAP_POINTS = 25  # a gap wider than this inside one Tesseract "line" means two columns


class TesseractOcrEngine:
    name = "tesseract"

    def __init__(self, languages: str = "eng+ind"):
        self._languages = languages
        # On Windows Tesseract is often not on PATH: allow TESSERACT_CMD=C:\...\tesseract.exe
        if os.environ.get("TESSERACT_CMD"):
            pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

    def recognize(self, image_rgb: np.ndarray, page_number: int, scale: float) -> list[TextLine]:
        data = pytesseract.image_to_data(
            Image.fromarray(image_rgb),
            lang=self._languages,
            config="--psm 3",
            output_type=pytesseract.Output.DICT,
        )
        lines = [
            line
            for words in self._split_on_gaps(self._group_words(data), data, scale)
            if (line := self._to_line(words, data, page_number, scale)) is not None
        ]
        gray = image_rgb.mean(axis=2).astype(np.uint8)
        return mark_bold(lines, gray, scale)

    @staticmethod
    def _group_words(data: dict) -> list[list[int]]:
        groups: dict[tuple, list[int]] = {}
        for i, word in enumerate(data["text"]):
            if word.strip() and float(data["conf"][i]) >= _MIN_WORD_CONF:
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                groups.setdefault(key, []).append(i)
        return list(groups.values())

    @staticmethod
    def _split_on_gaps(groups: list[list[int]], data: dict, scale: float) -> list[list[int]]:
        """Tesseract sometimes glues the left and right column into one line — split them."""
        gap_px = _COLUMN_GAP_POINTS / scale
        out = []
        for idxs in groups:
            idxs = sorted(idxs, key=lambda i: data["left"][i])
            current = [idxs[0]]
            for prev, i in zip(idxs, idxs[1:]):
                if data["left"][i] - (data["left"][prev] + data["width"][prev]) > gap_px:
                    out.append(current)
                    current = []
                current.append(i)
            out.append(current)
        return out

    @staticmethod
    def _to_line(idxs: list[int], data: dict, page: int, scale: float) -> TextLine | None:
        text = clean_line(" ".join(data["text"][i] for i in idxs))
        if alnum_count(text) < 2:
            return None
        x0 = min(data["left"][i] for i in idxs) * scale
        y0 = min(data["top"][i] for i in idxs) * scale
        x1 = max(data["left"][i] + data["width"][i] for i in idxs) * scale
        y1 = max(data["top"][i] + data["height"][i] for i in idxs) * scale
        return TextLine(
            text=text,
            bbox=BBox(x0, y0, x1, y1),
            size=median(data["height"][i] for i in idxs) * scale,
            page=page,
            source=TextSource.OCR,
            confidence=sum(float(data["conf"][i]) for i in idxs) / len(idxs) / 100,
        )
