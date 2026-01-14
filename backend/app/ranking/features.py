"""Feature extraction for paper ranking."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.dedup.merge import MergedPaper

# Known high-quality venues (can be expanded)
TOP_TIER_VENUES = {
    # Journals
    "nature", "science", "cell", "lancet", "nejm", "bmj",
    "pnas", "plos one", "ieee", "acm", "springer", "elsevier",
    # Conferences
    "neurips", "icml", "iclr", "aaai", "ijcai", "cvpr", "iccv", "eccv",
    "acl", "emnlp", "naacl", "sigir", "kdd", "www", "chi", "uist",
}


@dataclass
class PaperFeatures:
    """Extracted features for a paper."""
    
    # Relevance (from source or computed)
    relevance: float
    
    # Citation-based
    log_citations: float
    citation_velocity: float
    
    # Time-based
    recency: float
    age_years: int
    
    # Binary flags
    is_survey: float
    is_open_access: float
    
    # Venue signal (placeholder for MVP)
    venue_signal: float


def compute_features(
    paper: MergedPaper,
    current_year: Optional[int] = None,
    query: Optional[str] = None,
) -> PaperFeatures:
    """Compute ranking features for a paper."""
    if current_year is None:
        current_year = datetime.now().year
    
    # Age in years
    age_years = 0
    if paper.year:
        age_years = max(0, current_year - paper.year)
    
    # Relevance score - use unified relevance computation
    relevance = compute_unified_relevance(paper, query)
    
    # Log-scaled citations
    citations = paper.citation_count or 0
    log_citations = math.log1p(citations)  # log(1 + citations)
    
    # Citation velocity (citations per year) with acceleration detection
    # For very new papers (< 1 year), use the raw count
    if age_years <= 0:
        citation_velocity = float(citations)
    else:
        base_velocity = citations / age_years
        
        # Detect acceleration: boost for very recent papers with high citations
        # This indicates papers with accelerating citation growth
        if age_years < 2 and citations > 10:
            # Recent papers with citations are likely accelerating
            acceleration_factor = 1.5
        elif age_years < 3 and citations > 20:
            # Moderately recent papers with good citations
            acceleration_factor = 1.2
        else:
            acceleration_factor = 1.0
        
        citation_velocity = base_velocity * acceleration_factor
    
    # Log-scale velocity for comparison
    log_velocity = math.log1p(citation_velocity)
    
    # Recency score (exponential decay)
    # Papers from current year = 1.0, decreasing by ~50% every 5 years
    decay_rate = 0.15
    recency = math.exp(-decay_rate * age_years)
    
    # Binary flags
    is_survey = 1.0 if paper.is_survey else 0.0
    is_open_access = 1.0 if paper.is_open_access else 0.0
    
    # Venue signal - enhanced with quality metrics
    venue_signal = compute_venue_quality(paper)
    
    return PaperFeatures(
        relevance=relevance,
        log_citations=log_citations,
        citation_velocity=log_velocity,
        recency=recency,
        age_years=age_years,
        is_survey=is_survey,
        is_open_access=is_open_access,
        venue_signal=venue_signal,
    )


def normalize_features(
    papers_with_features: list[tuple[MergedPaper, PaperFeatures]],
) -> list[tuple[MergedPaper, PaperFeatures]]:
    """Normalize features using robust percentile-based method.
    
    Uses interquartile range (IQR) for robust normalization that handles outliers.
    Falls back to min-max if IQR is too small.
    """
    if not papers_with_features:
        return []
    
    # Extract values for normalization
    citations = [f.log_citations for _, f in papers_with_features]
    velocities = [f.citation_velocity for _, f in papers_with_features]
    relevances = [f.relevance for _, f in papers_with_features]
    
    # Use percentile-based robust normalization
    def percentile_normalize(values: list[float], value: float) -> float:
        """Normalize using percentiles (robust to outliers)."""
        if not values:
            return 0.5
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Compute percentiles
        p25_idx = max(0, int(n * 0.25))
        p75_idx = min(n - 1, int(n * 0.75))
        p25 = sorted_values[p25_idx]
        p75 = sorted_values[p75_idx]
        
        # Use IQR for robust normalization
        iqr = p75 - p25
        if iqr > 0.001:  # Avoid division by very small numbers
            # Normalize: (value - p25) / IQR, then clip to [0, 1]
            normalized = (value - p25) / iqr
            normalized = max(0.0, min(1.0, normalized))
            return normalized
        else:
            # Fallback to min-max if IQR is too small
            val_min, val_max = min(values), max(values)
            if val_max > val_min:
                return (value - val_min) / (val_max - val_min)
            else:
                return 0.5
    
    # Normalize
    result = []
    for paper, features in papers_with_features:
        # Normalize citations using robust method
        norm_cites = percentile_normalize(citations, features.log_citations)
        
        # Normalize velocity using robust method
        norm_vel = percentile_normalize(velocities, features.citation_velocity)
        
        # Normalize relevance using robust method
        norm_rel = percentile_normalize(relevances, features.relevance)
        
        normalized = PaperFeatures(
            relevance=norm_rel,
            log_citations=norm_cites,
            citation_velocity=norm_vel,
            recency=features.recency,
            age_years=features.age_years,
            is_survey=features.is_survey,
            is_open_access=features.is_open_access,
            venue_signal=features.venue_signal,
        )
        
        result.append((paper, normalized))
    
    return result


def compute_unified_relevance(paper: MergedPaper, query: Optional[str] = None) -> float:
    """Compute unified relevance score across sources.
    
    Combines:
    1. Source-provided relevance scores (weighted by source reliability)
    2. Query-paper similarity (if query provided)
    3. Topic/concept overlap
    """
    # 1. Source-provided relevance (weighted by source reliability)
    source_relevance = 0.0
    total_weight = 0.0
    
    # Source reliability weights
    source_weights = {
        "semantic_scholar": 1.0,  # Highest reliability
        "openalex": 0.9,
        "crossref": 0.8,
        "pubmed": 0.85,
        "arxiv": 0.7,
    }
    
    # Weight sources by their reliability
    if paper.relevance_score and paper.relevance_score > 0:
        # Use average source weight if multiple sources
        avg_weight = sum(source_weights.get(src, 0.5) for src in paper.sources) / max(len(paper.sources), 1)
        source_relevance = paper.relevance_score * avg_weight
        total_weight = avg_weight
    else:
        # Default relevance if no source score
        source_relevance = 0.5
        total_weight = 0.5
    
    # 2. Query-paper similarity (if query provided)
    query_similarity = 0.0
    if query:
        query_similarity = compute_query_similarity(query, paper)
    
    # 3. Topic/concept overlap
    topic_overlap = compute_topic_overlap(paper)
    
    # Combine with weights
    # If query provided, use query similarity; otherwise rely more on source relevance
    if query and query_similarity > 0:
        relevance = 0.4 * source_relevance + 0.4 * query_similarity + 0.2 * topic_overlap
    else:
        relevance = 0.7 * source_relevance + 0.3 * topic_overlap
    
    return max(0.0, min(1.0, relevance))


def compute_query_similarity(query: str, paper: MergedPaper) -> float:
    """Compute query-paper similarity using keyword matching."""
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Check title
    title_lower = paper.title.lower() if paper.title else ""
    title_words = set(title_lower.split())
    title_overlap = len(query_words & title_words) / max(len(query_words), 1)
    
    # Check abstract
    abstract_overlap = 0.0
    if paper.abstract:
        abstract_lower = paper.abstract.lower()
        abstract_words = set(abstract_lower.split())
        abstract_overlap = len(query_words & abstract_words) / max(len(query_words), 1)
    
    # Check keywords
    keyword_overlap = 0.0
    if paper.keywords:
        keyword_words = {kw.lower() for kw in paper.keywords}
        keyword_overlap = len(query_words & keyword_words) / max(len(query_words), 1)
    
    # Weighted combination: title most important, then abstract, then keywords
    similarity = 0.5 * title_overlap + 0.3 * abstract_overlap + 0.2 * keyword_overlap
    
    return min(1.0, similarity)


def compute_topic_overlap(paper: MergedPaper) -> float:
    """Compute topic/concept overlap score.
    
    For now, returns a score based on number of topics.
    Future: could compare against query topics.
    """
    if not paper.topics:
        return 0.3  # Default score if no topics
    
    # More topics = better coverage = higher score
    topic_count = len(paper.topics)
    # Normalize: 0 topics = 0.3, 5+ topics = 1.0
    overlap = min(1.0, 0.3 + (topic_count / 10.0))
    
    return overlap


def compute_venue_quality(paper: MergedPaper) -> float:
    """Compute venue quality score from publication metrics and venue name.
    
    Uses Publication model metrics if available, otherwise uses heuristics
    based on venue name and work type.
    """
    # TODO: When Publication model is integrated, use actual metrics
    # For now, use heuristics based on venue name and work_type
    
    if not paper.venue:
        return 0.0
    
    venue_lower = paper.venue.lower()
    score = 0.0
    
    # Check if venue matches known top-tier venues
    for top_venue in TOP_TIER_VENUES:
        if top_venue in venue_lower:
            score += 0.6
            break
    
    # Boost for journal/conference work types (vs book/preprint)
    if paper.work_type in ("journal", "conference"):
        score += 0.3
    elif paper.work_type == "book":
        score += 0.1
    
    # Future: When Publication model is integrated:
    # if paper.publication:
    #     pub = paper.publication
    #     # CiteScore contribution (0-0.4)
    #     if pub.cite_score:
    #         score += min(0.4, pub.cite_score / 25.0)
    #     # SJR contribution (0-0.4)
    #     if pub.sjr:
    #         score += min(0.4, pub.sjr / 5.0)
    #     # SNIP contribution (0-0.2)
    #     if pub.snip:
    #         score += min(0.2, pub.snip / 3.0)
    #     # Penalize predatory journals
    #     if pub.is_potentially_predatory:
    #         score *= 0.1
    
    return min(1.0, score)

