"""Similarity computation for paper deduplication."""

from rapidfuzz import fuzz
from typing import Optional

from app.adapters.base import PaperResult
from app.dedup.normalize import normalize_title, extract_first_author_lastname


def title_similarity(title1: str, title2: str) -> float:
    """Compute normalized title similarity (0-1 scale)."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Use token sort ratio for better handling of word order differences
    score = fuzz.token_sort_ratio(norm1, norm2)
    
    return score / 100.0


def author_similarity(paper1: PaperResult, paper2: PaperResult) -> float:
    """Compute author similarity based on first author last name."""
    lastname1 = extract_first_author_lastname(paper1.authors)
    lastname2 = extract_first_author_lastname(paper2.authors)
    
    if not lastname1 or not lastname2:
        return 0.5  # Uncertain - could be same or different
    
    # Exact match on last name
    if lastname1 == lastname2:
        return 1.0
    
    # Fuzzy match for minor variations
    ratio = fuzz.ratio(lastname1, lastname2) / 100.0
    return ratio


def year_similarity(year1: Optional[int], year2: Optional[int]) -> float:
    """Compute year similarity (allows for minor differences)."""
    if year1 is None or year2 is None:
        return 0.5  # Uncertain
    
    diff = abs(year1 - year2)
    
    if diff == 0:
        return 1.0
    elif diff == 1:
        return 0.9  # Off by one year is common
    elif diff <= 2:
        return 0.7
    else:
        return 0.0  # Likely different papers


def are_likely_same_paper(
    paper1: PaperResult,
    paper2: PaperResult,
    title_threshold: float = 0.9,
) -> bool:
    """Determine if two papers are likely the same work.
    
    Strategy:
    1. If both have DOIs and they match -> definitely same
    2. If both have DOIs and they don't match -> definitely different
    3. Otherwise, use fuzzy matching on title + author + year
       - Require year within +/-2 OR at least one year missing
       - Require at least one author overlap (for non-exact title matches)
    """
    # DOI comparison (definitive when both present)
    if paper1.doi and paper2.doi:
        return paper1.doi.lower() == paper2.doi.lower()
    
    # Title similarity
    title_sim = title_similarity(paper1.title, paper2.title)
    if title_sim < title_threshold:
        return False
    
    # Year check: require years within +/-2 OR at least one side missing
    if paper1.year and paper2.year:
        year_diff = abs(paper1.year - paper2.year)
        if year_diff > 2:
            # Years too far apart - likely different papers even with similar titles
            return False
    
    # If title is very similar (>= 0.95) and years are compatible, likely same
    if title_sim >= 0.95:
        return True
    
    # For title matches between 0.9-0.95, require author overlap
    author_sim = author_similarity(paper1, paper2)
    
    # Require at least some author overlap (> 0.3) for non-exact title matches
    if author_sim < 0.3:
        return False
    
    year_sim = year_similarity(paper1.year, paper2.year)
    
    # Combined score with higher weight on author match
    combined = (title_sim * 0.5) + (author_sim * 0.35) + (year_sim * 0.15)
    
    return combined >= 0.85


def compute_merge_priority(paper: PaperResult) -> int:
    """Compute priority for keeping data from this source during merge.
    
    Higher score = prefer this source's data.
    """
    score = 0
    
    # Prefer sources with DOIs
    if paper.doi:
        score += 100
    
    # Prefer sources with abstracts
    if paper.abstract:
        score += 50
    
    # Prefer sources with citation counts
    if paper.citation_count is not None:
        score += 30
    
    # Prefer sources with more authors
    score += min(len(paper.authors) * 5, 25)
    
    # Prefer certain sources
    source_priorities = {
        "semantic_scholar": 20,
        "openalex": 18,
        "crossref": 15,
        "pubmed": 12,
        "arxiv": 10,
    }
    score += source_priorities.get(paper.source, 0)
    
    # Prefer papers with OA URLs
    if paper.oa_url:
        score += 10
    
    return score

