"""Use case: extract name, contact and sections from one CV document.

Orchestrates the pure services and the injected adapters (reader, labelers, LLM advisor).
Contains no library-specific code, so every dependency can be swapped or mocked.
"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Optional

from cv_extractor.application.config import PipelineConfig
from cv_extractor.application.ports import DocumentReader, HeadingAdvisor, HeadingLabeler, RawPage
from cv_extractor.domain.models import ExtractionMeta, ParsedCV, TextLine
from cv_extractor.domain.section_labels import UNKNOWN_LABEL
from cv_extractor.services import layout
from cv_extractor.services.confidence import assess
from cv_extractor.services.contact_extractor import extract_contact, extract_location
from cv_extractor.services.heading_detector import DetectedHeading, HeadingDetection, HeadingDetector
from cv_extractor.services.sectioner import build_header_sections, parse_header, split_into_sections

_NAME_LABEL_MIN_SCORE = 75.0


class CVExtractionService:
    def __init__(
        self,
        reader: DocumentReader,
        anchor_labeler: HeadingLabeler,
        fallback_labeler: Optional[HeadingLabeler] = None,
        advisor: Optional[HeadingAdvisor] = None,
        config: PipelineConfig = PipelineConfig(),
    ):
        self._reader = reader
        self._detector = HeadingDetector(anchor_labeler)
        self._anchor_labeler = anchor_labeler
        self._fallback_labeler = fallback_labeler
        self._advisor = advisor
        self._config = config

    # -------------------------------------------------------------- public API
    def extract(self, data: bytes, file_name: str = "cv.pdf") -> ParsedCV:
        started = time.perf_counter()
        pages = self._reader.read(data)
        lines = self._layout(pages)

        detection = self._detector.detect(lines)
        result = self._assemble(lines, detection, pages, file_name, started, llm_used=False)

        if self._should_ask_llm(result):
            llm_detection = self._ask_advisor(lines, detection)
            if llm_detection is not None:
                llm_result = self._assemble(lines, llm_detection, pages, file_name, started, llm_used=True)
                if llm_result.meta.confidence > result.meta.confidence:
                    result = llm_result
        return result

    # -------------------------------------------------------------- steps
    @staticmethod
    def _layout(pages: list[RawPage]) -> list[TextLine]:
        cleaned = layout.remove_page_noise([p.lines for p in pages], [p.info.height for p in pages])
        ordered: list[TextLine] = []
        for page, page_lines in zip(pages, cleaned):
            split = layout.find_column_split(page_lines, page.info.width)
            page.info.columns = 2 if split is not None else 1
            page_lines = layout.assign_columns(page_lines, split)
            page_lines = layout.merge_same_row(page_lines)
            page.info.line_count = len(page_lines)
            ordered.extend(layout.reading_order(page_lines))
        return ordered

    def _name_headings(self, headings: list[DetectedHeading]) -> list[DetectedHeading]:
        """Give a label to headings found by style only (dictionary -> LLM -> 'other')."""
        named = []
        for h in headings:
            if h.label is None:
                result = self._anchor_labeler.label(h.text)
                if (result is None or result.score < _NAME_LABEL_MIN_SCORE) and self._use_llm_labels():
                    result = self._fallback_labeler.label(h.text)
                if result is not None and (result.source == "llm" or result.score >= _NAME_LABEL_MIN_SCORE):
                    h = replace(h, label=result.label, label_source=result.source, score=result.score)
                else:
                    h = replace(h, label=UNKNOWN_LABEL, label_source="unknown")
            named.append(h)
        return named

    def _assemble(
        self,
        lines: list[TextLine],
        detection: HeadingDetection,
        pages: list[RawPage],
        file_name: str,
        started: float,
        llm_used: bool,
    ) -> ParsedCV:
        headings = self._name_headings(detection.headings)
        header_lines, sections = split_into_sections(lines, headings)
        header = parse_header(header_lines)
        sections = build_header_sections(header) + sections

        full_text = "\n".join(l.text for l in lines)
        contact = extract_contact("\n".join(header.contact_lines) + "\n" + full_text)
        contact.location = extract_location(header.contact_lines)

        report = assess(sections, header_lines, lines, header.name, contact)
        meta = ExtractionMeta(
            file_name=file_name,
            pages=[p.info for p in pages],
            seconds=time.perf_counter() - started,
            confidence=report.score,
            needs_review=report.score < self._config.review_threshold,
            heading_strategy=detection.strategy,
            llm_used=llm_used,
            warnings=report.warnings,
        )
        return ParsedCV(
            name=header.name,
            headline=header.headline,
            contact=contact,
            sections=sections,
            meta=meta,
        )

    # -------------------------------------------------------------- LLM fallback
    def _use_llm_labels(self) -> bool:
        return (
            self._fallback_labeler is not None
            and self._config.llm.enabled
            and self._config.llm.label_unknown_headings
        )

    def _should_ask_llm(self, result: ParsedCV) -> bool:
        return (
            self._advisor is not None
            and self._config.llm.enabled
            and result.meta.confidence < self._config.llm.confidence_threshold
        )

    def _ask_advisor(self, lines: list[TextLine], detection: HeadingDetection) -> Optional[HeadingDetection]:
        candidate_lines = [lines[i] for i in detection.candidates]
        if not candidate_lines:
            return None
        picked = self._advisor.detect(candidate_lines)
        if not picked:
            return None
        headings = [
            DetectedHeading(detection.candidates[k], lines[detection.candidates[k]].text, label, "llm", 70.0)
            for k, label in sorted(picked.items())
        ]
        return HeadingDetection(headings, "llm", None, detection.candidates)
