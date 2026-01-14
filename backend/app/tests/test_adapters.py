"""Unit tests for source adapters with fixture JSON data.

These tests verify that each adapter correctly parses year, DOI, and title
from raw source JSON, and that year sanity guards work correctly.
"""

import pytest
from datetime import datetime

from app.adapters.openalex import OpenAlexAdapter
from app.adapters.semantic_scholar import SemanticScholarAdapter
from app.adapters.crossref import CrossrefAdapter
from app.adapters.pubmed import PubMedAdapter
from app.adapters.arxiv import ArxivAdapter
from app.adapters.base import validate_year


# Fixture JSON data for each source
OPENALEX_FIXTURE = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.5555/3295222.3295349",
    "title": "Attention Is All You Need",
    "display_name": "Attention Is All You Need",
    "publication_year": 2017,
    "type": "article",
    "authorships": [
        {
            "author": {"display_name": "Ashish Vaswani"},
            "institutions": [{"display_name": "Google Brain"}],
        },
        {
            "author": {"display_name": "Noam Shazeer"},
            "institutions": [],
        },
    ],
    "cited_by_count": 50000,
    "concepts": [
        {"display_name": "Transformer", "score": 0.9},
        {"display_name": "Attention", "score": 0.85},
    ],
    "open_access": {"is_oa": True, "oa_url": "https://arxiv.org/pdf/1706.03762.pdf"},
    "primary_location": {"source": {"display_name": "NeurIPS"}},
    "abstract_inverted_index": None,
}

OPENALEX_FUTURE_YEAR_FIXTURE = {
    "id": "https://openalex.org/W9999999999",
    "doi": "https://doi.org/10.1234/future",
    "title": "Paper From The Future",
    "publication_year": 2099,  # Invalid future year
    "type": "article",
    "authorships": [],
    "cited_by_count": 0,
    "concepts": [],
    "open_access": {"is_oa": False},
    "primary_location": None,
}

SEMANTIC_SCHOLAR_FIXTURE = {
    "paperId": "204e3073870fae3d05bcbc2f6a8e263d9b72e776",
    "title": "Attention Is All You Need",
    "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
    "year": 2017,
    "venue": "NIPS",
    "authors": [
        {"name": "Ashish Vaswani"},
        {"name": "Noam Shazeer"},
    ],
    "citationCount": 51000,
    "isOpenAccess": True,
    "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762.pdf"},
    "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
    "publicationTypes": ["JournalArticle", "Conference"],
    "s2FieldsOfStudy": [{"category": "Computer Science"}],
}

SEMANTIC_SCHOLAR_BAD_YEAR_FIXTURE = {
    "paperId": "badyear123",
    "title": "Paper With Bad Year",
    "abstract": None,
    "year": 1750,  # Invalid - before 1800
    "venue": None,
    "authors": [],
    "citationCount": 0,
    "isOpenAccess": False,
    "openAccessPdf": None,
    "externalIds": {},
    "publicationTypes": [],
    "s2FieldsOfStudy": [],
}

CROSSREF_FIXTURE = {
    "DOI": "10.5555/3295222.3295349",
    "title": ["Attention Is All You Need"],
    "author": [
        {"given": "Ashish", "family": "Vaswani", "affiliation": []},
        {"given": "Noam", "family": "Shazeer", "affiliation": []},
    ],
    "published-print": {"date-parts": [[2017, 6, 12]]},
    "published-online": {"date-parts": [[2017, 6, 10]]},
    "issued": {"date-parts": [[2017]]},
    "container-title": ["Advances in Neural Information Processing Systems"],
    "type": "proceedings-article",
    "abstract": None,
    "is-referenced-by-count": 49000,
    "URL": "https://papers.nips.cc/paper/7181-attention-is-all-you-need",
}

CROSSREF_ONLY_ISSUED_FIXTURE = {
    "DOI": "10.1234/issued-only",
    "title": ["Paper With Only Issued Date"],
    "author": [],
    "issued": {"date-parts": [[2020, 3]]},
    "container-title": ["Some Journal"],
    "type": "article",
    "is-referenced-by-count": 10,
}

CROSSREF_ONLY_PUBLISHED_ONLINE_FIXTURE = {
    "DOI": "10.1234/online-only",
    "title": ["Paper With Only Online Date"],
    "author": [],
    "published-online": {"date-parts": [[2021, 5, 15]]},
    "container-title": ["Online Journal"],
    "type": "article",
    "is-referenced-by-count": 5,
}


class TestValidateYear:
    """Tests for the year validation helper function."""
    
    def test_valid_current_year(self):
        current_year = datetime.now().year
        year, flags = validate_year(current_year)
        assert year == current_year
        assert flags == []
    
    def test_valid_historical_year(self):
        year, flags = validate_year(2017)
        assert year == 2017
        assert flags == []
    
    def test_valid_oldest_year(self):
        year, flags = validate_year(1800)
        assert year == 1800
        assert flags == []
    
    def test_future_year_invalid(self):
        future_year = datetime.now().year + 5
        year, flags = validate_year(future_year)
        assert year is None
        assert "bad_year" in flags
    
    def test_ancient_year_invalid(self):
        year, flags = validate_year(1750)
        assert year is None
        assert "bad_year" in flags
    
    def test_none_year(self):
        year, flags = validate_year(None)
        assert year is None
        assert flags == []


class TestOpenAlexAdapter:
    """Tests for OpenAlex adapter parsing."""
    
    def test_parses_correct_year(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.year == 2017
        assert "bad_year" not in result.data_quality_flags
    
    def test_parses_correct_doi(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        # DOI should have https://doi.org/ prefix removed
        assert result.doi == "10.5555/3295222.3295349"
    
    def test_parses_correct_title(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.title == "Attention Is All You Need"
    
    def test_parses_authors(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert len(result.authors) == 2
        assert result.authors[0].name == "Ashish Vaswani"
        assert "Google Brain" in result.authors[0].affiliations
    
    def test_parses_citation_count(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.citation_count == 50000
    
    def test_parses_oa_url(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.oa_url == "https://arxiv.org/pdf/1706.03762.pdf"
        assert result.is_open_access is True
    
    def test_future_year_flagged(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FUTURE_YEAR_FIXTURE)
        
        assert result.year is None
        assert "bad_year" in result.data_quality_flags


class TestSemanticScholarAdapter:
    """Tests for Semantic Scholar adapter parsing."""
    
    def test_parses_correct_year(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.year == 2017
        assert "bad_year" not in result.data_quality_flags
    
    def test_parses_correct_doi(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.doi == "10.5555/3295222.3295349"
    
    def test_parses_correct_title(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.title == "Attention Is All You Need"
    
    def test_parses_source_id(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.source_id == "204e3073870fae3d05bcbc2f6a8e263d9b72e776"
    
    def test_parses_citation_count(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.citation_count == 51000
    
    def test_bad_year_flagged(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_BAD_YEAR_FIXTURE)
        
        assert result.year is None
        assert "bad_year" in result.data_quality_flags


class TestCrossrefAdapter:
    """Tests for Crossref adapter parsing."""
    
    def test_parses_correct_year_from_published_print(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        # Should prefer published-print over published-online and issued
        assert result.year == 2017
        assert "bad_year" not in result.data_quality_flags
    
    def test_parses_correct_doi(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        assert result.doi == "10.5555/3295222.3295349"
    
    def test_parses_correct_title(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        assert result.title == "Attention Is All You Need"
    
    def test_parses_authors(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        assert len(result.authors) == 2
        assert result.authors[0].name == "Ashish Vaswani"
    
    def test_parses_citation_count(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        assert result.citation_count == 49000
    
    def test_parses_year_from_issued_when_no_published(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_ONLY_ISSUED_FIXTURE)
        
        assert result.year == 2020
    
    def test_parses_year_from_published_online_when_no_print(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_ONLY_PUBLISHED_ONLINE_FIXTURE)
        
        assert result.year == 2021


class TestLinkCorrectness:
    """Tests for link/URL correctness."""
    
    def test_openalex_doi_url_format(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        # DOI should be clean (no URL prefix)
        assert result.doi.startswith("10.")
        assert not result.doi.startswith("http")
    
    def test_semantic_scholar_doi_url_format(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.doi.startswith("10.")
        assert not result.doi.startswith("http")
    
    def test_oa_url_is_valid_url(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.oa_url is not None
        assert result.oa_url.startswith("http")


class TestSourceIdentifiers:
    """Tests for source-specific identifier preservation."""
    
    def test_openalex_preserves_source_id(self):
        adapter = OpenAlexAdapter()
        result = adapter._parse_work(OPENALEX_FIXTURE)
        
        assert result.source_id == "W2741809807"
        assert result.source == "openalex"
    
    def test_semantic_scholar_preserves_source_id(self):
        adapter = SemanticScholarAdapter()
        result = adapter._parse_paper(SEMANTIC_SCHOLAR_FIXTURE)
        
        assert result.source_id == "204e3073870fae3d05bcbc2f6a8e263d9b72e776"
        assert result.source == "semantic_scholar"
    
    def test_crossref_source_id_is_doi(self):
        adapter = CrossrefAdapter()
        result = adapter._parse_work(CROSSREF_FIXTURE)
        
        # Crossref uses DOI as source ID
        assert result.source_id == result.doi
        assert result.source == "crossref"

