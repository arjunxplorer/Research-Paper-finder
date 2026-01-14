"""Crossref API adapter for DOI resolution and metadata."""

from typing import Optional
import httpx

from app.adapters.base import BaseAdapter, PaperResult, Author, validate_year


class CrossrefAdapter(BaseAdapter):
    """Adapter for Crossref API."""
    
    source_name = "crossref"
    base_url = "https://api.crossref.org"
    
    def __init__(self, email: str = "user@example.com"):
        super().__init__()
        self.email = email  # Polite pool access
    
    def _get_headers(self) -> dict:
        """Get request headers."""
        return {
            "Accept": "application/json",
            "User-Agent": f"BestPapersFinder/1.0 (mailto:{self.email})",
        }
    
    def _parse_work(self, data: dict) -> PaperResult:
        """Parse Crossref work data into PaperResult."""
        # Extract DOI
        doi = data.get("DOI")
        
        # Extract title
        titles = data.get("title", [])
        title = titles[0] if titles else ""
        
        # Extract authors
        authors = []
        for author_data in data.get("author", []) or []:
            name_parts = []
            if author_data.get("given"):
                name_parts.append(author_data["given"])
            if author_data.get("family"):
                name_parts.append(author_data["family"])
            if name_parts:
                affiliations = []
                for aff in author_data.get("affiliation", []) or []:
                    if aff.get("name"):
                        affiliations.append(aff["name"])
                authors.append(Author(
                    name=" ".join(name_parts),
                    affiliations=affiliations,
                ))
        
        # Extract year - check published-print, published-online, issued, published in priority order
        year = None
        for date_field in ["published-print", "published-online", "issued", "published"]:
            date_info = data.get(date_field)
            if date_info:
                date_parts = date_info.get("date-parts", [[]])
                if date_parts and date_parts[0] and date_parts[0][0]:
                    year = date_parts[0][0]
                    break
        
        # Validate year
        validated_year, year_flags = validate_year(year)
        
        # Extract venue
        venue = None
        container_titles = data.get("container-title", [])
        if container_titles:
            venue = container_titles[0]
        
        # Check if review
        work_type = data.get("type", "")
        is_survey = work_type in ["review", "book-review"]
        
        # Get abstract
        abstract = data.get("abstract")
        if abstract:
            # Remove JATS tags if present
            abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "")
            abstract = abstract.replace("<jats:italic>", "").replace("</jats:italic>", "")
        
        # Get URL
        publisher_url = data.get("URL") or data.get("resource", {}).get("primary", {}).get("URL")
        
        return PaperResult(
            title=title,
            source=self.source_name,
            doi=doi,
            source_id=doi,
            abstract=abstract,
            year=validated_year,
            venue=venue,
            authors=authors,
            citation_count=data.get("is-referenced-by-count"),
            publisher_url=publisher_url,
            is_survey=is_survey,
            data_quality_flags=year_flags,
        )
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Search Crossref for works."""
        url = f"{self.base_url}/works"
        
        params = {
            "query": query,
            "rows": min(limit, 100),
            "select": "DOI,title,author,published,container-title,type,abstract,is-referenced-by-count,URL,resource",
        }
        
        # Add filters
        filters = []
        if year_min:
            filters.append(f"from-pub-date:{year_min}")
        if year_max:
            filters.append(f"until-pub-date:{year_max}")
        
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
            message = data.get("message", {})
            for item in message.get("items", []):
                titles = item.get("title", [])
                if titles:  # Skip items without titles
                    papers.append(self._parse_work(item))
            
            return papers
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return []
            raise
    
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Get a work by DOI."""
        # Clean DOI
        doi = paper_id.replace("https://doi.org/", "").replace("http://doi.org/", "")
        
        url = f"{self.base_url}/works/{doi}"
        
        try:
            response = await self._make_request(
                "GET",
                url,
                headers=self._get_headers(),
            )
            data = response.json()
            
            message = data.get("message", {})
            if message.get("title"):
                return self._parse_work(message)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

