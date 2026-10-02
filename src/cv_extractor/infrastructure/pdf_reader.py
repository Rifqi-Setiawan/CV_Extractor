"""PDF adapter (PyMuPDF): text layer when usable, OCR otherwise — decided per page."""
from __future__ import annotations

import numpy as np
import pymupdf

from cv_extractor.application.config import OcrConfig
from cv_extractor.application.ports import OcrEngine, RawPage
from cv_extractor.domain.models import BBox, PageInfo, TextLine, TextSource
from cv_extractor.services.text_cleaning import alnum_count, clean_line

_BOLD_FONT_HINTS = ("bold", "black", "heavy", "semibold", "demi")


class PdfDocumentReader:
    def __init__(self, ocr_engine: OcrEngine, config: OcrConfig):
        self._ocr = ocr_engine
        self._config = config

    def read(self, data: bytes) -> list[RawPage]:
        pages = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for number, page in enumerate(doc):
                if self._has_usable_text_layer(page):
                    lines, source = self._text_layer_lines(page, number), TextSource.TEXT_LAYER
                else:
                    lines, source = self._ocr_lines(page, number), TextSource.OCR
                info = PageInfo(number, page.rect.width, page.rect.height, source, columns=1, line_count=len(lines))
                pages.append(RawPage(info, lines))
        return pages

    # -------------------------------------------------------------- text layer
    def _has_usable_text_layer(self, page: pymupdf.Page) -> bool:
        text = page.get_text()
        usable = alnum_count(clean_line(text))
        # "(cid:123)" or replacement chars mean the font has no usable unicode mapping
        broken = text.count("�") + text.count("(cid:")
        return usable >= self._config.min_text_chars and broken < usable * 0.05

    @staticmethod
    def _text_layer_lines(page: pymupdf.Page, number: int) -> list[TextLine]:
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for raw in block.get("lines", []):
                spans = [s for s in raw["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean_line(" ".join(s["text"].strip() for s in spans))
                if alnum_count(text) < 2:
                    continue
                main = max(spans, key=lambda s: len(s["text"].strip()))
                lines.append(
                    TextLine(
                        text=text,
                        bbox=BBox(*raw["bbox"]),
                        size=round(main["size"], 2),
                        page=number,
                        source=TextSource.TEXT_LAYER,
                        bold=all(_is_bold(s) for s in spans if alnum_count(s["text"]) > 0),
                    )
                )
        return lines

    # -------------------------------------------------------------- OCR
    def _ocr_lines(self, page: pymupdf.Page, number: int) -> list[TextLine]:
        image = render_page(page, self._config.dpi)
        return self._ocr.recognize(image, number, scale=72 / self._config.dpi)


def render_page(page: pymupdf.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


def render_pdf_pages(data: bytes, dpi: int = 110) -> list[np.ndarray]:
    """Page images for the UI preview."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [render_page(page, dpi) for page in doc]


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or any(h in span["font"].lower() for h in _BOLD_FONT_HINTS)
