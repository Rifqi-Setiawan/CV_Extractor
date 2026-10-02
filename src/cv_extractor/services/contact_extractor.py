"""Regex-based extraction of e-mail, phone, LinkedIn, other URLs and location."""
from __future__ import annotations

import re
from typing import Optional

from cv_extractor.domain.models import ContactInfo

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# Indonesian (08.., +62, 62..) and generic international numbers; separators: space . -
PHONE_RE = re.compile(r"(?<![\w/])(?:\+?\d{1,3}[\s.-]?)?\(?0?\d{2,4}\)?(?:[\s.-]?\d{2,5}){2,4}(?![\w/])")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub|company)/[^\s|,•·)]+", re.I)
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s|,•·)]+|\b(?:github\.com|gitlab\.com|bit\.ly|behance\.net|medium\.com)/[^\s|,•·)]+",
    re.I,
)
_DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*[-–]\s*(?:(?:19|20)\d{2})\b")
_SEPARATORS = re.compile(r"\s*[|•·]\s*|\s{3,}")


def extract_contact(text: str) -> ContactInfo:
    emails = _unique(m.group().strip(".") for m in EMAIL_RE.finditer(text))
    linkedin_match = LINKEDIN_RE.search(text)
    all_urls = _unique(m.group().rstrip("/.") for m in URL_RE.finditer(text))
    if linkedin_match:
        linkedin = linkedin_match.group().rstrip("/.")
    else:  # e.g. "https://www.linkedin.com/feed/" — not a profile URL, but still LinkedIn
        linkedin = next((u for u in all_urls if "linkedin.com" in u.lower()), None)
    urls = [u for u in all_urls if "linkedin.com" not in u.lower()]
    return ContactInfo(emails=emails, phones=_phones(text), linkedin=linkedin, urls=urls)


def extract_location(contact_lines: list[str]) -> Optional[str]:
    """First separator-delimited chunk that is not an e-mail, phone or URL.

    "Sidoarjo, Jawa Timur · 0813... · mail@x.com"  ->  "Sidoarjo, Jawa Timur"
    """
    for line in contact_lines:
        parts = [p.strip(" ,") for p in _SEPARATORS.split(line) if p.strip(" ,")]
        if len(parts) < 2:
            continue
        for part in parts:
            if EMAIL_RE.search(part) or URL_RE.search(part) or LINKEDIN_RE.search(part):
                continue
            if sum(c.isdigit() for c in part) >= 8:
                continue
            if sum(c.isalpha() for c in part) >= 3:
                return part
    return None


def looks_like_contact_line(text: str) -> bool:
    return bool(
        EMAIL_RE.search(text) or LINKEDIN_RE.search(text) or URL_RE.search(text) or _phones(text)
    )


def _phones(text: str) -> list[str]:
    cleaned = _DATE_RANGE.sub(" ", text)
    found = []
    for m in PHONE_RE.finditer(cleaned):
        candidate = m.group().strip()
        digits = re.sub(r"\D", "", candidate)
        if not 9 <= len(digits) <= 15:
            continue
        if not (candidate.startswith("+") or digits.startswith("0") or digits.startswith("62")):
            continue
        found.append(candidate)
    return _unique(found)


def _unique(items) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out
