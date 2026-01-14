"""Search API endpoint."""

import asyncio
import time
from datetime import datetime, date
from typing import Literal, Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.semantic_scholar import SemanticScholarAdapter
from app.adapters.openalex import OpenAlexAdapter
from app.adapters.pubmed import PubMedAdapter
from app.adapters.arxiv import ArxivAdapter
from app.adapters.base import PaperResult
from app.dedup.merge import merge_papers, MergedPaper
from app.dedup.enrich import enrich_papers
from app.ranking.scoring import rank_papers
from app.ranking.explain import add_explanations
from app.cache.search_cache import get_cached_results, cache_results
from app.config import get_settings


router = APIRouter()

# Maximum number of papers to cache per query (full candidate set)
MAX_CACHED_RESULTS = 100


class AuthorResponse(BaseModel):
    """Author in API response."""
    name: str
    affiliations: list[str] = []


class PublicationResponse(BaseModel):
    """Publication in API response."""
    id: Optional[str] = None
    title: Optional[str] = None
    isbn: Optional[str] = None
    issn: Optional[str] = None
    publisher: Optional[str] = None
    category: Optional[str] = None
    citeScore: Optional[float] = None
    sjr: Optional[float] = None
    snip: Optional[float] = None
    subjectAreas: list[str] = []
    isPotentiallyPredatory: bool = False


class PaperResponse(BaseModel):
    """Paper in search results."""
    id: str
    doi: Optional[str]
    title: str
    abstract: Optional[str]
    year: Optional[int]
    publicationDate: Optional[str] = None  # ISO format date string
    venue: Optional[str]
    authors: list[AuthorResponse]
    citationCount: Optional[int]
    citationSource: Optional[str]
    oaUrl: Optional[str]
    publisherUrl: Optional[str]
    doiUrl: Optional[str]
    urls: list[str] = []  # Set of URLs from different databases
    topics: list[str]
    keywords: list[str] = []  # Author-provided keywords
    comments: Optional[str] = None
    numberOfPages: Optional[int] = None
    pages: Optional[str] = None
    selected: bool = False
    categories: dict[str, list[str]] = {}  # Facet -> categories
    databases: list[str] = []  # Database names where paper was found
    score: float
    whyRecommended: list[str]
    sourceIds: dict[str, str]  # Map of source name -> source ID (e.g., {"semantic_scholar": "123", "openalex": "W456"})
    publication: Optional[PublicationResponse] = None
    citationKey: Optional[str] = None


class SearchResponse(BaseModel):
    """Response from search endpoint."""
    results: list[PaperResponse]
    query: str
    mode: str
    sortBy: str
    limit: int
    totalCandidates: int
    sourceStats: dict[str, int]


class CachedSearchData(BaseModel):
    """Cached search data - full candidate set before limit/sort applied."""
    papers: list[PaperResponse]  # Full ranked list (up to MAX_CACHED_RESULTS)
    query: str
    mode: str
    totalCandidates: int
    sourceStats: dict[str, int]


def apply_sort_and_limit(
    papers: list[PaperResponse],
    sort_by: str,
    limit: int,
) -> list[PaperResponse]:
    """Apply user-selected sort order and limit to cached results."""
    if sort_by == "citations":
        # Sort by citation count (highest first), then by score
        sorted_papers = sorted(
            papers,
            key=lambda p: (p.citationCount or 0, p.score),
            reverse=True
        )
    elif sort_by == "year":
        # Sort by year (newest first), then by score
        sorted_papers = sorted(
            papers,
            key=lambda p: (p.year or 0, p.score),
            reverse=True
        )
    else:
        # sort_by == "relevance" - keep original score-based order
        sorted_papers = papers
    
    return sorted_papers[:limit]


def merged_to_response(paper: MergedPaper) -> PaperResponse:
    """Convert MergedPaper to API response."""
    return PaperResponse(
        id=paper.id,
        doi=paper.doi,
        title=paper.title,
        abstract=paper.abstract,
        year=paper.year,
        publicationDate=paper.publication_date.isoformat() if paper.publication_date else None,
        venue=paper.venue,
        authors=[
            AuthorResponse(name=a.name, affiliations=a.affiliations)
            for a in paper.authors
        ],
        citationCount=paper.citation_count,
        citationSource=paper.citation_source,
        oaUrl=paper.oa_url,
        publisherUrl=paper.publisher_url,
        doiUrl=paper.doi_url,
        urls=list(paper.urls),
        topics=paper.topics,
        keywords=list(paper.keywords),
        comments=paper.comments,
        numberOfPages=paper.number_of_pages,
        pages=paper.pages,
        selected=paper.selected,
        categories=paper.categories,
        databases=list(paper.databases),
        score=paper.score,
        whyRecommended=paper.why_recommended,
        sourceIds=paper.source_ids,  # Include source IDs for related papers lookup
        citationKey=paper.get_citation_key(),
    )


async def fetch_from_source(
    adapter,
    query: str,
    limit: int,
    year_min: Optional[int],
    year_max: Optional[int],
) -> tuple[str, list[PaperResult]]:
    """Fetch papers from a single source with error handling."""
    try:
        results = await adapter.search(
            query=query,
            limit=limit,
            year_min=year_min,
            year_max=year_max,
        )
        return adapter.source_name, results
    except Exception as e:
        # Log error but don't fail
        print(f"Error fetching from {adapter.source_name}: {e}")
        return adapter.source_name, []
    finally:
        await adapter.close()


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    mode: Literal["foundational", "recent"] = Query(..., description="Ranking mode"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    sort_by: Literal["relevance", "citations", "year"] = Query("relevance", description="Sort order: relevance (default), citations (highest first), year (newest first)"),
    year_min: Optional[int] = Query(None, ge=1800, le=2100, description="Minimum year (deprecated, use since)"),
    year_max: Optional[int] = Query(None, ge=1800, le=2100, description="Maximum year (deprecated, use until)"),
    since: Optional[str] = Query(None, description="Start date (YYYY-MM-DD format)"),
    until: Optional[str] = Query(None, description="End date (YYYY-MM-DD format)"),
    limit_per_database: Optional[int] = Query(None, ge=1, le=200, description="Maximum results per database"),
    publication_types: Optional[str] = Query(None, description="Comma-separated publication types: Journal,Conference Proceedings,Book"),
    oa_only: bool = Query(False, description="Open access only"),
    survey_only: bool = Query(False, description="Survey/review papers only"),
    include_pubmed: bool = Query(True, description="Include PubMed results"),
    include_arxiv: bool = Query(True, description="Include arXiv results"),
    bypass_cache: bool = Query(False, description="Bypass cache for debugging"),
):
    """Search for top research papers.
    
    Returns papers ranked according to the specified mode and sort order:
    - mode: foundational (classic, highly-cited) or recent (high citation velocity)
    - sort_by: relevance (default ranking), citations (highest first), year (newest first)
    - limit: number of results (1-100, default 20)
    """
    settings = get_settings()
    start_time = time.time()
    
    # Parse date parameters
    since_date = None
    until_date = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' date format. Use YYYY-MM-DD")
    elif year_min:
        # Convert year_min to date for backward compatibility
        since_date = date(year_min, 1, 1)
    
    if until:
        try:
            until_date = datetime.strptime(until, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'until' date format. Use YYYY-MM-DD")
    elif year_max:
        # Convert year_max to date for backward compatibility
        until_date = date(year_max, 12, 31)
    
    # Parse publication types
    pub_types_list = None
    if publication_types:
        pub_types_list = [t.strip() for t in publication_types.split(",")]
        # Validate publication types
        valid_types = {"Journal", "Conference Proceedings", "Book"}
        for pt in pub_types_list:
            if pt not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid publication type '{pt}'. Valid types: {', '.join(valid_types)}"
                )
    
    # Build cache key
    # NOTE: limit and sort_by are NOT included in the cache key!
    # We cache the full ranked candidate set and slice/re-sort at the end.
    # This ensures consistent results regardless of limit selected.
    cache_key = {
        "query": q.lower().strip(),
        "mode": mode,
        "year_min": year_min,
        "year_max": year_max,
        "since": since_date.isoformat() if since_date else None,
        "until": until_date.isoformat() if until_date else None,
        "limit_per_database": limit_per_database,
        "publication_types": pub_types_list,
        "oa_only": oa_only,
        "survey_only": survey_only,
        "include_pubmed": include_pubmed,
        "include_arxiv": include_arxiv,
    }
    
    # Check cache (unless bypassed)
    # Cache stores full candidate set; we apply sort_by and limit here
    if not bypass_cache:
        cached: Optional[CachedSearchData] = await get_cached_results(cache_key)
        if cached:
            # Apply user's sort order and limit to cached full results
            sorted_results = apply_sort_and_limit(cached.papers, sort_by, limit)
            return SearchResponse(
                results=sorted_results,
                query=cached.query,
                mode=cached.mode,
                sortBy=sort_by,
                limit=limit,
                totalCandidates=cached.totalCandidates,
                sourceStats=cached.sourceStats,
            )
    
    # Build list of adapters to use
    adapters = [
        SemanticScholarAdapter(),
        OpenAlexAdapter(),
    ]
    
    if include_pubmed:
        adapters.append(PubMedAdapter())
    
    if include_arxiv:
        adapters.append(ArxivAdapter())
    
    # Fetch from all sources in parallel
    limit_per_source = limit_per_database if limit_per_database else settings.default_candidates_per_source
    
    # Convert dates to years for adapters (backward compatibility)
    adapter_year_min = year_min
    adapter_year_max = year_max
    if since_date and not year_min:
        adapter_year_min = since_date.year
    if until_date and not year_max:
        adapter_year_max = until_date.year
    
    tasks = [
        fetch_from_source(adapter, q, limit_per_source, adapter_year_min, adapter_year_max)
        for adapter in adapters
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Collect all papers and stats
    all_papers: list[PaperResult] = []
    source_stats: dict[str, int] = {}
    
    for source_name, papers in results:
        source_stats[source_name] = len(papers)
        all_papers.extend(papers)
    
    total_candidates = len(all_papers)
    
    if not all_papers:
        return SearchResponse(
            results=[],
            query=q,
            mode=mode,
            sortBy=sort_by,
            limit=limit,
            totalCandidates=0,
            sourceStats=source_stats,
        )
    
    # Deduplicate and merge
    merged_papers = merge_papers(all_papers)
    
    # Apply date filters (since/until)
    if since_date or until_date:
        filtered_papers = []
        for p in merged_papers:
            # Check publication_date first, fall back to year
            paper_date = p.publication_date
            if not paper_date and p.year:
                try:
                    paper_date = date(p.year, 1, 1)
                except ValueError:
                    pass
            
            if paper_date:
                if since_date and paper_date < since_date:
                    continue
                if until_date and paper_date > until_date:
                    continue
            elif since_date or until_date:
                # If we have date filters but no paper date, exclude it
                continue
            
            filtered_papers.append(p)
        merged_papers = filtered_papers
    
    # Apply filters
    if oa_only:
        merged_papers = [p for p in merged_papers if p.is_open_access or p.oa_url]
    
    if survey_only:
        merged_papers = [p for p in merged_papers if p.is_survey]
    
    # Apply publication types filter
    if pub_types_list:
        # TODO: Filter by publication type once Publication model is integrated
        # For now, filter by work_type which is a proxy
        type_mapping = {
            "Journal": "journal",
            "Conference Proceedings": "conference",
            "Book": "book",
        }
        work_types = [type_mapping.get(pt, pt.lower()) for pt in pub_types_list]
        merged_papers = [p for p in merged_papers if p.work_type in work_types]
    
    # Enrich with OA links
    merged_papers = await enrich_papers(merged_papers, fetch_oa_links=True)
    
    # Rank papers (pass survey_only to skip survey cap when filtering for surveys)
    # Always rank up to MAX_CACHED_RESULTS for consistent caching
    # Pass query for query-aware ranking
    ranked_papers = rank_papers(
        merged_papers,
        mode=mode,
        limit=MAX_CACHED_RESULTS,
        survey_only=survey_only,
        query=q,
    )
    
    # Add explanations to full candidate set (before caching)
    ranked_papers = add_explanations(ranked_papers, mode)
    
    # Convert full set to response format for caching
    all_paper_responses = [merged_to_response(p) for p in ranked_papers]
    
    # Cache the full candidate set (sort_by and limit applied at retrieval)
    cached_data = CachedSearchData(
        papers=all_paper_responses,
        query=q,
        mode=mode,
        totalCandidates=total_candidates,
        sourceStats=source_stats,
    )
    await cache_results(cache_key, cached_data)
    
    # Apply user's sort order and limit for this request
    sorted_results = apply_sort_and_limit(all_paper_responses, sort_by, limit)
    
    # Build final response
    response = SearchResponse(
        results=sorted_results,
        query=q,
        mode=mode,
        sortBy=sort_by,
        limit=limit,
        totalCandidates=total_candidates,
        sourceStats=source_stats,
    )
    
    # Log request
    latency_ms = int((time.time() - start_time) * 1000)
    print(f"Search completed in {latency_ms}ms: {q} ({mode})")
    
    return response

