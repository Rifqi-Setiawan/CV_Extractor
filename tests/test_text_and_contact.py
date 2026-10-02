from cv_extractor.services.contact_extractor import extract_contact, extract_location
from cv_extractor.services.text_cleaning import clean_line, heading_display_text, normalize_heading


class TestTextCleaning:
    def test_strips_bullets_and_private_use_glyphs(self):
        assert clean_line("• Built a POS app") == "Built a POS app"
        assert clean_line(" HTML5, CSS3") == "HTML5, CSS3"
        assert clean_line("e@ Developed a pipeline") == "Developed a pipeline"  # OCR'd bullet

    def test_keeps_normal_words(self):
        assert clean_line("email me") == "email me"

    def test_heading_normalization_drops_urls_and_symbols(self):
        assert normalize_heading("PROJECTS https://bit.ly/abc") == "projects"
        assert normalize_heading("Skills & Others") == "skills & others"
        assert heading_display_text("PROJECTS https://bit.ly/abc") == "PROJECTS"


class TestContactExtractor:
    def test_extracts_email_phone_linkedin(self):
        text = "Sidoarjo, Jawa Timur · 081332496225 · tiara05@gmail.com\nhttps://www.linkedin.com/in/tiararh/"
        c = extract_contact(text)
        assert c.emails == ["tiara05@gmail.com"]
        assert c.phones == ["081332496225"]
        assert c.linkedin == "https://www.linkedin.com/in/tiararh"

    def test_international_phone_with_spaces(self):
        assert extract_contact("+62 821 7883 0078 | a@b.com").phones == ["+62 821 7883 0078"]

    def test_year_ranges_are_not_phone_numbers(self):
        assert extract_contact("2019 - 2023 TELKOM UNIVERSITY 2009-2012").phones == []

    def test_non_profile_linkedin_url_is_still_reported(self):
        assert extract_contact("https://www.linkedin.com/feed/").linkedin == "https://www.linkedin.com/feed"

    def test_location_is_first_non_contact_chunk(self):
        assert extract_location(["Cinunuk, Bandung 40624 • 085759090311 • elsa@gmail.com"]) == "Cinunuk, Bandung 40624"
        assert extract_location(["just one chunk"]) is None
