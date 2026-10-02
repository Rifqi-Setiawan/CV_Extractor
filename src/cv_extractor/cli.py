"""Command-line entry point (batch processing / evaluation).

    python -m cv_extractor.cli cv1.pdf cv2.pdf -o hasil.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cv_extractor.application.config import LlmConfig, OcrConfig, PipelineConfig
from cv_extractor.bootstrap import build_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract name, contact and sections from CV PDFs.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="write JSON here instead of stdout")
    parser.add_argument("--ocr-lang", default="eng+ind")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--llm", action="store_true", help="enable the local Ollama fallback")
    parser.add_argument("--llm-model", default="qwen2.5:3b")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    args = parser.parse_args()

    config = PipelineConfig(
        ocr=OcrConfig(languages=args.ocr_lang, dpi=args.dpi),
        llm=LlmConfig(enabled=args.llm, model=args.llm_model, base_url=args.ollama_url),
    )
    service = build_service(config)
    results = [service.extract(path.read_bytes(), path.name).to_dict() for path in args.files]

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
        print(f"Saved {len(results)} result(s) to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
