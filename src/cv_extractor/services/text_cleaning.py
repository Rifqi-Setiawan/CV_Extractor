"""Small, pure text helpers shared by several services."""
from __future__ import annotations

import re

# Bullets as real glyphs, private-use-area glyphs (e.g. Symbol/Wingdings bullets in
# "Print to PDF" files) and the characters OCR typically reads bullets as.
_LEADING_BULLET = re.compile(
    r"^\s*(?:[•●▪◦·‣⁃■□➢✓✔\-–*»«¢“”©®°>]"
    r"|[-]|e@|e(?=\s)|o(?=\s))\s*"
)
_PRIVATE_USE = re.compile(r"[-]")
_ZERO_WIDTH_AND_BIDI = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|id|ly|io|me|dev|net|org)/\S*", re.I)
_MULTISPACE = re.compile(r"[ \t]+")


def clean_line(text: str) -> str:
    """Strip bullets and private-use glyphs, collapse whitespace."""
    text = _ZERO_WIDTH_AND_BIDI.sub("", text)
    text = _LEADING_BULLET.sub("", text, count=1)
    text = _PRIVATE_USE.sub("", text)
    return _MULTISPACE.sub(" ", text).strip()


def alnum_count(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def strip_urls(text: str) -> str:
    return _MULTISPACE.sub(" ", _URL.sub("", text)).strip()


def normalize_heading(text: str) -> str:
    """Lowercase, drop URLs/punctuation/digits so headings can be compared to aliases."""
    text = strip_urls(text).lower().replace("&", " & ")
    text = re.sub(r"[^a-z&\s-]", " ", text)
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def heading_display_text(text: str) -> str:
    """Heading as it should be shown: without trailing URLs or separators."""
    return strip_urls(text).strip(" :|-–")
