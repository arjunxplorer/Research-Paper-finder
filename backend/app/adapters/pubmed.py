"""PubMed API adapter using NCBI E-utilities."""

from typing import Optional
import xml.etree.ElementTree as ET
import httpx

from app.adapters.base import BaseAdapter, PaperResult, Author, validate_year


class PubMedAdapter(BaseAdapter):
    """Adapter for PubMed/NCBI E-utilities API."""
    
    source_name = "pubmed"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self, email: str = "user@example.com"):
        super().__init__()
        self.email = email  # Required by NCBI
    
    def _get_params(self) -> dict:
        """Get base params for E-utilities."""
        return {
            "email": self.email,
            "tool": "BestPapersFinder",
        }
    
    def _parse_article(self, article: ET.Element) -> Optional[PaperResult]:
        """Parse PubMed article XML into PaperResult."""
        try:
            medline_citation = article.find("MedlineCitation")
            if medline_citation is None:
                return None
            
            pmid_elem = medline_citation.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            article_elem = medline_citation.find("Article")
            if article_elem is None:
                return None
            
            # Title
            title_elem = article_elem.find("ArticleTitle")
            title = title_elem.text if title_elem is not None else ""
            if not title:
                return None
            
            # Abstract
            abstract = None
            abstract_elem = article_elem.find("Abstract")
            if abstract_elem is not None:
                abstract_texts = []
                for text_elem in abstract_elem.findall("AbstractText"):
                    if text_elem.text:
                        label = text_elem.get("Label", "")
                        if label:
                            abstract_texts.append(f"{label}: {text_elem.text}")
                        else:
                            abstract_texts.append(text_elem.text)
                abstract = " ".join(abstract_texts)
            
            # Authors
            authors = []
            author_list = article_elem.find("AuthorList")
            if author_list is not None:
                for author_elem in author_list.findall("Author"):
                    name_parts = []
                    fore_name = author_elem.find("ForeName")
                    last_name = author_elem.find("LastName")
                    if fore_name is not None and fore_name.text:
                        name_parts.append(fore_name.text)
                    if last_name is not None and last_name.text:
                        name_parts.append(last_name.text)
                    if name_parts:
                        # Get affiliations
                        affiliations = []
                        for aff in author_elem.findall("AffiliationInfo/Affiliation"):
                            if aff.text:
                                affiliations.append(aff.text)
                        authors.append(Author(
                            name=" ".join(name_parts),
                            affiliations=affiliations,
                        ))
            
            # Year
            year = None
            journal = article_elem.find("Journal")
            if journal is not None:
                pub_date = journal.find("JournalIssue/PubDate")
                if pub_date is not None:
                    year_elem = pub_date.find("Year")
                    if year_elem is not None and year_elem.text:
                        year = int(year_elem.text)
            
            # Venue (journal title)
            venue = None
            if journal is not None:
                title_elem = journal.find("Title")
                if title_elem is not None:
                    venue = title_elem.text
            
            # DOI
            doi = None
            pubmed_data = article.find("PubmedData")
            if pubmed_data is not None:
                for article_id in pubmed_data.findall("ArticleIdList/ArticleId"):
                    if article_id.get("IdType") == "doi":
                        doi = article_id.text
                        break
            
            # Check if review
            is_survey = False
            pub_type_list = article_elem.find("PublicationTypeList")
            if pub_type_list is not None:
                for pub_type in pub_type_list.findall("PublicationType"):
                    if pub_type.text and "review" in pub_type.text.lower():
                        is_survey = True
                        break
            
            # Validate year
            validated_year, year_flags = validate_year(year)
            
            return PaperResult(
                title=title,
                source=self.source_name,
                doi=doi,
                source_id=pmid,
                pmid=pmid,  # Set explicit pmid field
                abstract=abstract,
                year=validated_year,
                venue=venue,
                authors=authors,
                is_survey=is_survey,
                publisher_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
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
        """Search PubMed for articles."""
        # Step 1: Search for PMIDs
        search_url = f"{self.base_url}/esearch.fcgi"
        
        # Build query with date filters
        search_query = query
        if year_min or year_max:
            date_range = f"{year_min or 1900}:{year_max or 2100}[dp]"
            search_query = f"({query}) AND {date_range}"
        
        search_params = {
            **self._get_params(),
            "db": "pubmed",
            "term": search_query,
            "retmax": min(limit, 100),
            "retmode": "json",
            "sort": "relevance",
        }
        
        try:
            search_response = await self._make_request(
                "GET",
                search_url,
                params=search_params,
            )
            search_data = search_response.json()
            
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []
            
            # Step 2: Fetch article details
            fetch_url = f"{self.base_url}/efetch.fcgi"
            fetch_params = {
                **self._get_params(),
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "xml",
            }
            
            fetch_response = await self._make_request(
                "GET",
                fetch_url,
                params=fetch_params,
            )
            
            # Parse XML
            root = ET.fromstring(fetch_response.text)
            
            all_articles = list(root.findall("PubmedArticle"))
            total = len(all_articles)
            
            papers = []
            for idx, article in enumerate(all_articles):
                paper = self._parse_article(article)
                if paper:
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
        """Get an article by PMID."""
        url = f"{self.base_url}/efetch.fcgi"
        
        params = {
            **self._get_params(),
            "db": "pubmed",
            "id": paper_id,
            "retmode": "xml",
        }
        
        try:
            response = await self._make_request(
                "GET",
                url,
                params=params,
            )
            
            root = ET.fromstring(response.text)
            article = root.find("PubmedArticle")
            
            if article is not None:
                return self._parse_article(article)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except ET.ParseError:
            return None

