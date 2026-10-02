from cv_extractor.services import layout

PAGE_WIDTH = 600


def _two_column_page(make_line):
    left = [make_line(f"left column sentence number {i}", y=100 + i * 15, x=40, width=200) for i in range(10)]
    right = [make_line(f"right column sentence number {i}", y=100 + i * 15, x=350, width=200) for i in range(10)]
    return left, right


def test_detects_two_columns(line):
    left, right = _two_column_page(line)
    split = layout.find_column_split(left + right, PAGE_WIDTH)
    assert split is not None and 240 <= split <= 350


def test_right_aligned_dates_are_not_a_column(line):
    lines = []
    for i in range(6):
        lines.append(line(f"Backend Engineer at company {i}", y=100 + i * 40, x=40, width=200))
        lines.append(line("Jan 2020 - Mei 2023", y=100 + i * 40, x=450, width=100))
        lines.append(line("Membuat aplikasi dengan Laravel dan Vue untuk klien", y=115 + i * 40, x=40, width=500))
    assert layout.find_column_split(lines, PAGE_WIDTH) is None


def test_reading_order_reads_left_column_first(line):
    left, right = _two_column_page(line)
    split = layout.find_column_split(left + right, PAGE_WIDTH)
    ordered = layout.reading_order(layout.assign_columns(right + left, split))
    assert [l.text for l in ordered[:10]] == [l.text for l in left]
    assert ordered[10].text.startswith("right")


def test_full_width_title_comes_first(line):
    left, right = _two_column_page(line)
    title = line("JANE DOE", y=40, x=40, width=520, size=24)
    lines = left + right + [title]
    ordered = layout.reading_order(layout.assign_columns(lines, layout.find_column_split(lines, PAGE_WIDTH)))
    assert ordered[0].text == "JANE DOE"


def test_merge_same_row_joins_title_and_date(line):
    title = line("Technical Leader", y=100, x=38, width=100, bold=True)
    date = line("Januari 2024 - April 2025", y=100, x=418, width=140, bold=True)
    merged = layout.merge_same_row([title, date])
    assert len(merged) == 1
    assert merged[0].text.startswith("Technical Leader") and merged[0].text.endswith("April 2025")


def test_gap_above_is_computed(line):
    ordered = layout.reading_order([line("a b c", y=100), line("d e f", y=150)])
    assert ordered[0].gap_above is None
    assert ordered[1].gap_above == 150 - (100 + 12)


def test_removes_page_numbers_and_repeated_footers(line):
    p0 = [line("Body text one two", y=100), line("Jane Doe - CV", y=800, page=0), line("1", y=810, page=0)]
    p1 = [line("Body text three", y=100, page=1), line("Jane Doe - CV", y=800, page=1), line("2", y=810, page=1)]
    cleaned = layout.remove_page_noise([p0, p1], [842, 842])
    assert [l.text for l in cleaned[0]] == ["Body text one two"]
    assert [l.text for l in cleaned[1]] == ["Body text three"]
