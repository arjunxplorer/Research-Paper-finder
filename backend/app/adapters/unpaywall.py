"""Unpaywall API adapter for finding open access links."""

from typing import Optional
import httpx

from app.adapters.base import BaseAdapter, PaperResult
from app.config import get_settings


class UnpaywallAdapter(BaseAdapter):
    """Adapter for Unpaywall API to find open access versions of papers."""
    
    source_name = "unpaywall"
    base_url = "https://api.unpaywall.org/v2"
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.email = settings.unpaywall_email
    
    async def get_oa_url(self, doi: str) -> Optional[str]:
        """Get the best open access URL for a DOI.
        
        Args:
            doi: The DOI to look up (without https://doi.org/ prefix)
            
        Returns:
            The best OA URL if available, None otherwise
        """
        # Clean DOI
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        
        url = f"{self.base_url}/{doi}"
        
        params = {"email": self.email}
        
        try:
            response = await self._make_request("GET", url, params=params)
            data = response.json()
            
            # Check if open access
            if not data.get("is_oa"):
                return None
            
            # Get best OA location
            best_location = data.get("best_oa_location")
            if best_location:
                # Prefer PDF URL over landing page
                if best_location.get("url_for_pdf"):
                    return best_location["url_for_pdf"]
                elif best_location.get("url"):
                    return best_location["url"]
                elif best_location.get("url_for_landing_page"):
                    return best_location["url_for_landing_page"]
            
            # Try other OA locations
            for location in data.get("oa_locations", []):
                if location.get("url_for_pdf"):
                    return location["url_for_pdf"]
                elif location.get("url"):
                    return location["url"]
            
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 422):
                # DOI not found or invalid
                return None
            # Don't raise on rate limit, just return None
            if e.response.status_code == 429:
                return None
            raise
    
    async def get_oa_urls_batch(self, dois: list[str]) -> dict[str, Optional[str]]:
        """Get OA URLs for multiple DOIs.
        
        Note: Unpaywall doesn't have a batch API, so this makes sequential requests.
        Consider adding rate limiting for large batches.
        
        Args:
            dois: List of DOIs to look up
            
        Returns:
            Dictionary mapping DOI to OA URL (or None if not available)
        """
        results = {}
        
        for doi in dois:
            results[doi] = await self.get_oa_url(doi)
        
        return results
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Unpaywall doesn't support search - this is a no-op."""
        # Unpaywall is only for DOI lookups, not search
        return []
    
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Unpaywall only provides OA links, not full paper metadata."""
        return None

