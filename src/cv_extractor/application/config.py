"""User-tunable settings for one extraction run."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrConfig:
    languages: str = "eng+ind"     # Tesseract language codes
    dpi: int = 300
    min_text_chars: int = 50       # a page with fewer usable characters is sent to OCR


@dataclass(frozen=True)
class LlmConfig:
    enabled: bool = False
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b"
    timeout_seconds: int = 120
    # Ask the LLM only when the rule-based confidence is below this value.
    confidence_threshold: float = 0.6
    # Also use the LLM to name headings the dictionary does not know.
    label_unknown_headings: bool = True


@dataclass(frozen=True)
class PipelineConfig:
    ocr: OcrConfig = OcrConfig()
    llm: LlmConfig = LlmConfig()
    review_threshold: float = 0.6  # confidence below this marks the CV as "needs review"
