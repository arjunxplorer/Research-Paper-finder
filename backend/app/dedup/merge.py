"""Paper deduplication and merging logic."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import uuid

from app.adapters.base import PaperResult, Author
from app.dedup.normalize import (
    normalize_doi, normalize_paper, compute_work_key,
    WORK_TYPE_BOOK, WORK_TYPE_CHAPTER, WORK_TYPE_JOURNAL, WORK_TYPE_CONFERENCE,
)
from app.dedup.similarity import are_likely_same_paper, compute_merge_priority, title_similarity, author_similarity

logger = logging.getLogger(__name__)


@dataclass
class MergedPaper:
    """A paper merged from multiple sources."""
    
    id: str
    doi: Optional[str]
    title: str
    abstract: Optional[str]
    year: Optional[int]
    publication_date: Optional[date] = None  # Full publication date
    venue: Optional[str] = None
    authors: list[Author] = field(default_factory=list)
    citation_count: Optional[int] = None
    citation_source: Optional[str] = None
    oa_url: Optional[str] = None
    publisher_url: Optional[str] = None
    doi_url: Optional[str] = None
    urls: set[str] = field(default_factory=set)  # Set of URLs from different databases
    topics: list[str] = field(default_factory=list)
    keywords: set[str] = field(default_factory=set)  # Author-provided keywords
    comments: Optional[str] = None  # User comments/notes
    number_of_pages: Optional[int] = None
    pages: Optional[str] = None  # Page range (e.g., "123-145")
    selected: bool = False  # User selection/bookmark flag
    categories: dict[str, list[str]] = field(default_factory=dict)  # Facet -> categories
    databases: set[str] = field(default_factory=set)  # Database names where paper was found
    is_survey: bool = False
    is_open_access: bool = False
    
    # Additional identifiers (propagated from sources)
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    
    # Work type classification
    work_type: Optional[str] = None
    
    # Tracking
    source_ids: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    work_key: Optional[str] = None  # Canonical identifier used for clustering
    
    # Data quality tracking
    data_quality_flags: list[str] = field(default_factory=list)
    
    # Provenance tracking
    field_provenance: dict[str, str] = field(default_factory=dict)
    
    # Scoring (filled in later)
    score: float = 0.0
    relevance_score: float = 0.0
    why_recommended: list[str] = field(default_factory=list)
    
    def add_url(self, url: str) -> None:
        """Add a URL to the paper's URL set."""
        self.urls.add(url)
    
    def add_database(self, database_name: str) -> None:
        """Add a database name where the paper was found."""
        valid_databases = {"semantic_scholar", "openalex", "pubmed", "arxiv", "crossref"}
        if database_name not in valid_databases:
            raise ValueError(
                f"Invalid database name '{database_name}'. Valid databases: {', '.join(valid_databases)}"
            )
        self.databases.add(database_name)
    
    def get_citation_key(self) -> str:
        """Generate citation key following pattern <FIRST_AUTHOR><YEAR><TITLE_FIRST_WORD>."""
        # Extract first author last name
        author_key = "unknown"
        if self.authors:
            first_author = self.authors[0]
            author_name = first_author.name if hasattr(first_author, 'name') else str(first_author)
            # Extract last name (before comma or last word)
            if "," in author_name:
                author_key = author_name.split(",")[0].strip().lower().replace(" ", "")
            else:
                parts = author_name.split()
                if parts:
                    author_key = parts[-1].lower().replace(" ", "")
        
        # Extract year
        year_key = "XXXX"
        if self.publication_date:
            year_key = str(self.publication_date.year)
        elif self.year:
            year_key = str(self.year)
        
        # Extract first word of title
        title_key = self.title.split()[0].lower() if self.title else "unknown"
        
        # Combine and clean
        citation_key = re.sub(r"[^\w\d]", "", f"{author_key}{year_key}{title_key}")
        return citation_key
    
    def has_category_match(self, categories: dict[str, list[str]]) -> bool:
        """Check if paper matches provided category facets."""
        if not categories or not self.categories:
            return False
        
        for facet, facet_categories in categories.items():
            for facet_category in facet_categories:
                if facet_category in self.categories.get(facet, []):
                    return True
        return False
    
    def enrich(self, other: "MergedPaper") -> None:
        """Enrich this paper with data from another paper (duplicate)."""
        # Fill missing publication date
        if self.publication_date is None and other.publication_date is not None:
            self.publication_date = other.publication_date
        
        # Fill missing DOI
        if self.doi is None and other.doi is not None:
            self.doi = other.doi
            if other.doi_url:
                self.doi_url = other.doi_url
        
        # Use longer abstract if available
        if not self.abstract or (other.abstract and len(other.abstract) > len(self.abstract or "")):
            self.abstract = other.abstract
        
        # Use more authors if available
        if not self.authors or (other.authors and len(other.authors) > len(self.authors)):
            self.authors = other.authors
        
        # Use higher citation count
        if self.citation_count is None or (other.citation_count is not None and other.citation_count > (self.citation_count or 0)):
            self.citation_count = other.citation_count
            self.citation_source = other.citation_source
        
        # Merge keywords
        self.keywords.update(other.keywords)
        
        # Use longer comments if available
        if not self.comments or (other.comments and len(other.comments) > len(self.comments or "")):
            self.comments = other.comments
        
        # Use more pages if available
        if self.number_of_pages is None or (other.number_of_pages is not None and other.number_of_pages > (self.number_of_pages or 0)):
            self.number_of_pages = other.number_of_pages
        
        # Use longer page range if available
        if not self.pages or (other.pages and len(other.pages) > len(self.pages or "")):
            self.pages = other.pages
        
        # Merge URLs
        self.urls.update(other.urls)
        
        # Merge databases
        self.databases.update(other.databases)
        
        # Merge sources
        for source in other.sources:
            if source not in self.sources:
                self.sources.append(source)
        
        # Merge source IDs
        self.source_ids.update(other.source_ids)
        
        # Merge topics
        for topic in other.topics:
            if topic not in self.topics:
                self.topics.append(topic)
        
        # Merge categories
        for facet, categories_list in other.categories.items():
            if facet not in self.categories:
                self.categories[facet] = []
            for cat in categories_list:
                if cat not in self.categories[facet]:
                    self.categories[facet].append(cat)
        
        # Merge data quality flags
        for flag in other.data_quality_flags:
            if flag not in self.data_quality_flags:
                self.data_quality_flags.append(flag)
        
        # Merge OA status
        self.is_open_access = self.is_open_access or other.is_open_access
        
        # Merge survey flag
        self.is_survey = self.is_survey or other.is_survey


def merge_papers(papers: list[PaperResult]) -> list[MergedPaper]:
    """Deduplicate and merge papers from multiple sources.
    
    Algorithm (Canonical Work Clustering):
    1. Normalize all papers
    2. Compute work_key for each paper (doi > pmid > arxiv > s2 > title_hash)
    3. Group papers by work_key
    4. For title_hash groups, apply fuzzy matching to catch near-duplicates
    5. Select representative and merge each group
    """
    if not papers:
        return []
    
    # Normalize all papers first
    normalized = [normalize_paper(p) for p in papers]
    
    # Group by work_key (canonical clustering)
    work_key_groups: dict[str, list[PaperResult]] = {}
    
    for paper in normalized:
        key = compute_work_key(paper)
        if key not in work_key_groups:
            work_key_groups[key] = []
        work_key_groups[key].append(paper)
    
    logger.debug(f"Work key clustering: {len(normalized)} papers -> {len(work_key_groups)} clusters")
    
    # For title_hash groups, apply additional fuzzy matching to merge similar titles
    # This handles cases where the same paper has different title_hashes due to minor variations
    title_hash_groups = {k: v for k, v in work_key_groups.items() if k.startswith("title_hash:")}
    strong_id_groups = {k: v for k, v in work_key_groups.items() if not k.startswith("title_hash:")}
    
    # Process title_hash papers with fuzzy matching
    title_hash_papers = []
    for papers_list in title_hash_groups.values():
        title_hash_papers.extend(papers_list)
    
    # Fuzzy match title_hash papers
    assigned_indices = set()
    fuzzy_groups: list[list[PaperResult]] = []
    
    for i, paper in enumerate(title_hash_papers):
        if i in assigned_indices:
            continue
        
        group = [paper]
        assigned_indices.add(i)
        
        for j in range(i + 1, len(title_hash_papers)):
            if j in assigned_indices:
                continue
            
            other = title_hash_papers[j]
            if are_likely_same_paper(paper, other):
                group.append(other)
                assigned_indices.add(j)
        
        fuzzy_groups.append(group)
    
    # Merge each group
    merged_papers = []
    
    # Strong identifier groups (doi, pmid, arxiv, s2)
    for work_key, group in strong_id_groups.items():
        merged = _merge_group(group, work_key)
        merged_papers.append(merged)
    
    # Fuzzy-matched title groups
    for group in fuzzy_groups:
        # Use the first paper's work_key for the group
        work_key = compute_work_key(group[0])
        merged = _merge_group(group, work_key)
        merged_papers.append(merged)
    
    logger.debug(f"After first merge: {len(merged_papers)} unique papers")
    
    # Apply citation age sanity check (Option D)
    merged_papers = _apply_citation_age_sanity_check(merged_papers)
    
    # Apply safe post-merge dedup (Option C)
    merged_papers = _safe_post_merge_dedup(merged_papers)
    
    logger.debug(f"After all dedup: {len(merged_papers)} unique papers")
    
    return merged_papers


# Citation source priority (prefer cleaner sources)
CITATION_SOURCE_PRIORITY = {
    "semantic_scholar": 1,
    "openalex": 2,
    "crossref": 3,
    "pubmed": 4,
    "arxiv": 5,
}


def _is_valid_year(year: Optional[int]) -> bool:
    """Check if year is valid (not future, not too old)."""
    if year is None:
        return False
    current_year = datetime.now().year
    return 1800 <= year <= current_year


def _is_preferred_venue(venue: Optional[str], work_type: Optional[str]) -> bool:
    """Check if venue is preferred (journal/conference over book/ebook)."""
    if not venue:
        return False
    return work_type in (WORK_TYPE_JOURNAL, WORK_TYPE_CONFERENCE)


def _apply_citation_age_sanity_check(papers: list["MergedPaper"]) -> list["MergedPaper"]:
    """Apply citation age sanity check (Option D).
    
    Detects papers where citations are implausible given the year.
    For example, a paper with 6,000+ citations cannot be from 2025.
    
    If detected:
    - Flags the paper with 'implausible_citation_age'
    - Attempts to correct the year if possible
    - If uncorrectable, sets year to None (will be deprioritized)
    """
    current_year = datetime.now().year
    
    # Rough heuristic: minimum years needed to accumulate citations
    # These are conservative estimates
    CITATION_THRESHOLDS = [
        (10000, 5),   # 10K+ citations needs at least 5 years
        (5000, 4),    # 5K+ citations needs at least 4 years
        (2000, 3),    # 2K+ citations needs at least 3 years
        (500, 2),     # 500+ citations needs at least 2 years
    ]
    
    for paper in papers:
        if paper.citation_count is None or paper.year is None:
            continue
        
        paper_age = current_year - paper.year
        
        for threshold, min_years in CITATION_THRESHOLDS:
            if paper.citation_count >= threshold and paper_age < min_years:
                # Flag the implausible year
                if "implausible_citation_age" not in paper.data_quality_flags:
                    paper.data_quality_flags.append("implausible_citation_age")
                    logger.warning(
                        f"Implausible citation age: '{paper.title[:50]}...' "
                        f"has {paper.citation_count} citations but year={paper.year}"
                    )
                
                # Try to correct: if we have an arxiv_id, we can infer a better year
                year_corrected = False
                if paper.arxiv_id:
                    # arXiv IDs encode year: 1706.03762 -> 2017
                    try:
                        arxiv_year_prefix = paper.arxiv_id.split(".")[0]
                        if len(arxiv_year_prefix) == 4:
                            yy = int(arxiv_year_prefix[:2])
                            inferred_year = 2000 + yy if yy < 50 else 1900 + yy
                            if _is_valid_year(inferred_year):
                                logger.info(f"Correcting year from {paper.year} to {inferred_year} based on arXiv ID")
                                paper.year = inferred_year
                                paper.field_provenance["year"] = "arxiv_id_inference"
                                if "year_corrected" not in paper.data_quality_flags:
                                    paper.data_quality_flags.append("year_corrected")
                                year_corrected = True
                    except (ValueError, IndexError):
                        pass
                
                # If we couldn't correct the year, set it to None
                # This paper has bad metadata and should be deprioritized
                if not year_corrected:
                    logger.warning(f"Could not correct year for '{paper.title[:50]}...', setting to None")
                    paper.year = None
                    paper.data_quality_flags.append("year_uncorrectable")
                
                break  # Only apply first matching threshold
    
    return papers


def _safe_post_merge_dedup(papers: list["MergedPaper"]) -> list["MergedPaper"]:
    """Safe post-merge deduplication (Option C).
    
    After initial work_key clustering, catches near-duplicates that slipped through.
    Very strict conditions to avoid wrong merges:
    - Title similarity > 0.95
    - First author must match
    - One paper has strong ID (arXiv, DOI) that other lacks, OR one has bad year flag
    - Merge prefers the one with better metadata
    """
    if len(papers) < 2:
        return papers
    
    # Build list of papers with their index
    remaining = list(enumerate(papers))
    merged_indices = set()
    result = []
    
    for i, paper_a in remaining:
        if i in merged_indices:
            continue
        
        # Look for potential duplicates
        best_merge_candidate = None
        best_merge_score = 0
        
        for j, paper_b in remaining:
            if j <= i or j in merged_indices:
                continue
            
            # Check if they might be the same paper
            if not _is_safe_merge_candidate(paper_a, paper_b):
                continue
            
            # Calculate merge confidence
            merge_score = _calculate_merge_confidence(paper_a, paper_b)
            if merge_score > best_merge_score:
                best_merge_score = merge_score
                best_merge_candidate = (j, paper_b)
        
        if best_merge_candidate:
            j, paper_b = best_merge_candidate
            merged_indices.add(j)
            
            # Merge: prefer the paper with better metadata
            merged = _merge_merged_papers(paper_a, paper_b)
            result.append(merged)
            logger.info(f"Post-merge dedup: merged '{paper_a.title[:40]}...' from {paper_a.sources} and {paper_b.sources}")
        else:
            result.append(paper_a)
    
    return result


def _is_safe_merge_candidate(a: "MergedPaper", b: "MergedPaper") -> bool:
    """Check if two papers are safe merge candidates.
    
    Very strict conditions to avoid wrong merges.
    """
    # Title similarity must be very high
    t_sim = title_similarity(a.title, b.title)
    if t_sim < 0.92:  # Slightly more lenient for obvious duplicates
        return False
    
    # First author must match (if both have authors)
    if a.authors and b.authors:
        a_sim = author_similarity(
            type("FakePaper", (), {"authors": a.authors})(),  # Create minimal object
            type("FakePaper", (), {"authors": b.authors})(),
        )
        if a_sim < 0.4:  # At least some author overlap
            return False
    
    # Check for bad metadata flags
    a_has_bad_metadata = (
        "implausible_citation_age" in a.data_quality_flags or
        "year_uncorrectable" in a.data_quality_flags or
        "bad_year" in a.data_quality_flags
    )
    b_has_bad_metadata = (
        "implausible_citation_age" in b.data_quality_flags or
        "year_uncorrectable" in b.data_quality_flags or
        "bad_year" in b.data_quality_flags
    )
    
    # If one has bad metadata, definitely merge with the good one
    if a_has_bad_metadata or b_has_bad_metadata:
        return True
    
    # Check for strong IDs
    a_has_strong = bool(a.arxiv_id or a.doi)
    b_has_strong = bool(b.arxiv_id or b.doi)
    
    # Safe to merge if: one has strong ID and other doesn't
    if a_has_strong != b_has_strong:
        return True
    
    # Both have strong IDs - merge if same arXiv
    if a.arxiv_id and b.arxiv_id:
        return a.arxiv_id == b.arxiv_id
    
    # If title similarity is very high (>0.98) and citations differ by >10x, 
    # likely same paper with different metadata
    if t_sim > 0.98:
        a_cites = a.citation_count or 0
        b_cites = b.citation_count or 0
        if a_cites > 0 and b_cites > 0:
            ratio = max(a_cites, b_cites) / min(a_cites, b_cites)
            if ratio > 10:  # Very different citation counts suggests metadata issue
                return True
    
    return False


def _calculate_merge_confidence(a: "MergedPaper", b: "MergedPaper") -> float:
    """Calculate confidence that two papers should be merged."""
    score = 0.0
    
    # Title similarity
    t_sim = title_similarity(a.title, b.title)
    score += t_sim * 0.4
    
    # Same arXiv ID is very strong signal
    if a.arxiv_id and b.arxiv_id and a.arxiv_id == b.arxiv_id:
        score += 0.5
    
    # One has arXiv and other doesn't - likely same paper with different metadata
    if bool(a.arxiv_id) != bool(b.arxiv_id):
        score += 0.2
    
    # One has bad year/metadata flags
    a_has_bad = any(f in a.data_quality_flags for f in ["implausible_citation_age", "year_uncorrectable", "bad_year"])
    b_has_bad = any(f in b.data_quality_flags for f in ["implausible_citation_age", "year_uncorrectable", "bad_year"])
    if a_has_bad or b_has_bad:
        score += 0.3
    
    # Large citation count difference (>10x) suggests metadata issue
    a_cites = a.citation_count or 0
    b_cites = b.citation_count or 0
    if a_cites > 0 and b_cites > 0:
        ratio = max(a_cites, b_cites) / min(a_cites, b_cites)
        if ratio > 10:
            score += 0.2
    
    return score


def _merge_merged_papers(a: "MergedPaper", b: "MergedPaper") -> "MergedPaper":
    """Merge two MergedPaper objects, preferring better metadata."""
    # Prefer paper with better metadata (valid year, more citations, has arXiv)
    def score(p: "MergedPaper") -> int:
        s = 0
        
        # Strongly prefer valid year with no bad flags
        if _is_valid_year(p.year):
            s += 20
        
        # Penalize bad metadata flags heavily
        if "implausible_citation_age" in p.data_quality_flags:
            s -= 30
        if "year_uncorrectable" in p.data_quality_flags:
            s -= 30
        if "bad_year" in p.data_quality_flags:
            s -= 20
        
        # Prefer papers with arXiv ID (reliable identifier)
        if p.arxiv_id:
            s += 10
        
        # Prefer Semantic Scholar as source (usually cleaner metadata)
        if "semantic_scholar" in p.sources:
            s += 8
        
        # DOI is good
        if p.doi:
            s += 5
        
        # More citations is better (but capped to avoid bias)
        if p.citation_count:
            s += min(p.citation_count // 10000, 5)  # Max 5 points from citations
        
        # Abstract is useful
        if p.abstract:
            s += 2
        
        return s
    
    if score(a) >= score(b):
        primary, secondary = a, b
    else:
        primary, secondary = b, a
    
    # Start with primary, fill from secondary
    result = primary
    
    # Merge sources
    for src in secondary.sources:
        if src not in result.sources:
            result.sources.append(src)
    
    # Merge source_ids
    for src, sid in secondary.source_ids.items():
        if src not in result.source_ids:
            result.source_ids[src] = sid
    
    # Fill missing fields
    if not result.abstract and secondary.abstract:
        result.abstract = secondary.abstract
    if not result.arxiv_id and secondary.arxiv_id:
        result.arxiv_id = secondary.arxiv_id
    if not result.doi and secondary.doi:
        result.doi = secondary.doi
        result.doi_url = f"https://doi.org/{secondary.doi}"
    if not result.oa_url and secondary.oa_url:
        result.oa_url = secondary.oa_url
    
    # Take better year (non-flagged)
    if "implausible_citation_age" in result.data_quality_flags:
        if secondary.year and "implausible_citation_age" not in secondary.data_quality_flags:
            result.year = secondary.year
    
    # Take higher citation count (from better source)
    if secondary.citation_count and result.citation_count:
        if secondary.citation_count > result.citation_count:
            result.citation_count = secondary.citation_count
            result.citation_source = secondary.citation_source
    
    # Take best relevance score
    result.relevance_score = max(result.relevance_score, secondary.relevance_score)
    
    # Merge data quality flags
    for flag in secondary.data_quality_flags:
        if flag not in result.data_quality_flags:
            result.data_quality_flags.append(flag)
    
    return result


def _merge_group(papers: list[PaperResult], work_key: Optional[str] = None) -> MergedPaper:
    """Merge a group of duplicate papers into one.
    
    Uses improved representative selection and field-safe merge policy:
    - Representative scoring includes venue type (journal/conference preferred)
    - Citations use source priority (Semantic Scholar > OpenAlex), not max
    - Venue prefers journal/conference over book/ebook
    """
    if len(papers) == 1:
        merged = _paper_to_merged(papers[0])
        merged.work_key = work_key
        return merged
    
    # Sort by priority (highest first) - representative selection
    papers_sorted = sorted(papers, key=compute_representative_score, reverse=True)
    primary = papers_sorted[0]
    
    # Start with primary paper's data
    merged = _paper_to_merged(primary)
    merged.work_key = work_key
    
    # Track merge provenance
    provenance = {
        "title": primary.source,
        "year": primary.source if primary.year else None,
        "doi": primary.source if primary.doi else None,
        "citations": primary.source if primary.citation_count else None,
        "venue": primary.source if primary.venue else None,
    }
    merged.field_provenance = provenance.copy()
    
    # Find best citation source using priority (not just highest count)
    best_citation_source = None
    best_citation_priority = 999
    best_citation_count = None
    
    for paper in papers_sorted:
        if paper.citation_count is not None:
            priority = CITATION_SOURCE_PRIORITY.get(paper.source, 99)
            if priority < best_citation_priority:
                best_citation_priority = priority
                best_citation_source = paper.source
                best_citation_count = paper.citation_count
    
    if best_citation_count is not None:
        merged.citation_count = best_citation_count
        merged.citation_source = best_citation_source
        provenance["citations"] = best_citation_source
    
    # Find best venue (prefer journal/conference over book/ebook)
    best_venue = merged.venue
    best_venue_source = primary.source
    
    for paper in papers_sorted:
        if paper.venue and _is_preferred_venue(paper.venue, paper.work_type):
            if not _is_preferred_venue(best_venue, merged.work_type):
                best_venue = paper.venue
                best_venue_source = paper.source
                merged.work_type = paper.work_type
                break
    
    if best_venue:
        merged.venue = best_venue
        provenance["venue"] = best_venue_source
    
    # Merge in data from other sources
    for paper in papers_sorted[1:]:
        # Track source
        merged.sources.append(paper.source)
        if paper.source_id:
            merged.source_ids[paper.source] = paper.source_id
        
        # Merge data quality flags
        for flag in (paper.data_quality_flags or []):
            if flag not in merged.data_quality_flags:
                merged.data_quality_flags.append(flag)
        
        # Fill in missing fields from this source
        if not merged.abstract and paper.abstract:
            merged.abstract = paper.abstract
        
        if not merged.oa_url and paper.oa_url:
            merged.oa_url = paper.oa_url
        
        if not merged.publisher_url and paper.publisher_url:
            merged.publisher_url = paper.publisher_url
        
        if not merged.doi and paper.doi:
            merged.doi = paper.doi
            merged.doi_url = f"https://doi.org/{paper.doi}"
            provenance["doi"] = paper.source
        
        # Year merge with protection: only accept valid years, never overwrite good with bad
        if paper.year:
            paper_year_valid = _is_valid_year(paper.year)
            merged_year_valid = _is_valid_year(merged.year)
            
            if not merged.year and paper_year_valid:
                # Fill missing year with valid year
                merged.year = paper.year
                provenance["year"] = paper.source
            elif merged.year and not merged_year_valid and paper_year_valid:
                # Replace invalid year with valid year
                merged.year = paper.year
                provenance["year"] = paper.source
                logger.debug(f"Replaced invalid year with {paper.year} from {paper.source}")
        
        # Merge topics
        for topic in paper.topics:
            if topic not in merged.topics:
                merged.topics.append(topic)
        
        # Merge keywords (if available)
        if hasattr(paper, 'keywords') and paper.keywords:
            if isinstance(paper.keywords, (list, set)):
                merged.keywords.update(paper.keywords)
            else:
                merged.keywords.add(paper.keywords)
        
        # Merge comments (use longer if available)
        if hasattr(paper, 'comments') and paper.comments:
            if not merged.comments or len(paper.comments) > len(merged.comments or ""):
                merged.comments = paper.comments
        
        # Merge pages (use more pages if available)
        if hasattr(paper, 'number_of_pages') and paper.number_of_pages:
            if not merged.number_of_pages or paper.number_of_pages > merged.number_of_pages:
                merged.number_of_pages = paper.number_of_pages
        
        if hasattr(paper, 'pages') and paper.pages:
            if not merged.pages or len(paper.pages) > len(merged.pages or ""):
                merged.pages = paper.pages
        
        # Merge categories (if available)
        if hasattr(paper, 'categories') and paper.categories:
            if isinstance(paper.categories, dict):
                for facet, categories_list in paper.categories.items():
                    if facet not in merged.categories:
                        merged.categories[facet] = []
                    if isinstance(categories_list, list):
                        for cat in categories_list:
                            if cat not in merged.categories[facet]:
                                merged.categories[facet].append(cat)
        
        # Merge databases
        if hasattr(paper, 'databases') and paper.databases:
            if isinstance(paper.databases, (list, set)):
                merged.databases.update(paper.databases)
            else:
                merged.databases.add(paper.databases)
        else:
            # Default to source name
            merged.databases.add(paper.source)
        
        # Merge URLs
        if paper.oa_url:
            merged.urls.add(paper.oa_url)
        if paper.publisher_url:
            merged.urls.add(paper.publisher_url)
        if paper.doi and not merged.doi_url:
            merged.doi_url = f"https://doi.org/{paper.doi}"
            merged.urls.add(merged.doi_url)
        
        # Merge OA status
        merged.is_open_access = merged.is_open_access or paper.is_open_access
        
        # Keep survey flag if any source says it's a survey
        merged.is_survey = merged.is_survey or paper.is_survey
        
        # Take best relevance score
        if paper.relevance_score is not None:
            if merged.relevance_score == 0.0:
                merged.relevance_score = paper.relevance_score
            else:
                merged.relevance_score = max(merged.relevance_score, paper.relevance_score)
        
        # Merge arXiv ID (propagate from any source)
        if not merged.arxiv_id and paper.arxiv_id:
            merged.arxiv_id = paper.arxiv_id
        
        # Merge PMID (propagate from any source)
        if not merged.pmid and paper.pmid:
            merged.pmid = paper.pmid
    
    # Store final provenance
    merged.field_provenance = provenance
    
    # Log merge provenance for debugging
    logger.debug(f"Merged '{merged.title[:50]}...' from {len(papers)} sources: {provenance}")
    
    # Limit topics
    merged.topics = merged.topics[:10]
    
    return merged


def compute_representative_score(paper: PaperResult) -> int:
    """Compute representative score for selecting best record from cluster.
    
    Scoring (per user spec):
    +4 if has DOI
    +3 if venue_type is journal/conference (not book/ebook)
    +2 if has abstract
    +2 if has publisher/DOI URL
    +1 if has citation_count
    +source_bonus
    """
    score = 0
    
    # +4 for DOI
    if paper.doi:
        score += 4
    
    # +3 for journal/conference venue type
    if paper.work_type in (WORK_TYPE_JOURNAL, WORK_TYPE_CONFERENCE):
        score += 3
    
    # +2 for abstract
    if paper.abstract:
        score += 2
    
    # +2 for publisher URL or DOI URL
    if paper.publisher_url:
        score += 2
    
    # +1 for citation count
    if paper.citation_count is not None:
        score += 1
    
    # Source bonus (Semantic Scholar > OpenAlex > PubMed > Crossref > arXiv)
    source_bonus = {
        "semantic_scholar": 5,
        "openalex": 4,
        "pubmed": 3,
        "crossref": 2,
        "arxiv": 1,
    }
    score += source_bonus.get(paper.source, 0)
    
    return score


def _paper_to_merged(paper: PaperResult) -> MergedPaper:
    """Convert a PaperResult to a MergedPaper."""
    doi_url = None
    if paper.doi:
        doi_url = f"https://doi.org/{paper.doi}"
    
    source_ids = {}
    if paper.source_id:
        source_ids[paper.source] = paper.source_id
    
    # Collect URLs
    urls = set()
    if paper.oa_url:
        urls.add(paper.oa_url)
    if paper.publisher_url:
        urls.add(paper.publisher_url)
    if doi_url:
        urls.add(doi_url)
    
    # Extract publication date from year if available
    publication_date = None
    if hasattr(paper, 'publication_date') and paper.publication_date:
        publication_date = paper.publication_date
    elif paper.year:
        # Create a date from year (use Jan 1 as default)
        try:
            publication_date = date(paper.year, 1, 1)
        except ValueError:
            pass
    
    # Extract keywords if available
    keywords = set()
    if hasattr(paper, 'keywords') and paper.keywords:
        if isinstance(paper.keywords, (list, set)):
            keywords = set(paper.keywords)
        else:
            keywords = {paper.keywords}
    
    # Extract pages if available
    number_of_pages = None
    pages = None
    if hasattr(paper, 'number_of_pages'):
        number_of_pages = paper.number_of_pages
    if hasattr(paper, 'pages'):
        pages = paper.pages
    
    # Extract comments if available
    comments = None
    if hasattr(paper, 'comments'):
        comments = paper.comments
    
    # Extract categories if available
    categories = {}
    if hasattr(paper, 'categories') and paper.categories:
        if isinstance(paper.categories, dict):
            categories = paper.categories
    
    # Extract databases if available
    databases = set()
    if hasattr(paper, 'databases') and paper.databases:
        if isinstance(paper.databases, (list, set)):
            databases = set(paper.databases)
    else:
        # Default to source name
        databases = {paper.source}
    
    return MergedPaper(
        id=str(uuid.uuid4()),
        doi=paper.doi,
        title=paper.title,
        abstract=paper.abstract,
        year=paper.year,
        publication_date=publication_date,
        venue=paper.venue,
        authors=paper.authors.copy() if paper.authors else [],
        citation_count=paper.citation_count,
        citation_source=paper.source if paper.citation_count else None,
        oa_url=paper.oa_url,
        publisher_url=paper.publisher_url,
        doi_url=doi_url,
        urls=urls,
        topics=paper.topics.copy() if paper.topics else [],
        keywords=keywords,
        comments=comments,
        number_of_pages=number_of_pages,
        pages=pages,
        selected=False,  # Default to False, user will set this
        categories=categories,
        databases=databases,
        is_survey=paper.is_survey,
        is_open_access=paper.is_open_access,
        arxiv_id=paper.arxiv_id,
        pmid=paper.pmid,
        work_type=paper.work_type,
        source_ids=source_ids,
        sources=[paper.source],
        data_quality_flags=paper.data_quality_flags.copy() if paper.data_quality_flags else [],
        relevance_score=paper.relevance_score or 0.0,
    )

