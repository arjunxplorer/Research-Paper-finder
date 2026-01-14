"""Tests for paper merging and deduplication."""

import pytest
from datetime import datetime

from app.dedup.merge import merge_papers, _merge_group, _paper_to_merged, _is_valid_year
from app.adapters.base import PaperResult, Author


def create_paper(
    title: str,
    source: str,
    doi: str = None,
    year: int = None,
    citation_count: int = None,
    abstract: str = None,
    oa_url: str = None,
    data_quality_flags: list = None,
) -> PaperResult:
    """Create a test paper."""
    return PaperResult(
        title=title,
        source=source,
        doi=doi,
        year=year,
        citation_count=citation_count,
        abstract=abstract,
        oa_url=oa_url,
        authors=[Author(name="Test Author")],
        data_quality_flags=data_quality_flags or [],
    )


class TestMergePapers:
    """Tests for paper merging."""
    
    def test_empty_list(self):
        result = merge_papers([])
        assert result == []
    
    def test_single_paper(self):
        paper = create_paper("Test", "s2")
        result = merge_papers([paper])
        
        assert len(result) == 1
        assert result[0].title == "Test"
    
    def test_merges_by_doi(self):
        paper1 = create_paper("Title 1", "s2", doi="10.1234/abc")
        paper2 = create_paper("Title 2", "openalex", doi="10.1234/abc")
        
        result = merge_papers([paper1, paper2])
        
        # Should merge into one paper
        assert len(result) == 1
        assert "s2" in result[0].sources
        assert "openalex" in result[0].sources
    
    def test_keeps_separate_different_dois(self):
        paper1 = create_paper("Title 1", "s2", doi="10.1234/abc")
        paper2 = create_paper("Title 2", "s2", doi="10.1234/xyz")
        
        result = merge_papers([paper1, paper2])
        
        # Should remain separate
        assert len(result) == 2
    
    def test_merges_similar_titles_no_doi(self):
        paper1 = create_paper("A Survey of Machine Learning", "s2", year=2024)
        paper2 = create_paper("A Survey of Machine Learning", "openalex", year=2024)
        
        result = merge_papers([paper1, paper2])
        
        # Should merge due to identical titles
        assert len(result) == 1
    
    def test_keeps_separate_different_titles(self):
        paper1 = create_paper("Machine Learning Survey", "s2", year=2024)
        paper2 = create_paper("Deep Learning Overview", "s2", year=2024)
        
        result = merge_papers([paper1, paper2])
        
        # Should remain separate
        assert len(result) == 2


class TestMergeGroup:
    """Tests for merging a group of duplicate papers."""
    
    def test_prefers_paper_with_doi(self):
        paper_with_doi = create_paper("Title", "s2", doi="10.1234/abc")
        paper_without_doi = create_paper("Title", "openalex")
        
        result = _merge_group([paper_without_doi, paper_with_doi])
        
        assert result.doi == "10.1234/abc"
    
    def test_fills_missing_abstract(self):
        paper_no_abstract = create_paper("Title", "s2")
        paper_with_abstract = create_paper("Title", "openalex", abstract="An abstract")
        
        result = _merge_group([paper_no_abstract, paper_with_abstract])
        
        assert result.abstract == "An abstract"
    
    def test_takes_higher_citation_count(self):
        paper_low = create_paper("Title", "s2", citation_count=100)
        paper_high = create_paper("Title", "openalex", citation_count=500)
        
        result = _merge_group([paper_low, paper_high])
        
        assert result.citation_count == 500
    
    def test_fills_missing_oa_url(self):
        paper_no_oa = create_paper("Title", "s2")
        paper_with_oa = create_paper("Title", "arxiv", oa_url="https://arxiv.org/pdf/123")
        
        result = _merge_group([paper_no_oa, paper_with_oa])
        
        assert result.oa_url == "https://arxiv.org/pdf/123"
    
    def test_combines_sources(self):
        paper1 = create_paper("Title", "s2")
        paper2 = create_paper("Title", "openalex")
        paper3 = create_paper("Title", "arxiv")
        
        result = _merge_group([paper1, paper2, paper3])
        
        # All sources should be tracked
        assert len(result.sources) == 3


class TestPaperToMerged:
    """Tests for converting PaperResult to MergedPaper."""
    
    def test_creates_doi_url(self):
        paper = create_paper("Title", "s2", doi="10.1234/abc")
        
        result = _paper_to_merged(paper)
        
        assert result.doi_url == "https://doi.org/10.1234/abc"
    
    def test_no_doi_url_without_doi(self):
        paper = create_paper("Title", "s2")
        
        result = _paper_to_merged(paper)
        
        assert result.doi_url is None
    
    def test_generates_uuid(self):
        paper = create_paper("Title", "s2")
        
        result = _paper_to_merged(paper)
        
        # Should have a valid UUID format
        assert len(result.id) == 36
        assert result.id.count("-") == 4
    
    def test_tracks_source_id(self):
        paper = create_paper("Title", "s2")
        paper.source_id = "S2_123456"
        
        result = _paper_to_merged(paper)
        
        assert result.source_ids.get("s2") == "S2_123456"
    
    def test_preserves_data_quality_flags(self):
        paper = create_paper("Title", "s2", data_quality_flags=["bad_year"])
        
        result = _paper_to_merged(paper)
        
        assert "bad_year" in result.data_quality_flags


class TestYearValidation:
    """Tests for year validation in merging."""
    
    def test_is_valid_year_current(self):
        current_year = datetime.now().year
        assert _is_valid_year(current_year) is True
    
    def test_is_valid_year_historical(self):
        assert _is_valid_year(2017) is True
        assert _is_valid_year(1800) is True
    
    def test_is_valid_year_future(self):
        future_year = datetime.now().year + 5
        assert _is_valid_year(future_year) is False
    
    def test_is_valid_year_ancient(self):
        assert _is_valid_year(1750) is False
    
    def test_is_valid_year_none(self):
        assert _is_valid_year(None) is False


class TestMergeYearProtection:
    """Tests to ensure merge never produces future/invalid years."""
    
    def test_merge_never_produces_future_year(self):
        """Critical test: Merged paper should never have a future year."""
        future_year = datetime.now().year + 10
        
        # Create papers with various year combinations
        paper_future = create_paper("Title", "s2", doi="10.1234/abc", year=future_year)
        paper_valid = create_paper("Title", "openalex", doi="10.1234/abc", year=2017)
        
        result = merge_papers([paper_future, paper_valid])
        
        # Merged paper should have the valid year, not the future year
        assert len(result) == 1
        assert result[0].year is None or result[0].year <= datetime.now().year
    
    def test_merge_prefers_valid_year_over_invalid(self):
        """Merge should prefer valid year when one source has invalid year."""
        paper_bad = create_paper("Title", "s2", doi="10.1234/abc", year=1700)
        paper_good = create_paper("Title", "openalex", doi="10.1234/abc", year=2020)
        
        result = _merge_group([paper_bad, paper_good])
        
        # Should use the valid year
        assert result.year == 2020
    
    def test_merge_fills_missing_year_with_valid(self):
        """Merge should fill missing year with valid year from other source."""
        paper_no_year = create_paper("Title", "s2", doi="10.1234/abc")
        paper_with_year = create_paper("Title", "openalex", doi="10.1234/abc", year=2019)
        
        result = _merge_group([paper_no_year, paper_with_year])
        
        assert result.year == 2019
    
    def test_merge_does_not_overwrite_valid_with_invalid(self):
        """Merge should not overwrite valid year with invalid year."""
        paper_valid = create_paper("Title", "s2", doi="10.1234/abc", year=2017)
        paper_invalid = create_paper("Title", "openalex", doi="10.1234/abc", year=2099)
        
        result = _merge_group([paper_valid, paper_invalid])
        
        # Should keep the valid year
        assert result.year == 2017
    
    def test_merge_does_not_overwrite_valid_with_none(self):
        """Merge should not overwrite valid year with None."""
        paper_with_year = create_paper("Title", "s2", doi="10.1234/abc", year=2015)
        paper_no_year = create_paper("Title", "openalex", doi="10.1234/abc")
        
        result = _merge_group([paper_with_year, paper_no_year])
        
        assert result.year == 2015


class TestSameDOIStability:
    """Tests for same DOI = stable year/title after merge."""
    
    def test_same_doi_yields_consistent_year(self):
        """Papers with same DOI should merge to consistent year."""
        paper1 = create_paper("Attention Is All You Need", "s2", doi="10.5555/3295222", year=2017)
        paper2 = create_paper("Attention Is All You Need", "openalex", doi="10.5555/3295222", year=2017)
        paper3 = create_paper("Attention Is All You Need", "crossref", doi="10.5555/3295222", year=2017)
        
        result = merge_papers([paper1, paper2, paper3])
        
        assert len(result) == 1
        assert result[0].year == 2017
    
    def test_same_doi_does_not_create_conflicting_years(self):
        """Same DOI papers with conflicting years should resolve to valid year."""
        # Simulate data error where one source has wrong year
        paper1 = create_paper("Paper", "s2", doi="10.1234/test", year=2017)
        paper2 = create_paper("Paper", "openalex", doi="10.1234/test", year=2018)  # Slight difference
        
        result = merge_papers([paper1, paper2])
        
        assert len(result) == 1
        # Should have one of the valid years (both are valid, so keeps primary)
        assert result[0].year in [2017, 2018]
    
    def test_merged_paper_has_data_quality_flags(self):
        """Merged paper should aggregate data quality flags from all sources."""
        paper1 = create_paper("Title", "s2", doi="10.1234/abc", data_quality_flags=["flag1"])
        paper2 = create_paper("Title", "openalex", doi="10.1234/abc", data_quality_flags=["flag2"])
        
        result = _merge_group([paper1, paper2])
        
        assert "flag1" in result.data_quality_flags
        assert "flag2" in result.data_quality_flags


class TestCitationAgeSanityCheck:
    """Tests for citation age sanity checking (Option D)."""
    
    def test_flags_implausible_citation_age(self):
        """A paper with 10K+ citations can't be from this year."""
        from app.dedup.merge import _apply_citation_age_sanity_check, MergedPaper
        from app.adapters.base import Author
        
        current_year = datetime.now().year
        
        paper = MergedPaper(
            id="test",
            doi=None,
            title="Attention Is All You Need",
            abstract=None,
            year=current_year,  # Implausible - paper from "this year" with 10K citations
            venue="Test",
            authors=[Author(name="Test Author")],
            citation_count=10000,
            citation_source="test",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
        )
        
        result = _apply_citation_age_sanity_check([paper])
        
        assert len(result) == 1
        assert "implausible_citation_age" in result[0].data_quality_flags
    
    def test_corrects_year_from_arxiv_id(self):
        """If arXiv ID is present, infer correct year from it."""
        from app.dedup.merge import _apply_citation_age_sanity_check, MergedPaper
        from app.adapters.base import Author
        
        current_year = datetime.now().year
        
        paper = MergedPaper(
            id="test",
            doi=None,
            title="Attention Is All You Need",
            abstract=None,
            year=current_year,  # Wrong year
            venue="Test",
            authors=[Author(name="Test Author")],
            citation_count=10000,
            citation_source="test",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
            arxiv_id="1706.03762",  # This implies 2017
        )
        
        result = _apply_citation_age_sanity_check([paper])
        
        assert len(result) == 1
        assert result[0].year == 2017
        assert "year_corrected" in result[0].data_quality_flags
    
    def test_does_not_flag_plausible_citation_age(self):
        """A paper with appropriate citations for its age should not be flagged."""
        from app.dedup.merge import _apply_citation_age_sanity_check, MergedPaper
        from app.adapters.base import Author
        
        paper = MergedPaper(
            id="test",
            doi=None,
            title="Some Paper",
            abstract=None,
            year=2017,  # 8+ years old
            venue="Test",
            authors=[Author(name="Test Author")],
            citation_count=10000,  # Plausible for 8-year-old paper
            citation_source="test",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
        )
        
        result = _apply_citation_age_sanity_check([paper])
        
        assert len(result) == 1
        assert "implausible_citation_age" not in result[0].data_quality_flags


class TestSafePostMergeDedup:
    """Tests for safe post-merge deduplication (Option C)."""
    
    def test_merges_same_title_with_different_year_flags(self):
        """Papers with same title but one has implausible_citation_age should merge."""
        from app.dedup.merge import _safe_post_merge_dedup, MergedPaper
        from app.adapters.base import Author
        
        # Paper 1: correct data
        paper1 = MergedPaper(
            id="test1",
            doi=None,
            title="Attention Is All You Need",
            abstract="Abstract text",
            year=2017,
            venue="NeurIPS",
            authors=[Author(name="Ashish Vaswani")],
            citation_count=150000,
            citation_source="semantic_scholar",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
            arxiv_id="1706.03762",
            sources=["semantic_scholar"],
        )
        
        # Paper 2: bad year (flagged)
        paper2 = MergedPaper(
            id="test2",
            doi="10.65215/ne77pf66",
            title="Attention Is All You Need",
            abstract=None,
            year=2025,
            venue=None,
            authors=[Author(name="Ashish Vaswani")],
            citation_count=6000,
            citation_source="openalex",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
            data_quality_flags=["implausible_citation_age"],
            sources=["openalex"],
        )
        
        result = _safe_post_merge_dedup([paper1, paper2])
        
        # Should merge into one paper
        assert len(result) == 1
        # Should have correct year (from paper1)
        assert result[0].year == 2017
        # Should have the higher citation count
        assert result[0].citation_count == 150000
        # Should have merged sources
        assert "semantic_scholar" in result[0].sources
        assert "openalex" in result[0].sources
    
    def test_does_not_merge_different_papers(self):
        """Papers with different titles should not merge."""
        from app.dedup.merge import _safe_post_merge_dedup, MergedPaper
        from app.adapters.base import Author
        
        paper1 = MergedPaper(
            id="test1",
            doi=None,
            title="Attention Is All You Need",
            abstract=None,
            year=2017,
            venue="NeurIPS",
            authors=[Author(name="Ashish Vaswani")],
            citation_count=150000,
            citation_source="semantic_scholar",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
            sources=["semantic_scholar"],
        )
        
        paper2 = MergedPaper(
            id="test2",
            doi=None,
            title="Deep Residual Learning for Image Recognition",
            abstract=None,
            year=2016,
            venue="CVPR",
            authors=[Author(name="Kaiming He")],
            citation_count=100000,
            citation_source="semantic_scholar",
            oa_url=None,
            publisher_url=None,
            doi_url=None,
            topics=[],
            is_survey=False,
            is_open_access=False,
            sources=["semantic_scholar"],
        )
        
        result = _safe_post_merge_dedup([paper1, paper2])
        
        # Should remain as two separate papers
        assert len(result) == 2

