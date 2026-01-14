"""Tests for similarity computation."""

import pytest
from app.dedup.similarity import (
    title_similarity,
    author_similarity,
    year_similarity,
    are_likely_same_paper,
    compute_merge_priority,
)
from app.adapters.base import PaperResult, Author


class TestTitleSimilarity:
    """Tests for title similarity."""
    
    def test_identical_titles(self):
        sim = title_similarity("Hello World", "Hello World")
        assert sim == 1.0
    
    def test_case_insensitive(self):
        sim = title_similarity("Hello World", "hello world")
        assert sim == 1.0
    
    def test_word_order_tolerance(self):
        sim = title_similarity("Machine Learning Survey", "Survey of Machine Learning")
        assert sim > 0.8
    
    def test_different_titles(self):
        sim = title_similarity("Hello World", "Goodbye Moon")
        assert sim < 0.5
    
    def test_empty_strings(self):
        assert title_similarity("", "") == 0.0
        assert title_similarity("Hello", "") == 0.0


class TestAuthorSimilarity:
    """Tests for author similarity."""
    
    def test_same_first_author(self):
        paper1 = PaperResult(
            title="Paper 1",
            source="test",
            authors=[Author(name="John Smith")],
        )
        paper2 = PaperResult(
            title="Paper 2",
            source="test",
            authors=[Author(name="John Smith")],
        )
        sim = author_similarity(paper1, paper2)
        assert sim == 1.0
    
    def test_different_first_author(self):
        paper1 = PaperResult(
            title="Paper 1",
            source="test",
            authors=[Author(name="John Smith")],
        )
        paper2 = PaperResult(
            title="Paper 2",
            source="test",
            authors=[Author(name="Jane Doe")],
        )
        sim = author_similarity(paper1, paper2)
        assert sim < 0.5
    
    def test_no_authors(self):
        paper1 = PaperResult(title="Paper 1", source="test", authors=[])
        paper2 = PaperResult(title="Paper 2", source="test", authors=[])
        sim = author_similarity(paper1, paper2)
        assert sim == 0.5  # Uncertain


class TestYearSimilarity:
    """Tests for year similarity."""
    
    def test_same_year(self):
        assert year_similarity(2024, 2024) == 1.0
    
    def test_off_by_one(self):
        sim = year_similarity(2024, 2023)
        assert sim == 0.9
    
    def test_off_by_two(self):
        sim = year_similarity(2024, 2022)
        assert sim == 0.7
    
    def test_very_different(self):
        sim = year_similarity(2024, 2000)
        assert sim == 0.0
    
    def test_none_values(self):
        assert year_similarity(None, 2024) == 0.5
        assert year_similarity(2024, None) == 0.5
        assert year_similarity(None, None) == 0.5


class TestAreLikelySamePaper:
    """Tests for paper matching."""
    
    def test_same_doi(self):
        paper1 = PaperResult(
            title="Paper 1",
            source="test",
            doi="10.1234/abc",
        )
        paper2 = PaperResult(
            title="Different Title",
            source="test",
            doi="10.1234/abc",
        )
        assert are_likely_same_paper(paper1, paper2) is True
    
    def test_different_doi(self):
        paper1 = PaperResult(
            title="Paper 1",
            source="test",
            doi="10.1234/abc",
        )
        paper2 = PaperResult(
            title="Paper 1",
            source="test",
            doi="10.1234/xyz",
        )
        assert are_likely_same_paper(paper1, paper2) is False
    
    def test_very_similar_title_no_doi(self):
        paper1 = PaperResult(
            title="A Survey of Machine Learning Techniques",
            source="test",
            year=2024,
            authors=[Author(name="John Smith")],
        )
        paper2 = PaperResult(
            title="A Survey of Machine Learning Techniques",
            source="test",
            year=2024,
            authors=[Author(name="John Smith")],
        )
        assert are_likely_same_paper(paper1, paper2) is True
    
    def test_different_papers(self):
        paper1 = PaperResult(
            title="Machine Learning for Healthcare",
            source="test",
            year=2024,
        )
        paper2 = PaperResult(
            title="Deep Learning for Finance",
            source="test",
            year=2020,
        )
        assert are_likely_same_paper(paper1, paper2) is False


class TestComputeMergePriority:
    """Tests for merge priority computation."""
    
    def test_doi_boosts_priority(self):
        paper_with_doi = PaperResult(
            title="Paper",
            source="test",
            doi="10.1234/abc",
        )
        paper_without_doi = PaperResult(
            title="Paper",
            source="test",
        )
        assert compute_merge_priority(paper_with_doi) > compute_merge_priority(paper_without_doi)
    
    def test_abstract_boosts_priority(self):
        paper_with_abstract = PaperResult(
            title="Paper",
            source="test",
            abstract="This is an abstract",
        )
        paper_without_abstract = PaperResult(
            title="Paper",
            source="test",
        )
        assert compute_merge_priority(paper_with_abstract) > compute_merge_priority(paper_without_abstract)
    
    def test_source_priority_ordering(self):
        s2_paper = PaperResult(title="Paper", source="semantic_scholar")
        oa_paper = PaperResult(title="Paper", source="openalex")
        arxiv_paper = PaperResult(title="Paper", source="arxiv")
        
        assert compute_merge_priority(s2_paper) > compute_merge_priority(oa_paper)
        assert compute_merge_priority(oa_paper) > compute_merge_priority(arxiv_paper)

