"""Base adapter interface and common utilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@dataclass
class Author:
    """Normalized author representation."""
    name: str
    affiliations: list[str] = field(default_factory=list)


@dataclass
class PaperResult:
    """Normalized paper result from any source."""
    
    # Required fields
    title: str
    source: str  # Which adapter produced this result
    
    # Identifiers
    doi: Optional[str] = None
    source_id: Optional[str] = None  # ID in the source system
    arxiv_id: Optional[str] = None  # arXiv ID (e.g., "1706.03762")
    pmid: Optional[str] = None  # PubMed ID
    
    # Metadata
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: list[Author] = field(default_factory=list)
    
    # Citations
    citation_count: Optional[int] = None
    
    # URLs
    oa_url: Optional[str] = None
    publisher_url: Optional[str] = None
    
    # Topics/Fields
    topics: list[str] = field(default_factory=list)
    
    # Flags
    is_survey: bool = False
    is_open_access: bool = False
    
    # Work type classification
    work_type: Optional[str] = None  # survey, book, chapter, preprint, journal, conference, unknown
    
    # Relevance score from source (if available)
    relevance_score: Optional[float] = None
    
    # Data quality tracking
    data_quality_flags: list[str] = field(default_factory=list)


def validate_year(year: Optional[int]) -> tuple[Optional[int], list[str]]:
    """Validate year and return (validated_year, quality_flags).
    
    Returns None for invalid years (future or before 1800) and adds 'bad_year' flag.
    """
    if year is None:
        return None, []
    
    current_year = datetime.now().year
    flags = []
    
    if year > current_year or year < 1800:
        flags.append("bad_year")
        return None, flags
    
    return year, []


class BaseAdapter(ABC):
    """Abstract base class for source adapters."""
    
    source_name: str = "unknown"
    base_url: str = ""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        client = await self.get_client()
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    
    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Search for papers matching the query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            year_min: Minimum publication year (optional)
            year_max: Maximum publication year (optional)
            
        Returns:
            List of normalized PaperResult objects
        """
        pass
    
    @abstractmethod
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Get a specific paper by its source-specific ID.
        
        Args:
            paper_id: The paper ID in this source's format
            
        Returns:
            PaperResult if found, None otherwise
        """
        pass

