from cv_extractor.infrastructure.labelers.dictionary_labeler import DictionaryLabeler
from cv_extractor.services.heading_detector import HeadingDetector, is_heading_candidate


def _heading(make_line, text, y, **kw):
    return make_line(text, y=y, size=14, bold=True, gap_above=20, **kw)


def _body(make_line, text, y, **kw):
    return make_line(text, y=y, size=10, gap_above=3, **kw)


def _cv(make_line):
    """A CV whose 'ACTIVITIES' heading is unknown to a reduced dictionary."""
    return [
        make_line("JANE DOE", y=20, size=24, bold=True),
        _heading(make_line, "EDUCATION", 60),
        _body(make_line, "Telkom University, Bachelor of Informatics", 80),
        _heading(make_line, "WORK EXPERIENCE", 120),
        _body(make_line, "QA Intern at XLSmart building Katalon test suites", 140),
        make_line("SOFTWARE ENGINEER, REMOTE", y=160, size=12, bold=True, gap_above=5),  # job title
        _body(make_line, "Built APIs with Laravel for real time transactions", 180),
        _heading(make_line, "ACTIVITIES", 220),
        _body(make_line, "Golang bootcamp by Kominfo with a final project", 240),
    ]


def test_candidate_filter():
    from cv_extractor.domain.models import BBox, TextLine, TextSource

    def mk(t):
        return TextLine(t, BBox(0, 0, 10, 10), 10, 0, TextSource.TEXT_LAYER)

    assert is_heading_candidate(mk("Work Experience"))
    assert is_heading_candidate(mk("PROJECTS https://bit.ly/x"))
    assert not is_heading_candidate(mk("applications."))          # sentence fragment
    assert not is_heading_candidate(mk("and trends"))             # starts lowercase
    assert not is_heading_candidate(mk("Jan 2020 - Mar 2021"))    # date
    assert not is_heading_candidate(mk("Languages : Python, SQL"))  # key: value


def test_unknown_heading_found_through_style_signature(line):
    labeler = DictionaryLabeler({"education": ["education"], "experience": ["work experience"]})
    result = HeadingDetector(labeler).detect(_cv(line))
    texts = [h.text for h in result.headings]
    assert result.strategy == "style_signature"
    assert texts == ["EDUCATION", "WORK EXPERIENCE", "ACTIVITIES"]
    assert result.headings[-1].label is None  # found by style; named later in the pipeline


def test_job_titles_with_other_style_are_not_headings(line):
    result = HeadingDetector(DictionaryLabeler()).detect(_cv(line))
    assert "SOFTWARE ENGINEER, REMOTE" not in [h.text for h in result.headings]


def test_single_prominent_anchor_is_enough(line):
    labeler = DictionaryLabeler({"experience": ["pengalaman kerja"]})
    lines = [
        _heading(line, "PENGALAMAN KERJA", 60),
        _body(line, "Backend Engineer di PT Contoh membuat API Laravel", 80),
        _heading(line, "PENDIDIKAN", 120),
        _body(line, "S1 Teknik Informatika UIN Bandung lulus dengan baik", 140),
    ]
    result = HeadingDetector(labeler).detect(lines)
    assert [h.text for h in result.headings] == ["PENGALAMAN KERJA", "PENDIDIKAN"]


def test_headline_under_name_is_not_promoted(line):
    lines = [
        line("HUYNH TRUNG KHAI", y=20, size=24, bold=True),
        _heading(line, "SAP CONSULTANT", 50),
        _heading(line, "EDUCATION", 80),
        _body(line, "Ton Duc Thang University mathematics and statistics", 100),
        _heading(line, "SKILLS", 140),
        _body(line, "SAP Production Planning and Quality Management", 160),
    ]
    result = HeadingDetector(DictionaryLabeler()).detect(lines)
    assert [h.text for h in result.headings] == ["EDUCATION", "SKILLS"]


def test_no_anchors_means_no_headings(line):
    lines = [_body(line, "Some random text without any section titles here", 20)]
    assert HeadingDetector(DictionaryLabeler()).detect(lines).strategy == "none"
