"""Normalization utilities for paper metadata."""

import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Optional

from app.adapters.base import PaperResult, Author


# Work type constants
WORK_TYPE_JOURNAL = "journal"
WORK_TYPE_CONFERENCE = "conference"
WORK_TYPE_BOOK = "book"
WORK_TYPE_CHAPTER = "chapter"
WORK_TYPE_PREPRINT = "preprint"
WORK_TYPE_SURVEY = "survey"
WORK_TYPE_UNKNOWN = "unknown"


def normalize_title(title: str) -> str:
    """Normalize title for comparison.
    
    - Lowercase
    - Remove extra whitespace
    - Remove common prefixes/suffixes
    - Unicode normalization
    """
    if not title:
        return ""
    
    # Unicode normalization (NFKD for compatibility)
    title = unicodedata.normalize("NFKD", title)
    
    # Lowercase
    title = title.lower()
    
    # Remove HTML tags
    title = re.sub(r"<[^>]+>", "", title)
    
    # Normalize whitespace
    title = re.sub(r"\s+", " ", title).strip()
    
    # Remove common prefixes
    prefixes = ["a ", "an ", "the ", "on ", "re: ", "re:", "fwd: ", "fwd:"]
    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[len(prefix):]
    
    # Remove trailing punctuation
    title = title.rstrip(".")
    
    return title


def normalize_author_name(name: str) -> str:
    """Normalize author name for comparison.
    
    - Unicode normalization
    - Remove extra whitespace
    - Handle initials
    """
    if not name:
        return ""
    
    # Unicode normalization
    name = unicodedata.normalize("NFKD", name)
    
    # Remove accents (optional - may want to keep them)
    name = "".join(c for c in name if not unicodedata.combining(c))
    
    # Lowercase
    name = name.lower()
    
    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()
    
    # Remove punctuation except periods (for initials)
    name = re.sub(r"[,;:'\"]", "", name)
    
    return name


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Normalize DOI to standard format.
    
    Returns DOI without any URL prefix, or None if invalid.
    """
    if not doi:
        return None
    
    doi = doi.strip()
    
    # Remove URL prefixes
    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "doi.org/",
        "doi:",
        "DOI:",
    ]
    
    for prefix in prefixes:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    
    # Basic DOI validation (starts with 10.)
    if not doi.startswith("10."):
        return None
    
    return doi


def normalize_year(year: Optional[int]) -> Optional[int]:
    """Validate and normalize publication year."""
    if year is None:
        return None
    
    current_year = datetime.now().year
    
    # Sanity check: not before 1800 and not in the future
    if year < 1800 or year > current_year:
        return None
    
    return year


def compute_work_key(paper: PaperResult) -> str:
    """Compute a stable work_key for clustering papers.
    
    Priority order (strongest first):
    1. doi:<normalized_doi> (but skip suspicious DOIs)
    2. arxiv:<arxiv_id> (from any source)
    3. pmid:<pmid> (from any source)
    4. s2:<semantic_scholar_paperId>
    5. fallback: title_hash:<normalized_title + first_author_last + year_bucket>
    """
    # Check DOI first (strongest identifier)
    # But skip suspicious DOIs that might be data errors
    if paper.doi:
        doi_lower = paper.doi.lower()
        # Skip suspicious DOI prefixes (known to have data quality issues)
        suspicious_prefixes = ["10.65215/"]  # Known problematic registrant
        is_suspicious = any(doi_lower.startswith(prefix) for prefix in suspicious_prefixes)
        if not is_suspicious:
            return f"doi:{doi_lower}"
    
    # Check arXiv ID from ANY source (key improvement!)
    arxiv_id = paper.arxiv_id
    if arxiv_id:
        # Normalize arXiv ID (remove version suffix like "v1", "v2")
        normalized_arxiv = arxiv_id.rsplit("v", 1)[0] if "v" in arxiv_id else arxiv_id
        return f"arxiv:{normalized_arxiv}"
    
    # For arxiv source, check source_id
    if paper.source == "arxiv" and paper.source_id:
        arxiv_id = paper.source_id.rsplit("v", 1)[0] if "v" in paper.source_id else paper.source_id
        return f"arxiv:{arxiv_id}"
    
    # Check PMID from any source
    if paper.pmid:
        return f"pmid:{paper.pmid}"
    
    # For pubmed source, check source_id
    if paper.source == "pubmed" and paper.source_id:
        return f"pmid:{paper.source_id}"
    
    # Semantic Scholar ID as fallback
    if paper.source == "semantic_scholar" and paper.source_id:
        return f"s2:{paper.source_id}"
    
    # Fallback: title hash with author and year bucket
    norm_title = normalize_title(paper.title)
    first_author = extract_first_author_lastname(paper.authors) or "unknown"
    year_bucket = str(paper.year) if paper.year else "unknown"
    
    # Create hash of title + author + year for fallback key
    key_content = f"{norm_title}|{first_author}|{year_bucket}"
    key_hash = hashlib.sha256(key_content.encode()).hexdigest()[:16]
    
    return f"title_hash:{key_hash}"


def detect_work_type(paper: PaperResult) -> str:
    """Classify the work type of a paper.
    
    Returns one of: survey, book, chapter, preprint, journal, conference, unknown
    """
    title_lower = paper.title.lower() if paper.title else ""
    venue_lower = paper.venue.lower() if paper.venue else ""
    
    # Check for survey/review first (most specific)
    survey_keywords = [
        "survey", "review", "overview", "tutorial",
        "state of the art", "state-of-the-art",
        "systematic review", "meta-analysis", "literature review",
    ]
    for keyword in survey_keywords:
        if keyword in title_lower:
            return WORK_TYPE_SURVEY
    
    if paper.is_survey:
        return WORK_TYPE_SURVEY
    
    # Check for book/chapter
    book_keywords = [
        "handbook", "press", "chapter", "ebook", "e-book",
        "isbn", "springer book", "edition", "textbook",
        "cambridge university press", "oxford university press",
        "wiley", "elsevier book", "academic press",
    ]
    for keyword in book_keywords:
        if keyword in title_lower or keyword in venue_lower:
            if "chapter" in title_lower or "chapter" in venue_lower:
                return WORK_TYPE_CHAPTER
            return WORK_TYPE_BOOK
    
    # Check for preprint
    if paper.source == "arxiv":
        return WORK_TYPE_PREPRINT
    if "arxiv" in venue_lower:
        return WORK_TYPE_PREPRINT
    if "preprint" in venue_lower or "preprint" in title_lower:
        return WORK_TYPE_PREPRINT
    
    # Check for conference
    conference_keywords = [
        "proceedings", "conference", "symposium", "workshop",
        "icml", "neurips", "nips", "iclr", "cvpr", "iccv",
        "eccv", "acl", "emnlp", "naacl", "aaai", "ijcai",
        "sigkdd", "www", "chi", "sigir", "wsdm",
    ]
    for keyword in conference_keywords:
        if keyword in venue_lower:
            return WORK_TYPE_CONFERENCE
    
    # Check for journal
    journal_keywords = [
        "journal", "transactions", "letters", "magazine",
        "nature", "science", "cell", "lancet", "nejm",
        "jama", "plos", "bmc", "frontiers",
    ]
    for keyword in journal_keywords:
        if keyword in venue_lower:
            return WORK_TYPE_JOURNAL
    
    # If venue exists but not matched, assume journal
    if paper.venue:
        return WORK_TYPE_JOURNAL
    
    return WORK_TYPE_UNKNOWN


def normalize_venue(venue: Optional[str]) -> Optional[str]:
    """Normalize venue/journal name."""
    if not venue:
        return None
    
    venue = venue.strip()
    
    # Remove common suffixes
    suffixes = [
        " (Online)",
        " (Print)",
        " - Online",
        " - Print",
    ]
    
    for suffix in suffixes:
        if venue.endswith(suffix):
            venue = venue[:-len(suffix)]
    
    # Normalize whitespace
    venue = re.sub(r"\s+", " ", venue).strip()
    
    return venue if venue else None


def extract_first_author_lastname(authors: list[Author]) -> Optional[str]:
    """Extract normalized last name of first author."""
    if not authors:
        return None
    
    name = authors[0].name
    if not name:
        return None
    
    # Normalize
    name = normalize_author_name(name)
    
    # Try to extract last name (last word, or word before comma if present)
    if "," in name:
        # Format: "Last, First"
        parts = name.split(",")
        return parts[0].strip()
    else:
        # Format: "First Last" or "First M. Last"
        parts = name.split()
        if parts:
            return parts[-1]
    
    return None


def detect_survey(paper: PaperResult) -> bool:
    """Detect if paper is likely a survey/review."""
    if paper.is_survey:
        return True
    
    # Check title
    title_lower = paper.title.lower()
    survey_keywords = [
        "survey",
        "review",
        "overview",
        "tutorial",
        "state of the art",
        "state-of-the-art",
        "comprehensive study",
        "systematic review",
        "meta-analysis",
        "literature review",
    ]
    
    for keyword in survey_keywords:
        if keyword in title_lower:
            return True
    
    return False


def normalize_paper(paper: PaperResult) -> PaperResult:
    """Apply all normalizations to a paper result."""
    work_type = detect_work_type(paper)
    is_survey = work_type == WORK_TYPE_SURVEY or detect_survey(paper)
    
    # Normalize arXiv ID (remove version suffix)
    arxiv_id = paper.arxiv_id
    if arxiv_id and "v" in arxiv_id:
        arxiv_id = arxiv_id.rsplit("v", 1)[0]
    
    return PaperResult(
        title=paper.title,  # Keep original for display
        source=paper.source,
        doi=normalize_doi(paper.doi),
        source_id=paper.source_id,
        arxiv_id=arxiv_id,
        pmid=paper.pmid,
        abstract=paper.abstract,
        year=normalize_year(paper.year),
        venue=normalize_venue(paper.venue),
        authors=paper.authors,
        citation_count=paper.citation_count,
        oa_url=paper.oa_url,
        publisher_url=paper.publisher_url,
        topics=paper.topics,
        is_survey=is_survey,
        is_open_access=paper.is_open_access,
        work_type=work_type,
        relevance_score=paper.relevance_score,
        data_quality_flags=paper.data_quality_flags.copy() if paper.data_quality_flags else [],
    )

