"""Tests for ranking system."""

import pytest
from datetime import datetime
from app.ranking.features import compute_features, normalize_features, PaperFeatures
from app.ranking.scoring import compute_score, FOUNDATIONAL_WEIGHTS, RECENT_WEIGHTS, rank_papers
from app.ranking.explain import generate_why_bullets
from app.dedup.merge import MergedPaper
from app.adapters.base import Author


def create_test_paper(
    title: str = "Test Paper",
    year: int = 2020,
    citation_count: int = 100,
    is_survey: bool = False,
    is_open_access: bool = False,
    venue: str = "Test Journal",
    relevance_score: float = 1.0,
) -> MergedPaper:
    """Create a test paper with default values."""
    return MergedPaper(
        id="test-id",
        doi="10.1234/test",
        title=title,
        abstract="This is a test abstract.",
        year=year,
        venue=venue,
        authors=[Author(name="Test Author")],
        citation_count=citation_count,
        citation_source="test",
        oa_url="https://example.com/paper.pdf" if is_open_access else None,
        publisher_url="https://example.com",
        doi_url="https://doi.org/10.1234/test",
        topics=["AI", "ML"],
        is_survey=is_survey,
        is_open_access=is_open_access,
        relevance_score=relevance_score,
    )


class TestComputeFeatures:
    """Tests for feature extraction."""
    
    def test_log_citations(self):
        paper = create_test_paper(citation_count=100)
        features = compute_features(paper)
        
        # log(1 + 100) ≈ 4.6
        assert features.log_citations > 4.0
        assert features.log_citations < 5.0
    
    def test_zero_citations(self):
        paper = create_test_paper(citation_count=0)
        features = compute_features(paper)
        
        # log(1 + 0) = 0
        assert features.log_citations == 0.0
    
    def test_citation_velocity(self):
        paper = create_test_paper(citation_count=100, year=2020)
        features = compute_features(paper, current_year=2024)
        
        # velocity = 100 / 4 = 25
        # log velocity = log(1 + 25) ≈ 3.26
        assert features.citation_velocity > 3.0
    
    def test_recency_recent_paper(self):
        paper = create_test_paper(year=2024)
        features = compute_features(paper, current_year=2024)
        
        # Very recent paper should have high recency
        assert features.recency > 0.9
    
    def test_recency_old_paper(self):
        paper = create_test_paper(year=2000)
        features = compute_features(paper, current_year=2024)
        
        # Old paper should have low recency
        assert features.recency < 0.1
    
    def test_survey_flag(self):
        survey = create_test_paper(is_survey=True)
        non_survey = create_test_paper(is_survey=False)
        
        assert compute_features(survey).is_survey == 1.0
        assert compute_features(non_survey).is_survey == 0.0
    
    def test_oa_flag(self):
        oa = create_test_paper(is_open_access=True)
        non_oa = create_test_paper(is_open_access=False)
        
        assert compute_features(oa).is_open_access == 1.0
        assert compute_features(non_oa).is_open_access == 0.0


class TestNormalizeFeatures:
    """Tests for feature normalization."""
    
    def test_normalizes_citations(self):
        papers = [
            create_test_paper(citation_count=10),
            create_test_paper(citation_count=100),
            create_test_paper(citation_count=1000),
        ]
        
        papers_with_features = [
            (paper, compute_features(paper))
            for paper in papers
        ]
        
        normalized = normalize_features(papers_with_features)
        
        # Check that citations are normalized to 0-1 range
        for _, features in normalized:
            assert 0.0 <= features.log_citations <= 1.0
    
    def test_min_gets_zero(self):
        papers = [
            create_test_paper(citation_count=10),
            create_test_paper(citation_count=100),
        ]
        
        papers_with_features = [
            (paper, compute_features(paper))
            for paper in papers
        ]
        
        normalized = normalize_features(papers_with_features)
        
        # Min citation paper should have 0
        assert normalized[0][1].log_citations == 0.0
    
    def test_max_gets_one(self):
        papers = [
            create_test_paper(citation_count=10),
            create_test_paper(citation_count=100),
        ]
        
        papers_with_features = [
            (paper, compute_features(paper))
            for paper in papers
        ]
        
        normalized = normalize_features(papers_with_features)
        
        # Max citation paper should have 1
        assert normalized[1][1].log_citations == 1.0


class TestComputeScore:
    """Tests for score computation."""
    
    def test_foundational_weights_citations(self):
        features = PaperFeatures(
            relevance=1.0,
            log_citations=1.0,
            citation_velocity=0.0,
            recency=0.0,
            age_years=10,
            is_survey=0.0,
            is_open_access=0.0,
            venue_signal=0.0,
        )
        
        score = compute_score(features, FOUNDATIONAL_WEIGHTS)
        
        # Should be relevance * 0.45 + citations * 0.35 = 0.80
        assert score == pytest.approx(0.80, rel=0.01)
    
    def test_recent_weights_velocity(self):
        features = PaperFeatures(
            relevance=1.0,
            log_citations=0.0,
            citation_velocity=1.0,
            recency=1.0,
            age_years=1,
            is_survey=0.0,
            is_open_access=0.0,
            venue_signal=0.0,
        )
        
        score = compute_score(features, RECENT_WEIGHTS)
        
        # Should be relevance * 0.55 + velocity * 0.25 + recency * 0.15 = 0.95
        assert score == pytest.approx(0.95, rel=0.01)


class TestRankPapers:
    """Tests for paper ranking."""
    
    def test_returns_correct_count(self):
        papers = [
            create_test_paper(title=f"Paper {i}", citation_count=i * 10)
            for i in range(30)
        ]
        
        ranked = rank_papers(papers, mode="foundational", limit=20)
        
        assert len(ranked) == 20
    
    def test_foundational_prefers_citations(self):
        low_cited = create_test_paper(title="Low", citation_count=10, year=2024)
        high_cited = create_test_paper(title="High", citation_count=10000, year=2020)
        
        ranked = rank_papers([low_cited, high_cited], mode="foundational", limit=2)
        
        # High cited should be first
        assert ranked[0].title == "High"
    
    def test_recent_prefers_velocity(self):
        # Old paper: 1000 citations over ~25 years = ~40 citations/year
        old_high = create_test_paper(title="Old Low Velocity", citation_count=1000, year=2000)
        # New paper: 500 citations over ~2 years = ~250 citations/year (much higher velocity)
        new_medium = create_test_paper(title="New High Velocity", citation_count=500, year=2024)
        
        ranked = rank_papers([old_high, new_medium], mode="recent", limit=2)
        
        # New paper with better velocity and recency should rank higher
        assert ranked[0].title == "New High Velocity"


class TestGenerateWhyBullets:
    """Tests for explanation generation."""
    
    def test_generates_bullets(self):
        paper = create_test_paper(
            citation_count=10000,
            is_survey=True,
            is_open_access=True,
        )
        all_papers = [paper]
        
        bullets = generate_why_bullets(paper, "foundational", all_papers)
        
        assert len(bullets) > 0
        assert len(bullets) <= 4
    
    def test_includes_survey_bullet(self):
        paper = create_test_paper(is_survey=True)
        
        bullets = generate_why_bullets(paper, "foundational", [paper])
        
        # Should mention it's a survey
        assert any("survey" in b.lower() or "review" in b.lower() for b in bullets)
    
    def test_includes_oa_bullet(self):
        paper = create_test_paper(is_open_access=True)
        
        bullets = generate_why_bullets(paper, "foundational", [paper])
        
        # Should mention open access
        assert any("open access" in b.lower() for b in bullets)

