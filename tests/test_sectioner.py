from cv_extractor.services.heading_detector import DetectedHeading
from cv_extractor.services.sectioner import build_header_sections, parse_header, split_into_sections


def _h(index, text, label):
    return DetectedHeading(index, text, label, "dictionary", 100.0)


def test_text_is_copied_verbatim_into_sections(line):
    lines = [
        line("Jane Doe", y=10, size=20),
        line("SKILLS", y=50),
        line("Python, SQL", y=70),
        line("EDUCATION", y=100),
        line("Telkom University", y=120),
    ]
    header, sections = split_into_sections(lines, [_h(1, "SKILLS", "skills"), _h(3, "EDUCATION", "education")])
    assert [l.text for l in header] == ["Jane Doe"]
    assert [(s.label, s.text) for s in sections] == [("skills", "Python, SQL"), ("education", "Telkom University")]


def test_same_label_in_a_row_becomes_sub_heading(line):
    lines = [line("KEMAMPUAN", y=10), line("TEKNIK SKILL", y=30), line("MS Office", y=50),
             line("SOFT SKILL", y=70), line("Kerja tim", y=90)]
    headings = [_h(0, "KEMAMPUAN", "skills"), _h(1, "TEKNIK SKILL", "skills"), _h(3, "SOFT SKILL", "skills")]
    _, sections = split_into_sections(lines, headings)
    assert len(sections) == 1
    assert sections[0].text == "TEKNIK SKILL\nMS Office\nSOFT SKILL\nKerja tim"


def test_later_page_continues_previous_section(line):
    lines = [line("EXPERIENCE", y=10), line("Job A", y=30), line("Job B continued", y=30, page=1)]
    _, sections = split_into_sections(lines, [_h(0, "EXPERIENCE", "experience")])
    assert sections[0].text == "Job A\nJob B continued"


def test_header_parsing_name_headline_contact_summary(line):
    header = [
        line("TRAN DAI DUONG", y=10, size=26),
        line("Software Engineer", y=40, size=18),
        line("Ho Chi Minh · 0973703214 · tran@mail.com", y=60),
        line("I am a software engineer with eight years of experience", y=80),
        line("in embedded testing, backend development and IT support", y=92),
        line("for global clients.", y=104),
    ]
    parts = parse_header(header)
    assert parts.name == "Tran Dai Duong"
    assert parts.headline == "Software Engineer"
    assert parts.contact_lines == ["Ho Chi Minh · 0973703214 · tran@mail.com"]
    assert [l.text for l in parts.summary_lines][-1] == "for global clients."
    assert build_header_sections(parts)[0].label == "summary"


def test_name_with_academic_title_and_url_line(line):
    header = [
        line("linkedin.com/in/andika-rafika", y=30, size=12),
        line("Andika Rafika Ningsih, S.Pd", y=10, size=11),
    ]
    assert parse_header(header).name == "Andika Rafika Ningsih, S.Pd"
