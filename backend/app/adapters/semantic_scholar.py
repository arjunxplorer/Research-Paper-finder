"""Semantic Scholar API adapter."""

from typing import Optional
import httpx

from app.adapters.base import BaseAdapter, PaperResult, Author, validate_year
from app.config import get_settings


class SemanticScholarAdapter(BaseAdapter):
    """Adapter for Semantic Scholar Academic Graph API."""
    
    source_name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1"
    
    # Fields to request from API
    PAPER_FIELDS = [
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "authors",
        "citationCount",
        "isOpenAccess",
        "openAccessPdf",
        "externalIds",
        "publicationTypes",
        "s2FieldsOfStudy",
    ]
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.semantic_scholar_api_key
    
    def _get_headers(self) -> dict:
        """Get request headers including API key if available."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers
    
    def _parse_paper(self, data: dict) -> PaperResult:
        """Parse Semantic Scholar paper data into PaperResult."""
        # Extract external IDs
        external_ids = data.get("externalIds", {}) or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        pmid = external_ids.get("PubMed")
        
        # Extract authors
        authors = []
        for author_data in data.get("authors", []) or []:
            if author_data.get("name"):
                authors.append(Author(name=author_data["name"]))
        
        # Extract topics/fields
        topics = []
        for field in data.get("s2FieldsOfStudy", []) or []:
            if field.get("category"):
                topics.append(field["category"])
        
        # Check if survey/review
        pub_types = data.get("publicationTypes", []) or []
        is_survey = "Review" in pub_types or "Survey" in pub_types
        
        # Validate year
        raw_year = data.get("year")
        validated_year, year_flags = validate_year(raw_year)
        
        # Get OA URL
        oa_pdf = data.get("openAccessPdf")
        oa_url = oa_pdf.get("url") if oa_pdf else None
        
        return PaperResult(
            title=data.get("title", ""),
            source=self.source_name,
            doi=doi,
            source_id=data.get("paperId"),
            arxiv_id=arxiv_id,
            pmid=pmid,
            abstract=data.get("abstract"),
            year=validated_year,
            venue=data.get("venue"),
            authors=authors,
            citation_count=data.get("citationCount"),
            oa_url=oa_url,
            topics=topics,
            is_survey=is_survey,
            is_open_access=data.get("isOpenAccess", False),
            data_quality_flags=year_flags,
        )
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Search Semantic Scholar for papers."""
        url = f"{self.base_url}/paper/search"
        
        params = {
            "query": query,
            "limit": min(limit, 100),  # API max is 100
            "fields": ",".join(self.PAPER_FIELDS),
        }
        
        # Add year filter if specified
        if year_min or year_max:
            year_filter = ""
            if year_min:
                year_filter = f"{year_min}-"
            if year_max:
                year_filter += str(year_max)
            elif year_min:
                year_filter += ""  # Open-ended
            params["year"] = year_filter
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()
            
            papers = []
            data_list = data.get("data", [])
            total = len(data_list)
            for idx, paper_data in enumerate(data_list):
                if paper_data.get("title"):  # Skip papers without titles
                    paper = self._parse_paper(paper_data)
                    # Assign position-based relevance score (1.0 for first, declining)
                    # This captures the API's relevance ranking
                    paper.relevance_score = 1.0 - (idx / max(total, 1)) * 0.5
                    papers.append(paper)
            
            return papers
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - return empty
                return []
            raise
    
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Get a specific paper by Semantic Scholar ID."""
        url = f"{self.base_url}/paper/{paper_id}"
        
        params = {"fields": ",".join(self.PAPER_FIELDS)}
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()
            
            if data.get("title"):
                return self._parse_paper(data)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_citations(self, paper_id: str, limit: int = 50) -> list[PaperResult]:
        """Get papers that cite this paper."""
        url = f"{self.base_url}/paper/{paper_id}/citations"
        
        params = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 100),
        }
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()
            
            papers = []
            for item in data.get("data", []):
                citing_paper = item.get("citingPaper", {})
                if citing_paper.get("title"):
                    papers.append(self._parse_paper(citing_paper))
            
            return papers
            
        except httpx.HTTPStatusError:
            return []
    
    async def get_references(self, paper_id: str, limit: int = 50) -> list[PaperResult]:
        """Get papers referenced by this paper."""
        url = f"{self.base_url}/paper/{paper_id}/references"
        
        params = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 100),
        }
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()
            
            papers = []
            for item in data.get("data", []):
                cited_paper = item.get("citedPaper", {})
                if cited_paper.get("title"):
                    papers.append(self._parse_paper(cited_paper))
            
            return papers
            
        except httpx.HTTPStatusError:
            return []

