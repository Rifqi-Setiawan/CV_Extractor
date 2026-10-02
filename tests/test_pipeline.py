"""End-to-end tests of the use case with fake adapters (no PDF, no OCR, no Ollama)."""
from unittest.mock import MagicMock, patch

from cv_extractor.application.config import LlmConfig, PipelineConfig
from cv_extractor.application.pipeline import CVExtractionService
from cv_extractor.application.ports import LabelResult, RawPage
from cv_extractor.domain.models import PageInfo, TextSource
from cv_extractor.infrastructure.labelers.dictionary_labeler import DictionaryLabeler
from cv_extractor.infrastructure.labelers.ollama import OllamaClient, OllamaHeadingAdvisor


class FakeReader:
    def __init__(self, lines):
        self._lines = lines

    def read(self, data: bytes):
        return [RawPage(PageInfo(0, 600, 842, TextSource.TEXT_LAYER, 1, len(self._lines)), self._lines)]


def _cv_lines(make_line):
    return [
        make_line("JANE DOE", y=20, size=24, bold=True),
        make_line("Jakarta · 081234567890 · jane@mail.com", y=50),
        make_line("RINGKASAN", y=80, size=14, bold=True),
        make_line("Data analyst with experience in SQL, Python and dashboards", y=100),
        make_line("PENGALAMAN KERJA", y=140, size=14, bold=True),
        make_line("Data Analyst at PT Contoh building weekly KPI dashboards", y=160),
        make_line("WHERE I VOLUNTEER", y=200, size=14, bold=True),
        make_line("Teaching coding to high-school students every weekend", y=220),
    ]


def test_full_extraction_without_llm(line):
    service = CVExtractionService(FakeReader(_cv_lines(line)), DictionaryLabeler())
    cv = service.extract(b"", "jane.pdf")

    assert cv.name == "Jane Doe"
    assert cv.contact.emails == ["jane@mail.com"]
    assert cv.contact.location == "Jakarta"
    assert [s.label for s in cv.sections] == ["summary", "experience", "other"]
    assert cv.sections[-1].raw_heading == "WHERE I VOLUNTEER"
    assert cv.meta.llm_used is False
    assert cv.to_dict()["sections"][1]["text"].startswith("Data Analyst at PT Contoh")


def test_unknown_heading_is_named_by_fallback_labeler(line):
    llm_labeler = MagicMock()
    llm_labeler.label.return_value = LabelResult("organizations", 70.0, "llm")
    service = CVExtractionService(
        FakeReader(_cv_lines(line)),
        DictionaryLabeler(),
        fallback_labeler=llm_labeler,
        config=PipelineConfig(llm=LlmConfig(enabled=True)),
    )
    cv = service.extract(b"", "jane.pdf")
    assert cv.sections[-1].label == "organizations"
    assert cv.sections[-1].label_source == "llm"


def test_advisor_is_used_when_rules_find_nothing(line):
    lines = [
        line("Jane Doe", y=20, size=12),
        line("Where I Worked", y=60, size=12),
        line("Data Analyst at PT Contoh building weekly KPI dashboards", y=80),
        line("What I Studied", y=120, size=12),
        line("Informatics at Telkom University with a 3.8 GPA overall", y=140),
    ]
    advisor = MagicMock()
    advisor.detect.side_effect = lambda cands: {
        i: {"Where I Worked": "experience", "What I Studied": "education"}[c.text]
        for i, c in enumerate(cands)
        if c.text in ("Where I Worked", "What I Studied")
    }
    service = CVExtractionService(
        FakeReader(lines), DictionaryLabeler(), advisor=advisor, config=PipelineConfig(llm=LlmConfig(enabled=True))
    )
    cv = service.extract(b"", "x.pdf")
    assert cv.meta.llm_used is True
    assert [s.label for s in cv.sections if not s.inferred] == ["experience", "education"]


def test_ollama_advisor_parses_schema_response(line):
    response = MagicMock()
    response.json.return_value = {"message": {"content": '{"headings": [{"line": 1, "label": "experience"}]}'}}
    with patch("cv_extractor.infrastructure.labelers.ollama.requests.post", return_value=response) as post:
        advisor = OllamaHeadingAdvisor(OllamaClient("http://localhost:11434", "qwen2.5:3b"))
        result = advisor.detect([line("Jane", y=0), line("Where I Worked", y=10)])
    assert result == {1: "experience"}
    sent = post.call_args.kwargs["json"]
    assert sent["format"]["required"] == ["headings"] and sent["options"]["temperature"] == 0


def test_ollama_failure_returns_empty(line):
    import requests

    with patch("cv_extractor.infrastructure.labelers.ollama.requests.post", side_effect=requests.ConnectionError):
        advisor = OllamaHeadingAdvisor(OllamaClient("http://localhost:11434", "m"))
        assert advisor.detect([line("A b", y=0)]) == {}
