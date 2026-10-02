"""Heuristic confidence score (0..1) for a parse, plus human-readable warnings.

The score decides whether the optional LLM fallback is called and whether the result is
flagged for manual review. Weights are simple and documented so they can be tuned
against a labeled evaluation set.
"""
from __future__ import annotations

from dataclasses import dataclass

from cv_extractor.domain.models import ContactInfo, Section, TextLine, TextSource
from cv_extractor.domain.section_labels import UNKNOWN_LABEL


@dataclass
class ConfidenceReport:
    score: float
    warnings: list[str]


def assess(
    sections: list[Section],
    header_lines: list[TextLine],
    all_lines: list[TextLine],
    name: str | None,
    contact: ContactInfo,
) -> ConfidenceReport:
    headed = [s for s in sections if not s.inferred]
    warnings: list[str] = []

    # 1. how many real (headed) sections were found
    n = len(headed)
    section_score = {0: 0.0, 1: 0.3, 2: 0.55, 3: 0.8}.get(n, 1.0)
    if n < 3:
        warnings.append(f"Hanya {n} section dengan heading yang terdeteksi.")

    # 2. how much text ended up inside headed sections (vs. stuck in the header)
    total = len(all_lines) or 1
    covered = sum(len(s.lines) for s in headed) / total
    if len(header_lines) / total > 0.35:
        warnings.append("Banyak teks tidak masuk section mana pun (tertinggal di header).")

    # 3. unknown labels
    unknown = sum(1 for s in headed if s.label == UNKNOWN_LABEL)
    unknown_ratio = unknown / n if n else 1.0
    if unknown:
        warnings.append(f"{unknown} heading tidak dikenali dan diberi label '{UNKNOWN_LABEL}'.")

    # 4. identity fields
    identity = (0.5 if name else 0.0) + (0.5 if contact.emails else 0.0)
    if not name:
        warnings.append("Nama tidak ditemukan.")
    if not contact.emails:
        warnings.append("Email tidak ditemukan.")

    # 5. OCR quality
    ocr_lines = [l for l in all_lines if l.source == TextSource.OCR]
    if ocr_lines:
        ocr_quality = sum(l.confidence for l in ocr_lines) / len(ocr_lines)
        warnings.append(
            "Sebagian/seluruh teks berasal dari OCR — cek ulang email, nomor HP dan nama "
            "(OCR bisa salah membaca satu karakter, mis. q→g)."
        )
    else:
        ocr_quality = 1.0

    score = (
        0.45 * section_score
        + 0.25 * min(covered / 0.7, 1.0)
        + 0.10 * (1 - unknown_ratio)
        + 0.10 * identity
        + 0.10 * ocr_quality
    )
    return ConfidenceReport(round(min(max(score, 0.0), 1.0), 3), warnings)
