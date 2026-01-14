"""Enrichment logic for merged papers."""

from typing import Optional

from app.adapters.unpaywall import UnpaywallAdapter
from app.dedup.merge import MergedPaper


async def enrich_with_oa_links(
    papers: list[MergedPaper],
    unpaywall: Optional[UnpaywallAdapter] = None,
) -> list[MergedPaper]:
    """Enrich papers with open access links from Unpaywall.
    
    Only fetches OA links for papers that:
    - Have a DOI
    - Don't already have an OA URL
    """
    if unpaywall is None:
        unpaywall = UnpaywallAdapter()
    
    try:
        for paper in papers:
            # Skip if already has OA URL or no DOI
            if paper.oa_url or not paper.doi:
                continue
            
            # Try to get OA URL
            oa_url = await unpaywall.get_oa_url(paper.doi)
            if oa_url:
                paper.oa_url = oa_url
                paper.is_open_access = True
        
        return papers
        
    finally:
        await unpaywall.close()


def build_doi_urls(papers: list[MergedPaper]) -> list[MergedPaper]:
    """Ensure all papers with DOIs have doi_url set."""
    for paper in papers:
        if paper.doi and not paper.doi_url:
            paper.doi_url = f"https://doi.org/{paper.doi}"
    
    return papers


def fill_publisher_urls(papers: list[MergedPaper]) -> list[MergedPaper]:
    """Fill in missing publisher URLs where possible."""
    for paper in papers:
        # If no publisher URL but has DOI URL, use that
        if not paper.publisher_url and paper.doi_url:
            paper.publisher_url = paper.doi_url
    
    return papers


async def enrich_papers(
    papers: list[MergedPaper],
    fetch_oa_links: bool = True,
) -> list[MergedPaper]:
    """Apply all enrichment steps to papers.
    
    Steps:
    1. Build DOI URLs
    2. Fetch OA links from Unpaywall (optional)
    3. Fill in missing publisher URLs
    """
    # Step 1: Build DOI URLs
    papers = build_doi_urls(papers)
    
    # Step 2: Fetch OA links
    if fetch_oa_links:
        # Only fetch for papers that need it
        papers_needing_oa = [p for p in papers if not p.oa_url and p.doi]
        if papers_needing_oa:
            papers = await enrich_with_oa_links(papers)
    
    # Step 3: Fill publisher URLs
    papers = fill_publisher_urls(papers)
    
    return papers

