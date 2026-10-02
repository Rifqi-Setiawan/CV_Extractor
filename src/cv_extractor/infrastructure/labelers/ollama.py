"""Optional local-LLM adapters talking to an Ollama server (self-hosted, no API cost).

Both adapters send as little text as possible (CPU inference is slow on long prompts):
- OllamaHeadingLabeler: one heading text in, one label out.
- OllamaHeadingAdvisor: only the *candidate* lines (short lines + style) in,
  {line_number: label} out — never the full CV.
Output is constrained with a JSON schema through Ollama's `format` parameter.
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Sequence

import requests

from cv_extractor.application.ports import LabelResult
from cv_extractor.domain.models import TextLine
from cv_extractor.domain.section_labels import ALL_LABELS, UNKNOWN_LABEL

log = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model = model
        self._timeout = timeout

    def chat_json(self, prompt: str, schema: dict) -> Optional[dict]:
        try:
            resp = requests.post(
                self._url,
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": schema,
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return json.loads(resp.json()["message"]["content"])
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("Ollama request failed: %s", exc)
            return None

    def is_available(self) -> bool:
        try:
            base = self._url.rsplit("/api/", 1)[0]
            return requests.get(base + "/api/tags", timeout=3).ok
        except requests.RequestException:
            return False


class OllamaHeadingLabeler:
    _SCHEMA = {
        "type": "object",
        "properties": {"label": {"type": "string", "enum": ALL_LABELS}},
        "required": ["label"],
    }

    def __init__(self, client: OllamaClient):
        self._client = client

    def label(self, heading_text: str) -> Optional[LabelResult]:
        prompt = (
            "You classify CV/resume section headings (English or Indonesian).\n"
            f"Allowed labels: {', '.join(ALL_LABELS)}.\n"
            f"Use '{UNKNOWN_LABEL}' if none fits.\n"
            f'Heading: "{heading_text}"'
        )
        data = self._client.chat_json(prompt, self._SCHEMA)
        if not data or data.get("label") not in ALL_LABELS:
            return None
        return LabelResult(data["label"], 70.0, "llm")


class OllamaHeadingAdvisor:
    _SCHEMA = {
        "type": "object",
        "properties": {
            "headings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "integer"},
                        "label": {"type": "string", "enum": ALL_LABELS},
                    },
                    "required": ["line", "label"],
                },
            }
        },
        "required": ["headings"],
    }

    def __init__(self, client: OllamaClient):
        self._client = client

    def detect(self, candidates: Sequence[TextLine]) -> dict[int, str]:
        listing = "\n".join(
            f"{i}: {line.text}  [size={line.size:.1f}"
            f"{', bold' if line.bold else ''}{', caps' if line.text.isupper() else ''}, page={line.page + 1}]"
            for i, line in enumerate(candidates)
        )
        prompt = (
            "Below are short lines taken from one CV/resume (English or Indonesian), with their style.\n"
            "Most are job titles, company names or sub-headings. Pick ONLY the lines that are "
            "top-level SECTION headings (e.g. Experience, Pendidikan, Skills) and give each a label.\n"
            "Section headings in one CV usually share the same style.\n"
            f"Allowed labels: {', '.join(ALL_LABELS)}.\n\n{listing}"
        )
        data = self._client.chat_json(prompt, self._SCHEMA)
        if not data:
            return {}
        result = {}
        for item in data.get("headings", []):
            idx, label = item.get("line"), item.get("label")
            if isinstance(idx, int) and 0 <= idx < len(candidates) and label in ALL_LABELS:
                result[idx] = label
        return result
