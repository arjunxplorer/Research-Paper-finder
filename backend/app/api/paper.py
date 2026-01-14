"""Paper API endpoints."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.semantic_scholar import SemanticScholarAdapter
from app.adapters.openalex import OpenAlexAdapter
from app.dedup.merge import merge_papers
from app.dedup.enrich import enrich_papers
from app.ranking.scoring import rank_papers
from app.db.database import get_db


router = APIRouter()


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


class PaperDetailResponse(BaseModel):
    """Detailed paper response."""
    id: str
    doi: Optional[str]
    title: str
    abstract: Optional[str]
    year: Optional[int]
    publicationDate: Optional[str] = None
    venue: Optional[str]
    authors: list[AuthorResponse]
    citationCount: Optional[int]
    citationSource: Optional[str]
    oaUrl: Optional[str]
    publisherUrl: Optional[str]
    doiUrl: Optional[str]
    urls: list[str] = []
    topics: list[str]
    keywords: list[str] = []
    comments: Optional[str] = None
    numberOfPages: Optional[int] = None
    pages: Optional[str] = None
    selected: bool = False
    categories: dict[str, list[str]] = {}
    databases: list[str] = []
    sourceIds: dict[str, str]
    publication: Optional[PublicationResponse] = None
    citationKey: Optional[str] = None
    score: float = 0.0  # Default score for bookmarked/noted papers
    whyRecommended: list[str] = []  # Default empty list


class RelatedPaperResponse(BaseModel):
    """Related paper in response."""
    id: str
    doi: Optional[str]
    title: str
    year: Optional[int]
    venue: Optional[str]
    authors: list[AuthorResponse]
    citationCount: Optional[int]
    oaUrl: Optional[str]
    doiUrl: Optional[str]


@router.get("/paper/{paper_id}", response_model=PaperDetailResponse)
async def get_paper(
    paper_id: str = Path(..., description="Paper ID (UUID or source-specific ID)"),
):
    """Get detailed information about a paper."""
    # Try to fetch from multiple sources
    s2_adapter = SemanticScholarAdapter()
    oa_adapter = OpenAlexAdapter()
    
    try:
        # Try Semantic Scholar first
        paper = await s2_adapter.get_paper(paper_id)
        
        if not paper:
            # Try OpenAlex
            paper = await oa_adapter.get_paper(paper_id)
        
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Merge into unified format
        merged = merge_papers([paper])
        if not merged:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Enrich with OA links
        merged = await enrich_papers(merged, fetch_oa_links=True)
        
        paper_data = merged[0]
        
        return PaperDetailResponse(
            id=paper_data.id,
            doi=paper_data.doi,
            title=paper_data.title,
            abstract=paper_data.abstract,
            year=paper_data.year,
            publicationDate=paper_data.publication_date.isoformat() if paper_data.publication_date else None,
            venue=paper_data.venue,
            authors=[
                AuthorResponse(name=a.name, affiliations=a.affiliations)
                for a in paper_data.authors
            ],
            citationCount=paper_data.citation_count,
            citationSource=paper_data.citation_source,
            oaUrl=paper_data.oa_url,
            publisherUrl=paper_data.publisher_url,
            doiUrl=paper_data.doi_url,
            urls=list(paper_data.urls),
            topics=paper_data.topics,
            keywords=list(paper_data.keywords),
            comments=paper_data.comments,
            numberOfPages=paper_data.number_of_pages,
            pages=paper_data.pages,
            selected=paper_data.selected,
            categories=paper_data.categories,
            databases=list(paper_data.databases),
            sourceIds=paper_data.source_ids,
            citationKey=paper_data.get_citation_key(),
        )
        
    finally:
        await s2_adapter.close()
        await oa_adapter.close()


@router.get("/paper/{paper_id}/related", response_model=list[RelatedPaperResponse])
async def get_related_papers(
    paper_id: str = Path(..., description="Paper ID (UUID, Semantic Scholar ID, or OpenAlex ID)"),
    limit: int = Query(20, ge=1, le=100, description="Number of related papers to return"),
    s2_id: Optional[str] = Query(None, description="Semantic Scholar paper ID (required if paper_id is UUID)"),
    oa_id: Optional[str] = Query(None, description="OpenAlex work ID (required if paper_id is UUID)"),
):
    """Get papers related to a given paper.
    
    Uses citation graph and similarity heuristics to find related work.
    
    The paper_id can be:
    - A UUID from search results (use s2_id/oa_id query params for source IDs)
    - A Semantic Scholar paper ID
    - An OpenAlex work ID (format: W1234567890)
    
    If paper_id is a UUID and source IDs are provided via query params, those will be used.
    """
    s2_adapter = SemanticScholarAdapter()
    oa_adapter = OpenAlexAdapter()
    
    try:
        # Determine which source IDs to use
        # If query params provided, use those (for UUIDs from search results)
        semantic_scholar_id = s2_id
        openalex_id = oa_id
        
        # If paper_id looks like a UUID (36 chars with hyphens), we need source IDs
        is_uuid = len(paper_id) == 36 and paper_id.count('-') == 4
        
        if is_uuid:
            # UUID - need source IDs from query params or lookup
            if not s2_id and not oa_id:
                # Try to fetch paper to get source IDs
                try:
                    paper_detail = await get_paper(paper_id)
                    if paper_detail and paper_detail.sourceIds:
                        semantic_scholar_id = paper_detail.sourceIds.get("semantic_scholar")
                        openalex_id = paper_detail.sourceIds.get("openalex")
                except HTTPException:
                    # Paper not found - can't get related papers
                    return []
        else:
            # Not a UUID - assume it's a source ID
            # Try Semantic Scholar format first, then OpenAlex
            if not semantic_scholar_id:
                semantic_scholar_id = paper_id
            if not openalex_id:
                openalex_id = paper_id
        
        # Fetch related papers from all available sources
        tasks = []
        task_types = []  # Track which task is which
        
        # Semantic Scholar: citations and references
        if semantic_scholar_id:
            tasks.append(s2_adapter.get_citations(semantic_scholar_id, limit=30))
            task_types.append("citations")
            tasks.append(s2_adapter.get_references(semantic_scholar_id, limit=30))
            task_types.append("references")
        
        # OpenAlex: related works
        if openalex_id:
            tasks.append(oa_adapter.get_related_works(openalex_id, limit=30))
            task_types.append("related")
        
        if not tasks:
            return []
        
        # Execute all tasks, catching exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results by type
        citations = []
        references = []
        related = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue  # Skip failed requests
            task_type = task_types[i]
            if task_type == "citations":
                citations = result
            elif task_type == "references":
                references = result
            elif task_type == "related":
                related = result
        
        # Combine all sources
        all_papers = citations + references + related
        
        if not all_papers:
            return []
        
        # Deduplicate
        merged = merge_papers(all_papers)
        
        # Enrich with OA links
        merged = await enrich_papers(merged, fetch_oa_links=True)
        
        # Rank by citations (foundational mode for related papers)
        ranked = rank_papers(merged, mode="foundational", limit=limit)
        
        # Convert to response
        return [
            RelatedPaperResponse(
                id=p.id,
                doi=p.doi,
                title=p.title,
                year=p.year,
                venue=p.venue,
                authors=[
                    AuthorResponse(name=a.name, affiliations=a.affiliations)
                    for a in p.authors
                ],
                citationCount=p.citation_count,
                oaUrl=p.oa_url,
                doiUrl=p.doi_url,
            )
            for p in ranked
        ]
        
    finally:
        await s2_adapter.close()
        await oa_adapter.close()


class PaperUpdateRequest(BaseModel):
    """Request body for updating paper bookmark/comment."""
    title: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: Optional[list[AuthorResponse]] = None
    citationCount: Optional[int] = None
    citationSource: Optional[str] = None
    oaUrl: Optional[str] = None
    publisherUrl: Optional[str] = None
    doiUrl: Optional[str] = None
    topics: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    sourceIds: Optional[dict[str, str]] = None


@router.put("/paper/{paper_id}/select", response_model=dict)
async def select_paper(
    paper_id: str = Path(..., description="Paper ID"),
    selected: bool = Query(True, description="Whether to select the paper"),
    paper_data: Optional[PaperUpdateRequest] = Body(default=None, description="Paper data to save"),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Select or deselect a paper (bookmark)."""
    from app.db.database import is_db_available
    from app.db.models import Paper as PaperModel
    from sqlalchemy import select
    from datetime import date as date_type
    
    if not is_db_available() or db is None:
        # Fallback: return success without persistence
        return {"paper_id": paper_id, "selected": selected, "persisted": False}
    
    try:
        # Try to find paper in database
        stmt = select(PaperModel).where(PaperModel.id == paper_id)
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        
        if paper:
            # Update existing paper
            paper.selected = selected
            # Update paper data if provided (and not None)
            if paper_data is not None and paper_data.title:
                if paper_data.title:
                    paper.title = paper_data.title
                if paper_data.doi:
                    paper.doi = paper_data.doi
                if paper_data.abstract:
                    paper.abstract = paper_data.abstract
                if paper_data.year:
                    paper.year = paper_data.year
                if paper_data.venue:
                    paper.venue = paper_data.venue
                if paper_data.authors:
                    paper.authors_json = [{"name": a.name, "affiliations": a.affiliations} for a in paper_data.authors]
                if paper_data.citationCount is not None:
                    paper.citation_count = paper_data.citationCount
                if paper_data.citationSource:
                    paper.citation_source = paper_data.citationSource
                if paper_data.oaUrl:
                    paper.oa_url = paper_data.oaUrl
                if paper_data.publisherUrl:
                    paper.publisher_url = paper_data.publisherUrl
                if paper_data.doiUrl:
                    paper.doi_url = paper_data.doiUrl
                if paper_data.topics:
                    paper.topics_json = paper_data.topics
                if paper_data.keywords:
                    paper.keywords_json = paper_data.keywords
                if paper_data.sourceIds:
                    paper.source_ids_json = paper_data.sourceIds
            await db.commit()
            print(f"✓ Updated bookmark for paper {paper_id}: selected={selected}")
            return {"paper_id": paper_id, "selected": selected, "persisted": True}
        else:
            # Paper not in database yet - create entry if we have data
            if paper_data and paper_data.title and paper_data.title.strip():
                new_paper = PaperModel(
                    id=paper_id,
                    title=paper_data.title.strip(),
                    doi=paper_data.doi,
                    abstract=paper_data.abstract,
                    year=paper_data.year,
                    venue=paper_data.venue,
                    authors_json=[{"name": a.name, "affiliations": a.affiliations} for a in (paper_data.authors or [])],
                    citation_count=paper_data.citationCount,
                    citation_source=paper_data.citationSource,
                    oa_url=paper_data.oaUrl,
                    publisher_url=paper_data.publisherUrl,
                    doi_url=paper_data.doiUrl,
                    topics_json=paper_data.topics or [],
                    keywords_json=paper_data.keywords or [],
                    source_ids_json=paper_data.sourceIds or {},
                    selected=selected,
                )
                db.add(new_paper)
                await db.commit()
                print(f"✓ Created new paper entry for bookmark: {paper_id} ({paper_data.title[:50]}...)")
                return {"paper_id": paper_id, "selected": selected, "persisted": True, "note": "Paper entry created"}
            else:
                error_msg = "Paper title is required to create bookmark entry"
                print(f"⚠ Bookmark request for {paper_id} but no valid paper data provided")
                return {"paper_id": paper_id, "selected": selected, "persisted": False, "error": error_msg}
    except Exception as e:
        await db.rollback()
        print(f"✗ Error updating bookmark for {paper_id}: {e}")
        import traceback
        traceback.print_exc()
        return {"paper_id": paper_id, "selected": selected, "persisted": False, "error": str(e)}


@router.put("/paper/{paper_id}/comment", response_model=dict)
async def update_paper_comment(
    paper_id: str = Path(..., description="Paper ID"),
    comment: Optional[str] = Query(None, description="Comment text"),
    paper_data: Optional[PaperUpdateRequest] = Body(default=None, description="Paper data to save"),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Update comment/notes on a paper."""
    from app.db.database import is_db_available
    from app.db.models import Paper as PaperModel
    from sqlalchemy import select
    
    if not is_db_available() or db is None:
        # Fallback: return success without persistence
        return {"paper_id": paper_id, "comment": comment, "persisted": False}
    
    try:
        # Try to find paper in database
        stmt = select(PaperModel).where(PaperModel.id == paper_id)
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        
        if paper:
            # Update existing paper
            paper.comments = comment
            # Update paper data if provided (and not None)
            if paper_data is not None and paper_data.title:
                if paper_data.title:
                    paper.title = paper_data.title
                if paper_data.doi:
                    paper.doi = paper_data.doi
                if paper_data.abstract:
                    paper.abstract = paper_data.abstract
                if paper_data.year:
                    paper.year = paper_data.year
                if paper_data.venue:
                    paper.venue = paper_data.venue
                if paper_data.authors:
                    paper.authors_json = [{"name": a.name, "affiliations": a.affiliations} for a in paper_data.authors]
                if paper_data.citationCount is not None:
                    paper.citation_count = paper_data.citationCount
                if paper_data.citationSource:
                    paper.citation_source = paper_data.citationSource
                if paper_data.oaUrl:
                    paper.oa_url = paper_data.oaUrl
                if paper_data.publisherUrl:
                    paper.publisher_url = paper_data.publisherUrl
                if paper_data.doiUrl:
                    paper.doi_url = paper_data.doiUrl
                if paper_data.topics:
                    paper.topics_json = paper_data.topics
                if paper_data.keywords:
                    paper.keywords_json = paper_data.keywords
                if paper_data.sourceIds:
                    paper.source_ids_json = paper_data.sourceIds
            await db.commit()
            print(f"✓ Updated comment for paper {paper_id}: comment={'set' if comment else 'cleared'}")
            return {"paper_id": paper_id, "comment": comment, "persisted": True}
        else:
            # Paper not in database yet - create entry if we have data
            if paper_data and paper_data.title and paper_data.title.strip():
                new_paper = PaperModel(
                    id=paper_id,
                    title=paper_data.title.strip(),
                    doi=paper_data.doi,
                    abstract=paper_data.abstract,
                    year=paper_data.year,
                    venue=paper_data.venue,
                    authors_json=[{"name": a.name, "affiliations": a.affiliations} for a in (paper_data.authors or [])],
                    citation_count=paper_data.citationCount,
                    citation_source=paper_data.citationSource,
                    oa_url=paper_data.oaUrl,
                    publisher_url=paper_data.publisherUrl,
                    doi_url=paper_data.doiUrl,
                    topics_json=paper_data.topics or [],
                    keywords_json=paper_data.keywords or [],
                    source_ids_json=paper_data.sourceIds or {},
                    comments=comment,
                )
                db.add(new_paper)
                await db.commit()
                print(f"✓ Created new paper entry with comment: {paper_id} ({paper_data.title[:50]}...)")
                return {"paper_id": paper_id, "comment": comment, "persisted": True, "note": "Paper entry created"}
            else:
                error_msg = "Paper title is required to create comment entry"
                print(f"⚠ Comment request for {paper_id} but no valid paper data provided")
                return {"paper_id": paper_id, "comment": comment, "persisted": False, "error": error_msg}
    except Exception as e:
        await db.rollback()
        print(f"✗ Error updating comment for {paper_id}: {e}")
        import traceback
        traceback.print_exc()
        return {"paper_id": paper_id, "comment": comment, "persisted": False, "error": str(e)}


@router.get("/papers/bookmarked", response_model=list[PaperDetailResponse])
async def get_bookmarked_papers(
    db: Optional[AsyncSession] = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
):
    """Get all bookmarked papers."""
    from app.db.database import is_db_available
    from app.db.models import Paper as PaperModel
    from sqlalchemy import select, desc
    
    if not is_db_available() or db is None:
        print("⚠ Database not available for bookmarked papers query")
        return []
    
    try:
        stmt = select(PaperModel).where(PaperModel.selected == True).order_by(desc(PaperModel.updated_at)).limit(limit)
        result = await db.execute(stmt)
        papers = result.scalars().all()
        
        print(f"✓ Found {len(papers)} bookmarked papers in database")
        
        # Convert to response format
        response_papers = []
        for paper in papers:
            # Parse authors JSON
            authors_list = []
            if paper.authors_json:
                if isinstance(paper.authors_json, list):
                    for a in paper.authors_json:
                        if isinstance(a, dict):
                            authors_list.append(AuthorResponse(
                                name=a.get("name", ""),
                                affiliations=a.get("affiliations", [])
                            ))
                        elif isinstance(a, str):
                            authors_list.append(AuthorResponse(name=a, affiliations=[]))
            
            response_papers.append(PaperDetailResponse(
                id=paper.id,
                doi=paper.doi,
                title=paper.title,
                abstract=paper.abstract,
                year=paper.year,
                publicationDate=paper.publication_date.isoformat() if paper.publication_date else None,
                venue=paper.venue,
                authors=authors_list,
                citationCount=paper.citation_count,
                citationSource=paper.citation_source,
                oaUrl=paper.oa_url,
                publisherUrl=paper.publisher_url,
                doiUrl=paper.doi_url,
                urls=paper.urls_json or [],
                topics=paper.topics_json or [],
                keywords=paper.keywords_json or [],
                comments=paper.comments,
                numberOfPages=paper.number_of_pages,
                pages=paper.pages,
                selected=paper.selected,
                categories=paper.categories_json or {},
                databases=paper.databases_json or [],
                sourceIds=paper.source_ids_json or {},
                citationKey=paper.get_citation_key() if hasattr(paper, 'get_citation_key') else None,
                score=0.0,  # Default score for bookmarked papers
                whyRecommended=[],  # Default empty list
            ))
        
        return response_papers
    except Exception as e:
        print(f"Error fetching bookmarked papers: {e}")
        return []


@router.get("/papers/with-notes", response_model=list[PaperDetailResponse])
async def get_papers_with_notes(
    db: Optional[AsyncSession] = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
):
    """Get all papers with notes/comments."""
    from app.db.database import is_db_available
    from app.db.models import Paper as PaperModel
    from sqlalchemy import select, desc, and_
    
    if not is_db_available() or db is None:
        print("⚠ Database not available for papers with notes query")
        return []
    
    try:
        # Query papers with non-empty comments
        stmt = select(PaperModel).where(
            and_(
                PaperModel.comments.isnot(None),
                PaperModel.comments != ""
            )
        ).order_by(desc(PaperModel.updated_at)).limit(limit)
        result = await db.execute(stmt)
        papers = result.scalars().all()
        
        print(f"✓ Found {len(papers)} papers with notes in database")
        
        # Convert to response format
        response_papers = []
        for paper in papers:
            # Parse authors JSON
            authors_list = []
            if paper.authors_json:
                if isinstance(paper.authors_json, list):
                    for a in paper.authors_json:
                        if isinstance(a, dict):
                            authors_list.append(AuthorResponse(
                                name=a.get("name", ""),
                                affiliations=a.get("affiliations", [])
                            ))
                        elif isinstance(a, str):
                            authors_list.append(AuthorResponse(name=a, affiliations=[]))
            
            response_papers.append(PaperDetailResponse(
                id=paper.id,
                doi=paper.doi,
                title=paper.title,
                abstract=paper.abstract,
                year=paper.year,
                publicationDate=paper.publication_date.isoformat() if paper.publication_date else None,
                venue=paper.venue,
                authors=authors_list,
                citationCount=paper.citation_count,
                citationSource=paper.citation_source,
                oaUrl=paper.oa_url,
                publisherUrl=paper.publisher_url,
                doiUrl=paper.doi_url,
                urls=paper.urls_json or [],
                topics=paper.topics_json or [],
                keywords=paper.keywords_json or [],
                comments=paper.comments,
                numberOfPages=paper.number_of_pages,
                pages=paper.pages,
                selected=paper.selected,
                categories=paper.categories_json or {},
                databases=paper.databases_json or [],
                sourceIds=paper.source_ids_json or {},
                citationKey=paper.get_citation_key() if hasattr(paper, 'get_citation_key') else None,
                score=0.0,  # Default score for papers with notes
                whyRecommended=[],  # Default empty list
            ))
        
        return response_papers
    except Exception as e:
        print(f"Error fetching papers with notes: {e}")
        return []


@router.get("/publication/{publication_id}", response_model=PublicationResponse)
async def get_publication(
    publication_id: str = Path(..., description="Publication ID"),
):
    """Get detailed information about a publication (journal/conference/book)."""
    # TODO: Implement publication lookup from database
    # For now, this is a placeholder endpoint
    raise HTTPException(status_code=501, detail="Publication endpoint not yet implemented")

