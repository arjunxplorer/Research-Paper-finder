"""Paper metadata caching layer."""

from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.dedup.merge import MergedPaper

# In-memory cache for MVP
_paper_cache: dict[str, tuple[MergedPaper, datetime]] = {}


async def get_cached_paper(paper_id: str) -> Optional[MergedPaper]:
    """Get cached paper metadata if available.
    
    Args:
        paper_id: Paper ID (UUID or DOI)
        
    Returns:
        Cached paper or None if not found/expired
    """
    if paper_id not in _paper_cache:
        return None
    
    paper, expires_at = _paper_cache[paper_id]
    
    if datetime.utcnow() > expires_at:
        del _paper_cache[paper_id]
        return None
    
    return paper


async def cache_paper(paper: MergedPaper) -> None:
    """Cache paper metadata.
    
    Args:
        paper: Paper to cache
    """
    settings = get_settings()
    expires_at = datetime.utcnow() + timedelta(days=settings.paper_cache_ttl_days)
    
    # Cache by ID
    _paper_cache[paper.id] = (paper, expires_at)
    
    # Also cache by DOI if available
    if paper.doi:
        _paper_cache[paper.doi.lower()] = (paper, expires_at)


async def cache_papers(papers: list[MergedPaper]) -> None:
    """Cache multiple papers."""
    for paper in papers:
        await cache_paper(paper)


async def invalidate_paper(paper_id: str) -> None:
    """Invalidate cached paper."""
    if paper_id in _paper_cache:
        del _paper_cache[paper_id]


async def cleanup_expired() -> int:
    """Remove expired paper cache entries."""
    global _paper_cache
    now = datetime.utcnow()
    
    expired_keys = [
        key for key, (_, expires_at) in _paper_cache.items()
        if now > expires_at
    ]
    
    for key in expired_keys:
        del _paper_cache[key]
    
    return len(expired_keys)

