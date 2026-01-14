"""Generate explanation bullets for why papers are recommended."""

from typing import Literal
from datetime import datetime

from app.dedup.merge import MergedPaper
from app.ranking.features import compute_features, PaperFeatures
from app.ranking.scoring import (
    get_feature_contributions,
    FOUNDATIONAL_WEIGHTS,
    RECENT_WEIGHTS,
)


# Explanation templates
EXPLANATIONS = {
    "high_relevance": "High semantic match to your topic",
    "top_cited": "Top-cited within the candidate set",
    "highly_cited": "Highly cited ({count:,} citations)",
    "classic": "Classic paper in the field",
    "fast_growth": "Fast citation growth for a recent paper",
    "trending": "Trending: rising citations",
    "very_recent": "Published recently ({year})",
    "survey": "Survey/Review (good starting point)",
    "open_access": "Open access available",
    "venue": "Published in recognized venue",
}


def generate_why_bullets(
    paper: MergedPaper,
    mode: Literal["foundational", "recent"],
    all_papers: list[MergedPaper],
    max_bullets: int = 4,
) -> list[str]:
    """Generate explanation bullets for why a paper is recommended.
    
    Args:
        paper: The paper to explain
        mode: Current ranking mode
        all_papers: All papers in the candidate set (for percentile computation)
        max_bullets: Maximum number of bullets to return
        
    Returns:
        List of explanation strings
    """
    bullets = []
    current_year = datetime.now().year
    
    # Compute features
    features = compute_features(paper, current_year)
    
    # Get weights for mode
    weights = FOUNDATIONAL_WEIGHTS if mode == "foundational" else RECENT_WEIGHTS
    
    # Get feature contributions
    contributions = get_feature_contributions(features, weights)
    
    # Sort by contribution (highest first)
    sorted_contributions = sorted(
        contributions.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    
    # Compute percentiles for context
    all_citations = [p.citation_count or 0 for p in all_papers]
    all_citations.sort()
    paper_citations = paper.citation_count or 0
    
    citation_percentile = 0
    if all_citations:
        below_count = sum(1 for c in all_citations if c < paper_citations)
        citation_percentile = below_count / len(all_citations)
    
    # Generate bullets based on top contributors
    for feature, contribution in sorted_contributions:
        if contribution <= 0:
            continue
        
        if len(bullets) >= max_bullets:
            break
        
        bullet = _feature_to_bullet(
            feature,
            contribution,
            paper,
            features,
            mode,
            citation_percentile,
            current_year,
        )
        
        if bullet and bullet not in bullets:
            bullets.append(bullet)
    
    # Always include OA if available and not already included
    if paper.is_open_access and EXPLANATIONS["open_access"] not in bullets:
        if len(bullets) < max_bullets:
            bullets.append(EXPLANATIONS["open_access"])
    
    # Always include survey if applicable and not already included
    if paper.is_survey and EXPLANATIONS["survey"] not in bullets:
        if len(bullets) < max_bullets:
            bullets.append(EXPLANATIONS["survey"])
    
    return bullets[:max_bullets]


def _feature_to_bullet(
    feature: str,
    contribution: float,
    paper: MergedPaper,
    features: PaperFeatures,
    mode: str,
    citation_percentile: float,
    current_year: int,
) -> str | None:
    """Convert a feature contribution to an explanation bullet."""
    
    if feature == "relevance" and contribution > 0.1:
        # Only show "high semantic match" for papers with above-average normalized relevance
        # This prevents showing it for every paper when all have similar relevance
        if features.relevance > 0.6:  # Above 60th percentile after normalization
            return EXPLANATIONS["high_relevance"]
        return None  # Skip this explanation for lower-relevance papers
    
    elif feature == "citations":
        if citation_percentile >= 0.9:
            return EXPLANATIONS["top_cited"]
        elif paper.citation_count and paper.citation_count >= 1000:
            return EXPLANATIONS["highly_cited"].format(count=paper.citation_count)
        elif paper.citation_count and paper.citation_count >= 100 and features.age_years >= 10:
            return EXPLANATIONS["classic"]
    
    elif feature == "velocity":
        if mode == "recent" and contribution > 0.1:
            return EXPLANATIONS["fast_growth"]
        elif contribution > 0.05:
            return EXPLANATIONS["trending"]
    
    elif feature == "recency":
        if paper.year and paper.year >= current_year - 2:
            return EXPLANATIONS["very_recent"].format(year=paper.year)
    
    elif feature == "survey" and paper.is_survey:
        return EXPLANATIONS["survey"]
    
    elif feature == "open_access" and paper.is_open_access:
        return EXPLANATIONS["open_access"]
    
    elif feature == "venue" and paper.venue:
        return EXPLANATIONS["venue"]
    
    return None


def add_explanations(
    papers: list[MergedPaper],
    mode: Literal["foundational", "recent"],
) -> list[MergedPaper]:
    """Add why_recommended bullets to all papers."""
    for paper in papers:
        paper.why_recommended = generate_why_bullets(paper, mode, papers)
    
    return papers

