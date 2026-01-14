"""Search result caching layer."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Optional

from app.config import get_settings

# Cache version - increment when canonicalization/ranking logic changes
# This ensures stale results are invalidated when logic is updated
CACHE_VERSION = "v5"  # v5: cache full candidate set, apply limit/sort at retrieval

# In-memory cache for MVP (would use Redis in production)
_cache: dict[str, tuple[Any, datetime]] = {}


def _make_cache_key(params: dict) -> str:
    """Generate a versioned cache key from search parameters.
    
    Format: search:{version}:{hash(params)}
    """
    # Sort keys for consistent hashing
    sorted_params = json.dumps(params, sort_keys=True)
    param_hash = hashlib.sha256(sorted_params.encode()).hexdigest()[:24]
    return f"search:{CACHE_VERSION}:{param_hash}"


async def get_cached_results(params: dict) -> Optional[Any]:
    """Get cached search results if available and not expired.
    
    Args:
        params: Search parameters dict
        
    Returns:
        Cached response or None if not found/expired
    """
    key = _make_cache_key(params)
    
    if key not in _cache:
        return None
    
    result, expires_at = _cache[key]
    
    # Check expiration
    if datetime.utcnow() > expires_at:
        # Expired - remove from cache
        del _cache[key]
        return None
    
    return result


async def cache_results(params: dict, results: Any) -> None:
    """Cache search results.
    
    Args:
        params: Search parameters dict
        results: Results to cache
    """
    settings = get_settings()
    key = _make_cache_key(params)
    
    ttl_hours = settings.search_cache_ttl_hours
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    
    _cache[key] = (results, expires_at)


async def invalidate_cache(params: Optional[dict] = None) -> None:
    """Invalidate cached results.
    
    Args:
        params: If provided, invalidate specific cache entry.
                If None, invalidate all entries.
    """
    global _cache
    
    if params is None:
        _cache = {}
    else:
        key = _make_cache_key(params)
        if key in _cache:
            del _cache[key]


async def cleanup_expired() -> int:
    """Remove expired entries from cache.
    
    Returns:
        Number of entries removed
    """
    global _cache
    now = datetime.utcnow()
    
    expired_keys = [
        key for key, (_, expires_at) in _cache.items()
        if now > expires_at
    ]
    
    for key in expired_keys:
        del _cache[key]
    
    return len(expired_keys)


def get_cache_stats() -> dict:
    """Get cache statistics."""
    now = datetime.utcnow()
    
    total = len(_cache)
    expired = sum(1 for _, expires_at in _cache.values() if now > expires_at)
    
    return {
        "total_entries": total,
        "expired_entries": expired,
        "active_entries": total - expired,
    }

