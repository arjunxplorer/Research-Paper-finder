"""SQLAlchemy database models."""

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, Date, Float, Boolean, JSON, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Publication(Base):
    """Publication (journal, conference proceedings, book) model."""
    
    __tablename__ = "publication"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    issn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    publisher: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Category: "Journal", "Conference Proceedings", "Book"
    cite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sjr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # SCImago Journal Rank
    snip: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Source Normalized Impact per Paper
    subject_areas_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: list of subject area strings
    is_potentially_predatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Relationships
    papers: Mapped[list["Paper"]] = relationship("Paper", back_populates="publication")
    
    __table_args__ = (
        Index("ix_publication_issn", "issn"),
        Index("ix_publication_isbn", "isbn"),
        Index("ix_publication_category", "category"),
    )
    
    def to_dict(self) -> dict:
        """Convert publication to dictionary for API response."""
        return {
            "id": self.id,
            "title": self.title,
            "isbn": self.isbn,
            "issn": self.issn,
            "publisher": self.publisher,
            "category": self.category,
            "citeScore": self.cite_score,
            "sjr": self.sjr,
            "snip": self.snip,
            "subjectAreas": self.subject_areas_json or [],
            "isPotentiallyPredatory": self.is_potentially_predatory,
        }


class Paper(Base):
    """Paper metadata model."""
    
    __tablename__ = "paper"
    
    # Use String for UUID to be compatible with both PostgreSQL and SQLite
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    doi: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # Keep year for backward compatibility, but prefer publication_date
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    venue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    source_ids_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: {openalex_id, s2_paperId, pmid, arxiv_id, crossref_id}
    citation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    citation_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., "semantic_scholar", "openalex", "crossref"
    oa_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publisher_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    urls_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: list of URLs from different databases
    topics_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    keywords_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: list of keyword strings (author-provided)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    # User comments/notes on the paper
    number_of_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pages: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Page range (e.g., "123-145")
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # User selection/bookmark flag
    categories_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: dict of facet -> list of categories
    databases_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: list of database names where paper was found
    data_quality_flags_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: ["bad_year", "missing_doi", etc.]
    
    # Foreign key to Publication
    publication_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("publication.id"),
        nullable=True,
        index=True,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Relationships
    publication: Mapped[Optional["Publication"]] = relationship("Publication", back_populates="papers")
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_paper_citation_count", "citation_count"),
        Index("ix_paper_year_citations", "year", "citation_count"),
        Index("ix_paper_publication_date", "publication_date"),
        Index("ix_paper_selected", "selected"),
        Index("ix_paper_comments", "comments"),  # For querying papers with notes
    )
    
    def add_url(self, url: str) -> None:
        """Add a URL to the paper's URL set."""
        urls = set(self.urls_json or [])
        urls.add(url)
        self.urls_json = list(urls)
    
    def add_database(self, database_name: str) -> None:
        """Add a database name where the paper was found."""
        # Valid database names
        valid_databases = {"semantic_scholar", "openalex", "pubmed", "arxiv", "crossref"}
        if database_name not in valid_databases:
            raise ValueError(
                f"Invalid database name '{database_name}'. Valid databases: {', '.join(valid_databases)}"
            )
        databases = set(self.databases_json or [])
        databases.add(database_name)
        self.databases_json = list(databases)
    
    def get_citation_key(self) -> str:
        """Generate citation key following pattern <FIRST_AUTHOR><YEAR><TITLE_FIRST_WORD>."""
        import re
        
        # Extract first author last name
        authors = self.authors_json or []
        author_key = "unknown"
        if authors:
            first_author = authors[0] if isinstance(authors[0], str) else authors[0].get("name", "")
            if isinstance(first_author, dict):
                first_author = first_author.get("name", "")
            # Extract last name (before comma or last word)
            if "," in first_author:
                author_key = first_author.split(",")[0].strip().lower().replace(" ", "")
            else:
                parts = first_author.split()
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
    
    def has_category_match(self, categories: dict) -> bool:
        """Check if paper matches provided category facets."""
        if not categories or not self.categories_json:
            return False
        
        paper_categories = self.categories_json or {}
        for facet, facet_categories in categories.items():
            for facet_category in facet_categories:
                if facet_category in paper_categories.get(facet, []):
                    return True
        return False
    
    def to_dict(self) -> dict:
        """Convert paper to dictionary for API response."""
        return {
            "id": self.id,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "year": self.year,
            "publicationDate": self.publication_date.isoformat() if self.publication_date else None,
            "venue": self.venue,
            "authors": self.authors_json or [],
            "citationCount": self.citation_count,
            "citationSource": self.citation_source,
            "oaUrl": self.oa_url,
            "publisherUrl": self.publisher_url,
            "doiUrl": self.doi_url,
            "urls": self.urls_json or [],
            "topics": self.topics_json or [],
            "keywords": self.keywords_json or [],
            "comments": self.comments,
            "numberOfPages": self.number_of_pages,
            "pages": self.pages,
            "selected": self.selected,
            "categories": self.categories_json or {},
            "databases": self.databases_json or [],
            "dataQualityFlags": self.data_quality_flags_json or [],
            "publication": self.publication.to_dict() if self.publication else None,
            "citationKey": self.get_citation_key(),
        }


class SearchCache(Base):
    """Cached search results."""
    
    __tablename__ = "search_cache"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    # "foundational" or "recent"
    filters_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    result_paper_ids_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    __table_args__ = (
        Index("ix_search_cache_query_mode", "query_text", "mode"),
        Index("ix_search_cache_expires", "expires_at"),
    )


class RequestLog(Base):
    """Request logging for analytics."""
    
    __tablename__ = "request_log"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    filters_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    source_stats_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    # Structure: {source_name: {count: int, errors: int, latency_ms: int}}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_request_log_created", "created_at"),
    )
