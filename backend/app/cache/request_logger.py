"""Request logging for analytics."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog


# In-memory log for MVP (when database isn't available)
_request_logs: list[dict] = []


async def log_request(
    query: str,
    mode: str,
    filters: dict,
    latency_ms: int,
    source_stats: dict[str, int],
    db: Optional[AsyncSession] = None,
) -> None:
    """Log a search request for analytics.
    
    Args:
        query: Search query
        mode: Ranking mode
        filters: Search filters applied
        latency_ms: Request latency in milliseconds
        source_stats: Papers fetched per source
        db: Optional database session
    """
    log_entry = {
        "id": str(uuid.uuid4()),
        "query_text": query,
        "mode": mode,
        "filters_json": filters,
        "latency_ms": latency_ms,
        "source_stats_json": source_stats,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    if db:
        # Persist to database
        try:
            db_log = RequestLog(
                query_text=query,
                mode=mode,
                filters_json=filters,
                latency_ms=latency_ms,
                source_stats_json=source_stats,
            )
            db.add(db_log)
            await db.commit()
        except Exception:
            # Log to memory if db fails
            _request_logs.append(log_entry)
    else:
        # Memory-only logging
        _request_logs.append(log_entry)
        
        # Keep only last 1000 logs
        if len(_request_logs) > 1000:
            _request_logs.pop(0)


def get_recent_logs(limit: int = 100) -> list[dict]:
    """Get recent request logs from memory."""
    return _request_logs[-limit:]


def get_log_stats() -> dict[str, Any]:
    """Get aggregate statistics from logs."""
    if not _request_logs:
        return {
            "total_requests": 0,
            "avg_latency_ms": 0,
            "mode_distribution": {},
            "top_queries": [],
        }
    
    total = len(_request_logs)
    avg_latency = sum(log["latency_ms"] for log in _request_logs) / total
    
    # Mode distribution
    mode_counts: dict[str, int] = {}
    for log in _request_logs:
        mode = log["mode"]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    
    # Top queries
    query_counts: dict[str, int] = {}
    for log in _request_logs:
        query = log["query_text"].lower()
        query_counts[query] = query_counts.get(query, 0) + 1
    
    top_queries = sorted(
        query_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    
    return {
        "total_requests": total,
        "avg_latency_ms": round(avg_latency, 2),
        "mode_distribution": mode_counts,
        "top_queries": [{"query": q, "count": c} for q, c in top_queries],
    }

