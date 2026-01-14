"""Tests for normalization utilities."""

import pytest
from app.dedup.normalize import (
    normalize_title,
    normalize_author_name,
    normalize_doi,
    normalize_year,
    normalize_venue,
    detect_survey,
    compute_work_key,
    detect_work_type,
    WORK_TYPE_JOURNAL,
    WORK_TYPE_CONFERENCE,
    WORK_TYPE_BOOK,
    WORK_TYPE_CHAPTER,
    WORK_TYPE_PREPRINT,
    WORK_TYPE_SURVEY,
)
from app.adapters.base import PaperResult, Author


class TestNormalizeTitle:
    """Tests for title normalization."""
    
    def test_basic_normalization(self):
        assert normalize_title("Hello World") == "hello world"
    
    def test_removes_extra_whitespace(self):
        assert normalize_title("Hello   World") == "hello world"
    
    def test_removes_leading_articles(self):
        assert normalize_title("The Quick Brown Fox") == "quick brown fox"
        assert normalize_title("A Study of AI") == "study of ai"
        assert normalize_title("An Overview") == "overview"
    
    def test_strips_trailing_punctuation(self):
        assert normalize_title("Hello World.") == "hello world"
    
    def test_removes_html_tags(self):
        assert normalize_title("<b>Hello</b> World") == "hello world"
    
    def test_handles_empty_string(self):
        assert normalize_title("") == ""
    
    def test_unicode_normalization(self):
        # Composed vs decomposed characters
        title = "café"
        result = normalize_title(title)
        assert "cafe" in result or "café" in result


class TestNormalizeAuthorName:
    """Tests for author name normalization."""
    
    def test_basic_normalization(self):
        assert normalize_author_name("John Doe") == "john doe"
    
    def test_removes_punctuation(self):
        assert normalize_author_name("John, Doe") == "john doe"
    
    def test_removes_quotes(self):
        assert normalize_author_name("John \"Johnny\" Doe") == "john johnny doe"
    
    def test_handles_empty_string(self):
        assert normalize_author_name("") == ""


class TestNormalizeDoi:
    """Tests for DOI normalization."""
    
    def test_returns_clean_doi(self):
        assert normalize_doi("10.1234/abc") == "10.1234/abc"
    
    def test_removes_https_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
    
    def test_removes_http_prefix(self):
        assert normalize_doi("http://doi.org/10.1234/abc") == "10.1234/abc"
    
    def test_removes_doi_prefix(self):
        assert normalize_doi("doi:10.1234/abc") == "10.1234/abc"
        assert normalize_doi("DOI:10.1234/abc") == "10.1234/abc"
    
    def test_returns_none_for_invalid(self):
        assert normalize_doi("invalid") is None
        assert normalize_doi("") is None
        assert normalize_doi(None) is None
    
    def test_strips_whitespace(self):
        assert normalize_doi("  10.1234/abc  ") == "10.1234/abc"


class TestNormalizeYear:
    """Tests for year normalization."""
    
    def test_valid_year(self):
        assert normalize_year(2024) == 2024
    
    def test_too_old(self):
        assert normalize_year(1700) is None
    
    def test_too_future(self):
        assert normalize_year(2200) is None
    
    def test_none_input(self):
        assert normalize_year(None) is None


class TestNormalizeVenue:
    """Tests for venue normalization."""
    
    def test_basic_normalization(self):
        assert normalize_venue("Nature") == "Nature"
    
    def test_removes_suffixes(self):
        assert normalize_venue("Journal (Online)") == "Journal"
        assert normalize_venue("Journal (Print)") == "Journal"
    
    def test_handles_none(self):
        assert normalize_venue(None) is None
    
    def test_handles_empty(self):
        assert normalize_venue("") is None
        assert normalize_venue("   ") is None


class TestDetectSurvey:
    """Tests for survey/review detection."""
    
    def test_detects_survey_keyword(self):
        paper = PaperResult(
            title="A Survey of Machine Learning",
            source="test",
        )
        assert detect_survey(paper) is True
    
    def test_detects_review_keyword(self):
        paper = PaperResult(
            title="A Review of Deep Learning",
            source="test",
        )
        assert detect_survey(paper) is True
    
    def test_detects_overview_keyword(self):
        paper = PaperResult(
            title="An Overview of Neural Networks",
            source="test",
        )
        assert detect_survey(paper) is True
    
    def test_non_survey_paper(self):
        paper = PaperResult(
            title="A Novel Approach to Machine Learning",
            source="test",
        )
        assert detect_survey(paper) is False
    
    def test_respects_is_survey_flag(self):
        paper = PaperResult(
            title="Some Paper",
            source="test",
            is_survey=True,
        )
        assert detect_survey(paper) is True


class TestComputeWorkKey:
    """Tests for work_key computation."""
    
    def test_doi_takes_priority(self):
        paper = PaperResult(
            title="Some Paper",
            source="semantic_scholar",
            doi="10.1234/abc",
            source_id="s2_12345",
            authors=[Author(name="John Smith")],
            year=2020,
        )
        key = compute_work_key(paper)
        assert key == "doi:10.1234/abc"
    
    def test_pmid_takes_priority_over_title(self):
        paper = PaperResult(
            title="Some Paper",
            source="pubmed",
            source_id="12345678",
            authors=[Author(name="John Smith")],
            year=2020,
        )
        key = compute_work_key(paper)
        assert key == "pmid:12345678"
    
    def test_arxiv_takes_priority_over_title(self):
        paper = PaperResult(
            title="Some Paper",
            source="arxiv",
            source_id="2301.12345v2",
            authors=[Author(name="John Smith")],
            year=2023,
        )
        key = compute_work_key(paper)
        # Should strip version number
        assert key == "arxiv:2301.12345"
    
    def test_arxiv_id_field_used_from_any_source(self):
        """Papers with arxiv_id field should cluster by arXiv ID regardless of source."""
        paper = PaperResult(
            title="Attention Is All You Need",
            source="semantic_scholar",
            source_id="204e3073870fae3d05bcbc2f6a8e263d9b72e776",
            arxiv_id="1706.03762",  # From externalIds
            authors=[Author(name="Ashish Vaswani")],
            year=2017,
        )
        key = compute_work_key(paper)
        assert key == "arxiv:1706.03762"
    
    def test_arxiv_id_strips_version(self):
        """ArXiv ID with version suffix should be normalized."""
        paper = PaperResult(
            title="Some Paper",
            source="semantic_scholar",
            arxiv_id="1706.03762v2",
            authors=[Author(name="Test Author")],
            year=2017,
        )
        key = compute_work_key(paper)
        assert key == "arxiv:1706.03762"
    
    def test_arxiv_id_takes_priority_over_s2(self):
        """ArXiv ID should take priority over S2 ID."""
        paper = PaperResult(
            title="Attention Is All You Need",
            source="semantic_scholar",
            source_id="abc123",
            arxiv_id="1706.03762",
            authors=[Author(name="Test Author")],
            year=2017,
        )
        key = compute_work_key(paper)
        # arxiv_id should win over s2 source_id
        assert key == "arxiv:1706.03762"
    
    def test_suspicious_doi_skipped(self):
        """DOIs from suspicious registrants should be skipped."""
        paper = PaperResult(
            title="Attention Is All You Need",
            source="openalex",
            doi="10.65215/ne77pf66",  # Suspicious registrant
            arxiv_id="1706.03762",
            authors=[Author(name="Test Author")],
            year=2025,
        )
        key = compute_work_key(paper)
        # Should skip suspicious DOI and use arXiv ID
        assert key == "arxiv:1706.03762"
    
    def test_s2_takes_priority_over_title(self):
        paper = PaperResult(
            title="Some Paper",
            source="semantic_scholar",
            source_id="abc123def456",
            authors=[Author(name="John Smith")],
            year=2020,
        )
        key = compute_work_key(paper)
        assert key == "s2:abc123def456"
    
    def test_title_hash_fallback(self):
        paper = PaperResult(
            title="Some Paper With No ID",
            source="openalex",
            authors=[Author(name="John Smith")],
            year=2020,
        )
        key = compute_work_key(paper)
        assert key.startswith("title_hash:")
    
    def test_same_title_author_year_same_hash(self):
        paper1 = PaperResult(
            title="Attention Is All You Need",
            source="openalex",
            authors=[Author(name="Ashish Vaswani")],
            year=2017,
        )
        paper2 = PaperResult(
            title="Attention Is All You Need",
            source="crossref",
            authors=[Author(name="Ashish Vaswani")],
            year=2017,
        )
        assert compute_work_key(paper1) == compute_work_key(paper2)


class TestDetectWorkType:
    """Tests for work type detection."""
    
    def test_detects_survey(self):
        paper = PaperResult(
            title="A Survey of Machine Learning",
            source="test",
            venue="ACM Computing Surveys",
        )
        assert detect_work_type(paper) == WORK_TYPE_SURVEY
    
    def test_detects_book(self):
        paper = PaperResult(
            title="Deep Learning",
            source="test",
            venue="MIT Press",
        )
        assert detect_work_type(paper) == WORK_TYPE_BOOK
    
    def test_detects_chapter(self):
        paper = PaperResult(
            title="Introduction to Neural Networks",
            source="test",
            venue="Handbook of Machine Learning, Chapter 1",
        )
        assert detect_work_type(paper) == WORK_TYPE_CHAPTER
    
    def test_detects_preprint_from_arxiv_source(self):
        paper = PaperResult(
            title="New Model Architecture",
            source="arxiv",
            venue="arXiv cs.LG",
        )
        assert detect_work_type(paper) == WORK_TYPE_PREPRINT
    
    def test_detects_conference(self):
        paper = PaperResult(
            title="Attention Is All You Need",
            source="test",
            venue="NeurIPS 2017",
        )
        assert detect_work_type(paper) == WORK_TYPE_CONFERENCE
    
    def test_detects_journal(self):
        paper = PaperResult(
            title="Some Research Paper",
            source="test",
            venue="Journal of Artificial Intelligence Research",
        )
        assert detect_work_type(paper) == WORK_TYPE_JOURNAL
    
    def test_icml_is_conference(self):
        paper = PaperResult(
            title="Some Paper",
            source="test",
            venue="Proceedings of ICML 2023",
        )
        assert detect_work_type(paper) == WORK_TYPE_CONFERENCE

