"""Scoring functions for paper ranking."""

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from app.dedup.merge import MergedPaper
from app.ranking.features import PaperFeatures, compute_features, normalize_features

logger = logging.getLogger(__name__)

# Two-stage ranking constants
RELEVANCE_PREFILTER_LIMIT = 200  # Pre-filter to top K by relevance before re-ranking
MAX_SURVEYS_IN_RESULTS = 6  # Soft cap on survey papers unless survey_only mode


# Scoring weights for each mode
@dataclass
class ScoringWeights:
    """Weights for combining features into final score."""
    relevance: float
    citations: float
    velocity: float
    recency: float
    venue: float
    survey: float
    open_access: float


FOUNDATIONAL_WEIGHTS = ScoringWeights(
    relevance=0.45,
    citations=0.35,
    velocity=0.0,   # Not used in foundational
    recency=0.0,    # Not used in foundational
    venue=0.10,
    survey=0.05,
    open_access=0.05,
)

RECENT_WEIGHTS = ScoringWeights(
    relevance=0.55,
    citations=0.0,  # Not used in recent
    velocity=0.25,
    recency=0.15,
    venue=0.03,
    survey=0.0,     # Less important for recent
    open_access=0.02,
)


def compute_score(
    features: PaperFeatures,
    weights: ScoringWeights,
) -> float:
    """Compute final score using weighted combination of features."""
    score = (
        weights.relevance * features.relevance +
        weights.citations * features.log_citations +
        weights.velocity * features.citation_velocity +
        weights.recency * features.recency +
        weights.venue * features.venue_signal +
        weights.survey * features.is_survey +
        weights.open_access * features.is_open_access
    )
    
    return score


def detect_query_intent(query: str) -> dict[str, float]:
    """Detect query intent and return weights.
    
    Returns a dictionary with intent scores:
    - survey_seeking: How much the query seeks surveys/reviews
    - recent_seeking: How much the query seeks recent papers
    - foundational_seeking: How much the query seeks foundational papers
    """
    query_lower = query.lower()
    
    intent = {
        "survey_seeking": 0.0,
        "recent_seeking": 0.0,
        "foundational_seeking": 0.0,
    }
    
    survey_keywords = ["survey", "review", "overview", "state of the art", "state-of-the-art", 
                       "comprehensive", "systematic review", "literature review"]
    recent_keywords = ["recent", "latest", "new", "current", "2024", "2023", "2022", 
                       "emerging", "trending", "cutting-edge", "cutting edge"]
    foundational_keywords = ["foundational", "classic", "seminal", "pioneering", 
                            "foundation", "fundamental", "original", "early"]
    
    for keyword in survey_keywords:
        if keyword in query_lower:
            intent["survey_seeking"] += 0.3
    
    for keyword in recent_keywords:
        if keyword in query_lower:
            intent["recent_seeking"] += 0.3
    
    for keyword in foundational_keywords:
        if keyword in query_lower:
            intent["foundational_seeking"] += 0.3
    
    # Normalize to [0, 1] range
    total = sum(intent.values())
    if total > 0:
        for key in intent:
            intent[key] = min(1.0, intent[key] / total)
    
    return intent


def rank_papers(
    papers: list[MergedPaper],
    mode: Literal["foundational", "recent"],
    limit: int = 20,
    survey_only: bool = False,
    query: Optional[str] = None,
) -> list[MergedPaper]:
    """Rank papers according to the specified mode using two-stage ranking.
    
    Two-stage ranking approach:
    1. Pre-filter to top K candidates by relevance score
    2. Re-rank within that set using mode-specific weights
    3. Apply survey cap (unless survey_only mode)
    
    Args:
        papers: List of merged papers to rank
        mode: Ranking mode ("foundational" or "recent")
        limit: Maximum number of papers to return
        survey_only: If True, skip survey cap
        
    Returns:
        Top papers sorted by score (highest first)
    """
    if not papers:
        return []
    
    # STAGE 1: Pre-filter by relevance
    # Sort papers by relevance score first to get most relevant candidates
    papers_by_relevance = sorted(
        papers, 
        key=lambda p: p.relevance_score if p.relevance_score else 0, 
        reverse=True
    )
    
    # Take top K by relevance for re-ranking
    candidates = papers_by_relevance[:RELEVANCE_PREFILTER_LIMIT]
    
    logger.debug(f"Two-stage ranking: {len(papers)} papers -> {len(candidates)} candidates after relevance filter")
    
    # Detect query intent if query provided
    query_intent = {}
    if query:
        query_intent = detect_query_intent(query)
        logger.debug(f"Query intent detected: {query_intent}")
    
    # Select weights based on mode, adjusted by query intent
    base_weights = FOUNDATIONAL_WEIGHTS if mode == "foundational" else RECENT_WEIGHTS
    weights = _adjust_weights_by_intent(base_weights, mode, query_intent)
    
    # Compute features for candidates only (pass query for unified relevance)
    papers_with_features = [
        (paper, compute_features(paper, query=query))
        for paper in candidates
    ]
    
    # Apply year filter for recent mode
    if mode == "recent":
        # For recent mode, prefer papers from last 3 years
        # But don't exclude older papers entirely
        from datetime import datetime
        current_year = datetime.now().year
        
        # Boost recency for recent papers
        for paper, features in papers_with_features:
            if paper.year and paper.year >= current_year - 3:
                # Extra boost for very recent papers
                features.recency = min(1.0, features.recency * 1.5)
    
    # STAGE 2: Re-rank by mode-specific formula
    # Normalize features within candidate set
    normalized = normalize_features(papers_with_features)
    
    # Compute scores
    scored = []
    for paper, features in normalized:
        score = compute_score(features, weights)
        paper.score = score
        scored.append((paper, score, features))
    
    # Sort by score (descending)
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Apply survey cap (unless survey_only mode)
    if not survey_only:
        result = _apply_adaptive_survey_cap(scored, limit, query_intent)
    else:
        result = [paper for paper, _, _ in scored[:limit]]
    
    # Apply diversity filters
    result = apply_diversity_filters(result, limit)
    
    return result


def apply_diversity_filters(
    papers: list[MergedPaper],
    limit: int,
) -> list[MergedPaper]:
    """Apply diversity filters to ensure result variety.
    
    Ensures:
    - Author diversity: max 2 papers per first author
    - Venue diversity: max 3 papers per venue
    - Temporal diversity: balanced year distribution
    """
    if len(papers) <= limit:
        return papers
    
    result = []
    author_counts = {}  # first_author -> count
    venue_counts = {}  # venue -> count
    year_distribution = {}  # decade -> count
    
    for paper in papers:
        if len(result) >= limit:
            break
        
        # Author diversity: max 2 papers per first author
        first_author = None
        if paper.authors:
            first_author = paper.authors[0].name
            author_count = author_counts.get(first_author, 0)
            if author_count >= 2:
                continue
            author_counts[first_author] = author_count + 1
        
        # Venue diversity: max 3 papers per venue
        if paper.venue:
            venue_count = venue_counts.get(paper.venue, 0)
            if venue_count >= 3:
                continue
            venue_counts[paper.venue] = venue_count + 1
        
        # Temporal diversity: ensure balanced decade distribution
        if paper.year:
            decade = (paper.year // 10) * 10
            decade_count = year_distribution.get(decade, 0)
            # Allow more papers from same decade if we haven't filled 70% of results
            if decade_count >= 3 and len(result) < limit * 0.7:
                continue
            year_distribution[decade] = decade_count + 1
        
        result.append(paper)
    
    # If we filtered too many, backfill with remaining papers
    if len(result) < limit:
        remaining = [p for p in papers if p not in result]
        result.extend(remaining[:limit - len(result)])
    
    return result[:limit]


def _adjust_weights_by_intent(
    base_weights: ScoringWeights,
    mode: Literal["foundational", "recent"],
    query_intent: dict[str, float],
) -> ScoringWeights:
    """Adjust scoring weights based on query intent."""
    if not query_intent:
        return base_weights
    
    # Create a copy to modify
    weights = ScoringWeights(
        relevance=base_weights.relevance,
        citations=base_weights.citations,
        velocity=base_weights.velocity,
        recency=base_weights.recency,
        venue=base_weights.venue,
        survey=base_weights.survey,
        open_access=base_weights.open_access,
    )
    
    # Adjust survey weight based on survey-seeking intent
    survey_intent = query_intent.get("survey_seeking", 0.0)
    if survey_intent > 0.3:
        # Increase survey weight for survey-seeking queries
        weights.survey = min(0.15, base_weights.survey + survey_intent * 0.1)
    
    # Adjust recency/velocity for recent-seeking queries
    recent_intent = query_intent.get("recent_seeking", 0.0)
    if recent_intent > 0.3 and mode == "recent":
        # Boost recency and velocity
        weights.recency = min(0.25, base_weights.recency + recent_intent * 0.1)
        weights.velocity = min(0.35, base_weights.velocity + recent_intent * 0.1)
    
    # Adjust citations for foundational-seeking queries
    foundational_intent = query_intent.get("foundational_seeking", 0.0)
    if foundational_intent > 0.3 and mode == "foundational":
        # Boost citations
        weights.citations = min(0.45, base_weights.citations + foundational_intent * 0.1)
    
    return weights


def _apply_survey_cap(
    scored: list[tuple[MergedPaper, float, PaperFeatures]], 
    limit: int
) -> list[MergedPaper]:
    """Apply soft cap on survey papers in results (legacy method).
    
    Ensures at least (limit - MAX_SURVEYS_IN_RESULTS) non-survey papers 
    appear in the top results.
    """
    result = []
    survey_count = 0
    
    for paper, score, features in scored:
        if len(result) >= limit:
            break
        
        if paper.is_survey:
            if survey_count < MAX_SURVEYS_IN_RESULTS:
                result.append(paper)
                survey_count += 1
            else:
                # Survey cap reached, skip this survey
                continue
        else:
            result.append(paper)
    
    # If we don't have enough papers, backfill with remaining surveys
    if len(result) < limit:
        for paper, score, features in scored:
            if len(result) >= limit:
                break
            if paper not in result:
                result.append(paper)
    
    return result


def _apply_adaptive_survey_cap(
    scored: list[tuple[MergedPaper, float, PaperFeatures]],
    limit: int,
    query_intent: dict[str, float],
) -> list[MergedPaper]:
    """Apply adaptive survey cap based on query intent and survey quality.
    
    Adapts the survey cap based on:
    - Query intent (survey-seeking queries get more surveys)
    - Survey quality (highly-cited surveys get priority)
    """
    surveys = [(p, s, f) for p, s, f in scored if p.is_survey]
    non_surveys = [(p, s, f) for p, s, f in scored if not p.is_survey]
    
    # Adaptive cap based on query intent
    base_cap = MAX_SURVEYS_IN_RESULTS
    survey_seeking = query_intent.get("survey_seeking", 0.0)
    
    if survey_seeking > 0.5:
        # Survey-seeking queries: allow up to 50% surveys
        survey_cap = min(limit // 2, len(surveys))
    else:
        survey_cap = base_cap
    
    # Quality threshold: only include surveys above median score
    if surveys:
        survey_scores = sorted([s for _, s, _ in surveys])
        median_score = survey_scores[len(survey_scores) // 2]
        quality_surveys = [(p, s, f) for p, s, f in surveys if s >= median_score]
    else:
        quality_surveys = []
    
    # Interleave surveys and non-surveys
    result = []
    survey_idx = 0
    non_survey_idx = 0
    
    while len(result) < limit:
        # Add survey if under cap and available
        if survey_idx < len(quality_surveys) and survey_idx < survey_cap:
            result.append(quality_surveys[survey_idx][0])
            survey_idx += 1
        # Add non-survey
        elif non_survey_idx < len(non_surveys):
            result.append(non_surveys[non_survey_idx][0])
            non_survey_idx += 1
        else:
            # If we've exhausted quality surveys but have more, add them
            if survey_idx < len(surveys) and len(result) < limit:
                result.append(surveys[survey_idx][0])
                survey_idx += 1
            else:
                break
    
    return result


def get_feature_contributions(
    features: PaperFeatures,
    weights: ScoringWeights,
) -> dict[str, float]:
    """Get individual feature contributions to the score."""
    return {
        "relevance": weights.relevance * features.relevance,
        "citations": weights.citations * features.log_citations,
        "velocity": weights.velocity * features.citation_velocity,
        "recency": weights.recency * features.recency,
        "venue": weights.venue * features.venue_signal,
        "survey": weights.survey * features.is_survey,
        "open_access": weights.open_access * features.is_open_access,
    }

