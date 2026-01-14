"""OpenAlex API adapter."""

import re
from typing import Optional
import httpx

from app.adapters.base import BaseAdapter, PaperResult, Author, validate_year


class OpenAlexAdapter(BaseAdapter):
    """Adapter for OpenAlex API."""
    
    source_name = "openalex"
    base_url = "https://api.openalex.org"
    
    def __init__(self, email: str = "user@example.com"):
        super().__init__()
        self.email = email  # Polite pool access
    
    def _get_headers(self) -> dict:
        """Get request headers with polite email."""
        return {
            "Accept": "application/json",
            "User-Agent": f"BestPapersFinder/1.0 (mailto:{self.email})",
        }
    
    def _parse_work(self, data: dict) -> PaperResult:
        """Parse OpenAlex work data into PaperResult."""
        # Extract DOI (remove https://doi.org/ prefix)
        doi = data.get("doi", "")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[16:]  # Remove prefix
        elif not doi:
            doi = None
        
        # Extract arXiv ID from DOI if it's an arXiv DOI
        # Format: 10.48550/arXiv.1706.03762 -> 1706.03762
        arxiv_id = None
        pmid = None
        if doi and "arxiv" in doi.lower():
            # Handle format like 10.48550/arXiv.1706.03762
            match = re.search(r'arxiv\.(\d+\.\d+)', doi.lower())
            if match:
                arxiv_id = match.group(1)
        
        # Also check external IDs from OpenAlex
        ids = data.get("ids", {}) or {}
        if not arxiv_id and ids.get("arxiv"):
            arxiv_id = ids.get("arxiv")
        if ids.get("pmid"):
            pmid = ids.get("pmid")
        
        # Extract OpenAlex ID (remove URL prefix)
        openalex_id = data.get("id", "")
        if openalex_id.startswith("https://openalex.org/"):
            openalex_id = openalex_id[21:]  # Remove prefix
        
        # Extract authors
        authors = []
        for authorship in data.get("authorships", []) or []:
            author_data = authorship.get("author", {})
            if author_data.get("display_name"):
                affiliations = []
                for inst in authorship.get("institutions", []) or []:
                    if inst.get("display_name"):
                        affiliations.append(inst["display_name"])
                authors.append(Author(
                    name=author_data["display_name"],
                    affiliations=affiliations,
                ))
        
        # Extract topics/concepts
        topics = []
        for concept in data.get("concepts", []) or []:
            if concept.get("display_name") and concept.get("score", 0) > 0.3:
                topics.append(concept["display_name"])
        
        # Get venue
        venue = None
        primary_location = data.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        if source.get("display_name"):
            venue = source["display_name"]
        
        # Validate year
        raw_year = data.get("publication_year")
        validated_year, year_flags = validate_year(raw_year)
        
        # Check if review
        work_type = data.get("type", "")
        is_survey = work_type in ["review", "book-chapter"] or "review" in (data.get("title") or "").lower()
        
        # Get OA URL
        oa_url = None
        open_access = data.get("open_access", {}) or {}
        if open_access.get("is_oa"):
            oa_url = open_access.get("oa_url")
        
        # Get best URL
        publisher_url = None
        best_oa_location = data.get("best_oa_location", {}) or {}
        if best_oa_location.get("pdf_url"):
            publisher_url = best_oa_location["pdf_url"]
        elif best_oa_location.get("landing_page_url"):
            publisher_url = best_oa_location["landing_page_url"]
        
        return PaperResult(
            title=data.get("title") or data.get("display_name", ""),
            source=self.source_name,
            doi=doi,
            source_id=openalex_id,
            arxiv_id=arxiv_id,
            pmid=pmid,
            abstract=self._reconstruct_abstract(data.get("abstract_inverted_index")),
            year=validated_year,
            venue=venue,
            authors=authors,
            citation_count=data.get("cited_by_count"),
            oa_url=oa_url or publisher_url,
            publisher_url=publisher_url,
            topics=topics[:10],  # Limit topics
            is_survey=is_survey,
            is_open_access=open_access.get("is_oa", False),
            data_quality_flags=year_flags,
        )
    
    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> Optional[str]:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return None
        
        # Convert inverted index to word list
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # Sort by position and join
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions)
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Search OpenAlex for works."""
        url = f"{self.base_url}/works"
        
        # Build filter string
        filters = []
        if year_min:
            filters.append(f"from_publication_date:{year_min}-01-01")
        if year_max:
            filters.append(f"to_publication_date:{year_max}-12-31")
        
        params = {
            "search": query,
            "per_page": min(limit, 200),  # API max is 200
            "select": "id,doi,title,display_name,abstract_inverted_index,publication_year,type,authorships,concepts,cited_by_count,open_access,primary_location,best_oa_location",
        }
        
        if filters:
            params["filter"] = ",".join(filters)
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()
            
            papers = []
            results = data.get("results", [])
            total = len(results)
            for idx, work_data in enumerate(results):
                title = work_data.get("title") or work_data.get("display_name")
                if title:  # Skip works without titles
                    paper = self._parse_work(work_data)
                    # Assign position-based relevance score (1.0 for first, declining)
                    paper.relevance_score = 1.0 - (idx / max(total, 1)) * 0.5
                    papers.append(paper)
            
            return papers
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return []
            raise
    
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Get a specific work by OpenAlex ID."""
        # Ensure proper format
        if not paper_id.startswith("W"):
            paper_id = f"W{paper_id}"
        
        url = f"{self.base_url}/works/{paper_id}"
        
        try:
            response = await self._make_request(
                "GET",
                url,
                headers=self._get_headers(),
            )
            data = response.json()
            
            if data.get("title") or data.get("display_name"):
                return self._parse_work(data)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_related_works(self, paper_id: str, limit: int = 50) -> list[PaperResult]:
        """Get related works using OpenAlex's related_works endpoint."""
        if not paper_id.startswith("W"):
            paper_id = f"W{paper_id}"
        
        url = f"{self.base_url}/works"
        
        params = {
            "filter": f"related_to:{paper_id}",
            "per_page": min(limit, 50),
            "select": "id,doi,title,display_name,abstract_inverted_index,publication_year,type,authorships,concepts,cited_by_count,open_access,primary_location,best_oa_location",
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
            for work_data in data.get("results", []):
                if work_data.get("title") or work_data.get("display_name"):
                    papers.append(self._parse_work(work_data))
            
            return papers
            
        except httpx.HTTPStatusError:
            return []

