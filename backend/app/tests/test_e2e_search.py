"""End-to-end tests for search functionality.

These tests make real API calls to verify the full search pipeline works correctly.
Run with: pytest app/tests/test_e2e_search.py -v -s
"""

import pytest
import httpx
import asyncio
from typing import Any

# Test configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0  # API calls can take time

# Test queries with expected characteristics
TEST_QUERIES = [
    {
        "query": "attention is all you need transformer",
        "mode": "foundational",
        "expected": {
            "min_results": 10,
            "should_contain_title_keywords": ["attention", "transformer"],
            "min_citations_for_top_result": 1000,  # Foundational papers should be highly cited
        }
    },
    {
        "query": "BERT language model",
        "mode": "foundational",
        "expected": {
            "min_results": 10,
            "should_contain_title_keywords": ["bert", "language"],
            "min_citations_for_top_result": 500,
        }
    },
    {
        "query": "large language models GPT",
        "mode": "recent",
        "expected": {
            "min_results": 5,
            "should_contain_title_keywords": ["language", "model"],
            "recent_year_threshold": 2020,  # Recent mode should favor newer papers
        }
    },
    {
        "query": "graph neural networks",
        "mode": "foundational", 
        "expected": {
            "min_results": 10,
            "should_contain_title_keywords": ["graph", "neural"],
        }
    },
]


class TestSearchEndpoint:
    """Test the /search endpoint with real queries."""

    @pytest.fixture
    def client(self):
        """Create HTTP client."""
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def test_health_check(self, client):
        """Verify API is running."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.parametrize("test_case", TEST_QUERIES)
    def test_search_returns_results(self, client, test_case):
        """Test that search returns expected results."""
        query = test_case["query"]
        mode = test_case["mode"]
        expected = test_case["expected"]

        print(f"\n🔍 Testing: '{query}' ({mode} mode)")

        response = client.get(
            "/search",
            params={"q": query, "mode": mode}
        )

        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        results = data["results"]

        print(f"   Found {len(results)} results")

        # Check minimum results
        min_results = expected.get("min_results", 1)
        assert len(results) >= min_results, \
            f"Expected at least {min_results} results, got {len(results)}"

        # Check results have required fields
        for i, paper in enumerate(results[:5]):
            self._validate_paper_structure(paper, i + 1)

        # Check title keywords if specified
        if "should_contain_title_keywords" in expected:
            keywords = expected["should_contain_title_keywords"]
            self._check_title_keywords(results, keywords)

        # Check citations for foundational mode
        if mode == "foundational" and "min_citations_for_top_result" in expected:
            min_cites = expected["min_citations_for_top_result"]
            top_result = results[0]
            if top_result.get("citationCount"):
                print(f"   Top result citations: {top_result['citationCount']}")
                assert top_result["citationCount"] >= min_cites, \
                    f"Top result should have >= {min_cites} citations"

        # Check recency for recent mode
        if mode == "recent" and "recent_year_threshold" in expected:
            threshold = expected["recent_year_threshold"]
            recent_count = sum(
                1 for p in results[:10] 
                if p.get("year") and p["year"] >= threshold
            )
            print(f"   Papers from {threshold}+: {recent_count}/10")
            assert recent_count >= 5, \
                f"Recent mode should have mostly papers from {threshold}+"

    def _validate_paper_structure(self, paper: dict, rank: int):
        """Validate a paper has all required fields."""
        required_fields = ["id", "title", "score", "whyRecommended"]
        
        for field in required_fields:
            assert field in paper, f"Paper #{rank} missing field: {field}"
        
        # Title should not be empty
        assert paper["title"], f"Paper #{rank} has empty title"
        
        # Score should be a number
        assert isinstance(paper["score"], (int, float)), \
            f"Paper #{rank} score is not a number"
        
        # Should have at least one link
        has_link = any([
            paper.get("doiUrl"),
            paper.get("publisherUrl"),
            paper.get("oaUrl"),
        ])
        # Note: Some papers may not have links, just warn
        if not has_link:
            print(f"   ⚠ Paper #{rank} has no links: {paper['title'][:50]}...")

    def _check_title_keywords(self, results: list, keywords: list):
        """Check that results contain expected keywords."""
        # At least some results should match keywords
        matching = 0
        for paper in results[:10]:
            title_lower = paper["title"].lower()
            if any(kw.lower() in title_lower for kw in keywords):
                matching += 1
        
        print(f"   Results matching keywords {keywords}: {matching}/10")
        assert matching >= 3, \
            f"Expected at least 3 results matching keywords {keywords}"


class TestRankingCorrectness:
    """Test that ranking produces correct ordering."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def test_foundational_ranks_by_citations(self, client):
        """Foundational mode should rank highly-cited papers higher."""
        response = client.get(
            "/search",
            params={"q": "deep learning neural networks", "mode": "foundational"}
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        if len(results) < 5:
            pytest.skip("Not enough results to test ranking")
        
        # Get citation counts for top 10
        citations = []
        for paper in results[:10]:
            cites = paper.get("citationCount") or 0
            citations.append(cites)
            print(f"   #{len(citations)}: {cites} citations - {paper['title'][:50]}...")
        
        # Top papers should generally have more citations
        # Check that top 5 average is higher than bottom 5 average
        if all(c > 0 for c in citations):
            top_5_avg = sum(citations[:5]) / 5
            bottom_5_avg = sum(citations[5:10]) / 5
            print(f"   Top 5 avg: {top_5_avg:.0f}, Bottom 5 avg: {bottom_5_avg:.0f}")
            # Allow some flexibility since relevance also matters
            assert top_5_avg >= bottom_5_avg * 0.5, \
                "Top 5 should have comparable or higher citations than bottom 5"

    def test_recent_ranks_by_recency(self, client):
        """Recent mode should rank newer papers higher."""
        response = client.get(
            "/search",
            params={"q": "machine learning", "mode": "recent"}
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        if len(results) < 5:
            pytest.skip("Not enough results to test ranking")
        
        # Get years for top 10
        years = []
        for paper in results[:10]:
            year = paper.get("year") or 2000
            years.append(year)
            print(f"   #{len(years)}: {year} - {paper['title'][:50]}...")
        
        # Top papers should generally be more recent
        top_5_avg_year = sum(years[:5]) / 5
        bottom_5_avg_year = sum(years[5:10]) / 5
        print(f"   Top 5 avg year: {top_5_avg_year:.0f}, Bottom 5 avg: {bottom_5_avg_year:.0f}")
        
        # Top 5 should be at least as recent as bottom 5
        assert top_5_avg_year >= bottom_5_avg_year - 2, \
            "Top 5 should be at least as recent as bottom 5"

    def test_scores_are_descending(self, client):
        """Results should be ordered by score (descending)."""
        response = client.get(
            "/search",
            params={"q": "computer vision", "mode": "foundational"}
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        scores = [p["score"] for p in results]
        
        # Scores should be in descending order
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], \
                f"Scores not descending: position {i} ({scores[i]}) < position {i+1} ({scores[i+1]})"
        
        print(f"   ✓ All {len(scores)} scores in descending order")


class TestWhyRecommended:
    """Test that explanation bullets are generated correctly."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def test_all_results_have_explanations(self, client):
        """Every result should have at least one explanation bullet."""
        response = client.get(
            "/search",
            params={"q": "reinforcement learning", "mode": "foundational"}
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        for i, paper in enumerate(results):
            bullets = paper.get("whyRecommended", [])
            assert len(bullets) >= 1, \
                f"Paper #{i+1} has no explanation bullets"
            
            # Bullets should be non-empty strings
            for bullet in bullets:
                assert isinstance(bullet, str) and len(bullet) > 5, \
                    f"Invalid bullet: {bullet}"
        
        print(f"   ✓ All {len(results)} papers have explanation bullets")

    def test_explanation_variety(self, client):
        """Different papers should have variety in explanations."""
        response = client.get(
            "/search",
            params={"q": "natural language processing", "mode": "foundational"}
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        all_bullets = set()
        for paper in results:
            for bullet in paper.get("whyRecommended", []):
                all_bullets.add(bullet)
        
        print(f"   Unique explanation types: {len(all_bullets)}")
        for bullet in all_bullets:
            print(f"     - {bullet}")
        
        # Should have at least 3 different types of explanations
        assert len(all_bullets) >= 3, \
            "Should have variety in explanation bullets"


class TestFilters:
    """Test search filters work correctly."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def test_year_filter(self, client):
        """Year filter should limit results to specified range."""
        response = client.get(
            "/search",
            params={
                "q": "machine learning",
                "mode": "foundational",
                "year_min": 2020,
                "year_max": 2024,
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        out_of_range = 0
        for paper in results:
            year = paper.get("year")
            if year:
                if year < 2020 or year > 2024:
                    out_of_range += 1
                    print(f"   ⚠ Out of range: {year} - {paper['title'][:40]}...")
        
        # Most results should be in range (some sources might not filter perfectly)
        in_range = len(results) - out_of_range
        print(f"   In range: {in_range}/{len(results)}")
        assert in_range >= len(results) * 0.7, \
            "At least 70% of results should be in year range"

    def test_survey_filter(self, client):
        """Survey filter should return review papers."""
        response = client.get(
            "/search",
            params={
                "q": "deep learning",
                "mode": "foundational",
                "survey_only": True,
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        survey_keywords = ["survey", "review", "overview", "tutorial"]
        survey_count = 0
        
        for paper in results[:10]:
            title_lower = paper["title"].lower()
            if any(kw in title_lower for kw in survey_keywords):
                survey_count += 1
        
        print(f"   Survey papers in results: {survey_count}/10")
        # At least some should be surveys
        assert survey_count >= 2, "Survey filter should return survey papers"


class TestModeComparison:
    """Compare foundational vs recent mode results."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def test_modes_produce_different_rankings(self, client):
        """Same query with different modes should produce different top results."""
        query = "neural networks"
        
        foundational = client.get(
            "/search",
            params={"q": query, "mode": "foundational"}
        )
        recent = client.get(
            "/search",
            params={"q": query, "mode": "recent"}
        )
        
        assert foundational.status_code == 200
        assert recent.status_code == 200
        
        found_results = foundational.json()["results"]
        recent_results = recent.json()["results"]
        
        if len(found_results) < 5 or len(recent_results) < 5:
            pytest.skip("Not enough results to compare modes")
        
        # Get top 5 titles from each
        found_titles = {p["title"] for p in found_results[:5]}
        recent_titles = {p["title"] for p in recent_results[:5]}
        
        # Calculate overlap
        overlap = found_titles & recent_titles
        print(f"   Foundational top 5: {len(found_titles)} unique")
        print(f"   Recent top 5: {len(recent_titles)} unique")
        print(f"   Overlap: {len(overlap)}")
        
        # There should be some difference (not all the same)
        # But could have some overlap for very famous papers
        assert len(overlap) < 5, \
            "Modes should produce somewhat different top results"

        # Recent mode should have newer papers on average
        found_years = [p.get("year") or 2000 for p in found_results[:10]]
        recent_years = [p.get("year") or 2000 for p in recent_results[:10]]
        
        found_avg = sum(found_years) / len(found_years)
        recent_avg = sum(recent_years) / len(recent_years)
        
        print(f"   Foundational avg year: {found_avg:.0f}")
        print(f"   Recent avg year: {recent_avg:.0f}")
        
        assert recent_avg >= found_avg, \
            "Recent mode should have newer papers on average"


class TestAnchorPapers:
    """Test that well-known anchor papers appear with correct metadata.
    
    These tests verify that foundational papers are returned with
    correct year, title, and other metadata.
    """

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    # Anchor paper definitions: (query, expected_title_keywords, expected_year)
    ANCHOR_PAPERS = [
        {
            "query": "attention is all you need transformer",
            "title_must_contain": ["attention", "need"],
            "expected_year": 2017,
            "min_citations": 10000,
        },
        {
            "query": "deep residual learning image recognition resnet",
            "title_must_contain": ["deep", "residual"],
            "expected_year": 2016,  # CVPR 2016
            "min_citations": 50000,
        },
        {
            "query": "BERT pre-training language representation",
            "title_must_contain": ["bert"],
            "expected_year": 2019,  # NAACL 2019
            "min_citations": 30000,
        },
        {
            "query": "dropout regularization neural networks",
            "title_must_contain": ["dropout"],
            "expected_year": 2014,  # JMLR 2014
            "min_citations": 20000,
        },
        {
            "query": "batch normalization accelerating deep network",
            "title_must_contain": ["batch", "normalization"],
            "expected_year": 2015,
            "min_citations": 20000,
        },
    ]

    @pytest.mark.parametrize("anchor", ANCHOR_PAPERS)
    def test_anchor_paper_appears_with_correct_year(self, client, anchor):
        """Verify anchor papers appear in results with correct year."""
        response = client.get(
            "/search",
            params={
                "q": anchor["query"],
                "mode": "foundational",
                "bypass_cache": True,  # Ensure fresh results
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        # Find the anchor paper in results
        anchor_paper = None
        for paper in results:
            title_lower = paper["title"].lower()
            if all(kw.lower() in title_lower for kw in anchor["title_must_contain"]):
                anchor_paper = paper
                break
        
        assert anchor_paper is not None, \
            f"Anchor paper with keywords {anchor['title_must_contain']} not found in results"
        
        print(f"\n   Found: {anchor_paper['title']}")
        print(f"   Year: {anchor_paper.get('year')} (expected: {anchor['expected_year']})")
        print(f"   Citations: {anchor_paper.get('citationCount')}")
        
        # Verify year is correct
        assert anchor_paper.get("year") == anchor["expected_year"], \
            f"Anchor paper has wrong year: {anchor_paper.get('year')} != {anchor['expected_year']}"
    
    def test_transformer_attention_paper_is_2017(self, client):
        """Specific test: 'Attention Is All You Need' must be year 2017."""
        response = client.get(
            "/search",
            params={
                "q": "attention is all you need transformer architecture",
                "mode": "foundational",
                "bypass_cache": True,
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        # Find the paper
        attention_paper = None
        for paper in results:
            if "attention" in paper["title"].lower() and "need" in paper["title"].lower():
                attention_paper = paper
                break
        
        if attention_paper:
            print(f"\n   Title: {attention_paper['title']}")
            print(f"   Year: {attention_paper.get('year')}")
            print(f"   DOI: {attention_paper.get('doi')}")
            print(f"   Citations: {attention_paper.get('citationCount')}")
            
            # THE CRITICAL CHECK: Year must be 2017, not 2025 or any other value
            assert attention_paper.get("year") == 2017, \
                f"CRITICAL ERROR: 'Attention Is All You Need' has year {attention_paper.get('year')}, should be 2017!"
            
            # Year should never be in the future
            from datetime import datetime
            current_year = datetime.now().year
            assert attention_paper.get("year") is None or attention_paper.get("year") <= current_year, \
                f"Paper has future year: {attention_paper.get('year')}"
        else:
            pytest.skip("Attention paper not found in results")

    def test_no_papers_have_future_years(self, client):
        """Verify no papers in results have future years."""
        from datetime import datetime
        current_year = datetime.now().year
        
        response = client.get(
            "/search",
            params={
                "q": "machine learning deep neural networks",
                "mode": "foundational",
                "bypass_cache": True,
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        future_year_papers = []
        for paper in results:
            year = paper.get("year")
            if year and year > current_year:
                future_year_papers.append({
                    "title": paper["title"][:50],
                    "year": year,
                })
        
        assert len(future_year_papers) == 0, \
            f"Found papers with future years: {future_year_papers}"
        
        print(f"\n   ✓ All {len(results)} papers have valid years (no future years)")

    def test_results_return_20_papers(self, client):
        """Verify search returns exactly 20 results."""
        response = client.get(
            "/search",
            params={
                "q": "neural network deep learning",
                "mode": "foundational",
            }
        )
        
        assert response.status_code == 200
        results = response.json()["results"]
        
        # Should return exactly 20 papers (the configured limit)
        assert len(results) == 20, \
            f"Expected 20 results, got {len(results)}"


def run_manual_test():
    """Run tests manually without pytest."""
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    
    print("\n" + "="*60)
    print("MANUAL SEARCH VERIFICATION TEST")
    print("="*60)
    
    # Test 1: Basic search
    print("\n📋 Test 1: Basic Foundational Search")
    print("-" * 40)
    response = client.get(
        "/search",
        params={"q": "transformer attention mechanism", "mode": "foundational"}
    )
    
    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code}")
        return
    
    data = response.json()
    print(f"✅ Found {len(data['results'])} results")
    print(f"   Total candidates: {data['totalCandidates']}")
    print(f"   Sources: {data['sourceStats']}")
    
    print("\n   Top 5 Results:")
    for i, paper in enumerate(data["results"][:5], 1):
        cites = paper.get("citationCount", "N/A")
        year = paper.get("year", "N/A")
        print(f"   {i}. [{year}] {paper['title'][:60]}...")
        print(f"      Citations: {cites} | Score: {paper['score']:.3f}")
        print(f"      Why: {', '.join(paper['whyRecommended'][:2])}")
    
    # Test 2: Recent mode
    print("\n📋 Test 2: Recent Mode Search")
    print("-" * 40)
    response = client.get(
        "/search",
        params={"q": "large language models", "mode": "recent"}
    )
    
    data = response.json()
    print(f"✅ Found {len(data['results'])} results")
    
    print("\n   Top 5 Results:")
    for i, paper in enumerate(data["results"][:5], 1):
        cites = paper.get("citationCount", "N/A")
        year = paper.get("year", "N/A")
        print(f"   {i}. [{year}] {paper['title'][:60]}...")
        print(f"      Citations: {cites} | Score: {paper['score']:.3f}")
    
    print("\n" + "="*60)
    print("✅ Manual tests completed!")
    print("="*60)


if __name__ == "__main__":
    run_manual_test()

