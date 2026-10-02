"""Composition root: the only place that knows which concrete adapters are used."""
from __future__ import annotations

from cv_extractor.application.config import PipelineConfig
from cv_extractor.application.pipeline import CVExtractionService
from cv_extractor.infrastructure.labelers.dictionary_labeler import DictionaryLabeler
from cv_extractor.infrastructure.labelers.ollama import (
    OllamaClient,
    OllamaHeadingAdvisor,
    OllamaHeadingLabeler,
)
from cv_extractor.infrastructure.ocr.tesseract_engine import TesseractOcrEngine
from cv_extractor.infrastructure.pdf_reader import PdfDocumentReader


def build_service(config: PipelineConfig = PipelineConfig()) -> CVExtractionService:
    ocr = TesseractOcrEngine(languages=config.ocr.languages)
    reader = PdfDocumentReader(ocr, config.ocr)

    fallback_labeler = advisor = None
    if config.llm.enabled:
        client = OllamaClient(config.llm.base_url, config.llm.model, config.llm.timeout_seconds)
        fallback_labeler = OllamaHeadingLabeler(client)
        advisor = OllamaHeadingAdvisor(client)

    return CVExtractionService(
        reader=reader,
        anchor_labeler=DictionaryLabeler(),
        fallback_labeler=fallback_labeler,
        advisor=advisor,
        config=config,
    )


def ollama_available(base_url: str) -> bool:
    return OllamaClient(base_url, model="").is_available()
