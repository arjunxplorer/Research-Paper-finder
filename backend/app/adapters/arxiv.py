"""arXiv API adapter."""

from typing import Optional
import xml.etree.ElementTree as ET
import re
import httpx

from app.adapters.base import BaseAdapter, PaperResult, Author, validate_year


class ArxivAdapter(BaseAdapter):
    """Adapter for arXiv API."""
    
    source_name = "arxiv"
    base_url = "http://export.arxiv.org/api"
    
    # XML namespaces
    ATOM_NS = "{http://www.w3.org/2005/Atom}"
    ARXIV_NS = "{http://arxiv.org/schemas/atom}"
    
    def _parse_entry(self, entry: ET.Element) -> Optional[PaperResult]:
        """Parse arXiv entry XML into PaperResult."""
        try:
            # Title
            title_elem = entry.find(f"{self.ATOM_NS}title")
            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
            if not title:
                return None
            
            # arXiv ID
            id_elem = entry.find(f"{self.ATOM_NS}id")
            arxiv_url = id_elem.text if id_elem is not None else ""
            arxiv_id = arxiv_url.split("/abs/")[-1] if arxiv_url else None
            # Remove version number for canonical ID
            if arxiv_id and "v" in arxiv_id:
                arxiv_id = arxiv_id.rsplit("v", 1)[0]
            
            # Abstract
            summary_elem = entry.find(f"{self.ATOM_NS}summary")
            abstract = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else None
            
            # Authors
            authors = []
            for author_elem in entry.findall(f"{self.ATOM_NS}author"):
                name_elem = author_elem.find(f"{self.ATOM_NS}name")
                if name_elem is not None and name_elem.text:
                    affiliation_elem = author_elem.find(f"{self.ARXIV_NS}affiliation")
                    affiliations = []
                    if affiliation_elem is not None and affiliation_elem.text:
                        affiliations.append(affiliation_elem.text)
                    authors.append(Author(
                        name=name_elem.text,
                        affiliations=affiliations,
                    ))
            
            # Published date
            year = None
            published_elem = entry.find(f"{self.ATOM_NS}published")
            if published_elem is not None and published_elem.text:
                # Format: 2023-01-15T12:00:00Z
                match = re.match(r"(\d{4})-", published_elem.text)
                if match:
                    year = int(match.group(1))
            
            # Categories (topics)
            topics = []
            for category in entry.findall(f"{self.ATOM_NS}category"):
                term = category.get("term")
                if term:
                    topics.append(term)
            
            # Primary category as venue
            primary_category = entry.find(f"{self.ARXIV_NS}primary_category")
            venue = f"arXiv {primary_category.get('term')}" if primary_category is not None else "arXiv"
            
            # DOI if available
            doi_elem = entry.find(f"{self.ARXIV_NS}doi")
            doi = doi_elem.text if doi_elem is not None else None
            
            # Validate year
            validated_year, year_flags = validate_year(year)
            
            # PDF link
            pdf_url = None
            for link in entry.findall(f"{self.ATOM_NS}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                    break
            
            return PaperResult(
                title=title,
                source=self.source_name,
                doi=doi,
                source_id=arxiv_id,
                arxiv_id=arxiv_id,  # Set explicit arxiv_id field
                abstract=abstract,
                year=validated_year,
                venue=venue,
                authors=authors,
                oa_url=pdf_url,
                publisher_url=arxiv_url,
                topics=topics,
                is_open_access=True,  # All arXiv papers are OA
                data_quality_flags=year_flags,
            )
            
        except Exception:
            return None
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[PaperResult]:
        """Search arXiv for papers."""
        url = f"{self.base_url}/query"
        
        # Build search query
        # arXiv uses prefix: notation (ti, au, abs, all, etc.)
        search_query = f"all:{query}"
        
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(limit, 100),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
            )
            
            # Parse XML
            root = ET.fromstring(response.text)
            
            # First pass: parse all entries
            all_entries = list(root.findall(f"{self.ATOM_NS}entry"))
            total = len(all_entries)
            
            papers = []
            for idx, entry in enumerate(all_entries):
                paper = self._parse_entry(entry)
                if paper:
                    # Apply year filter (arXiv doesn't support date filtering in API)
                    if year_min and paper.year and paper.year < year_min:
                        continue
                    if year_max and paper.year and paper.year > year_max:
                        continue
                    # Assign position-based relevance score (1.0 for first, declining)
                    paper.relevance_score = 1.0 - (idx / max(total, 1)) * 0.5
                    papers.append(paper)
            
            return papers
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return []
            raise
        except ET.ParseError:
            return []
    
    async def get_paper(self, paper_id: str) -> Optional[PaperResult]:
        """Get a paper by arXiv ID."""
        url = f"{self.base_url}/query"
        
        # Clean arXiv ID
        arxiv_id = paper_id.replace("arXiv:", "").replace("arxiv:", "")
        
        params = {
            "id_list": arxiv_id,
            "max_results": 1,
        }
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
            )
            
            root = ET.fromstring(response.text)
            entry = root.find(f"{self.ATOM_NS}entry")
            
            if entry is not None:
                return self._parse_entry(entry)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except ET.ParseError:
            return None

