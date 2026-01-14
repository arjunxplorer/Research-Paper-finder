/**
 * API client for the research paper finder backend.
 */

// API base URL - defaults to localhost for development
// In production, this should be set via NEXT_PUBLIC_API_URL environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Author {
  name: string;
  affiliations: string[];
}

export interface Publication {
  id?: string;
  title?: string;
  isbn?: string;
  issn?: string;
  publisher?: string;
  category?: string;
  citeScore?: number;
  sjr?: number;
  snip?: number;
  subjectAreas: string[];
  isPotentiallyPredatory: boolean;
}

export interface Paper {
  id: string;
  doi?: string | null;
  title: string;
  abstract?: string | null;
  year?: number | null;
  publicationDate?: string | null;
  venue?: string | null;
  authors: Author[];
  citationCount?: number | null;
  citationSource?: string | null;
  oaUrl?: string | null;
  publisherUrl?: string | null;
  doiUrl?: string | null;
  urls: string[];
  topics: string[];
  keywords: string[];
  comments?: string | null;
  numberOfPages?: number | null;
  pages?: string | null;
  selected: boolean;
  categories: Record<string, string[]>;
  databases: string[];
  score: number;
  whyRecommended: string[];
  sourceIds: Record<string, string>;
  publication?: Publication | null;
  citationKey?: string | null;
}

export interface SearchResponse {
  results: Paper[];
  query: string;
  mode: string;
  sortBy: string;
  limit: number;
  totalCandidates: number;
  sourceStats: Record<string, number>;
}

export interface RelatedPaper {
  id: string;
  doi?: string | null;
  title: string;
  year?: number | null;
  venue?: string | null;
  authors: Author[];
  citationCount?: number | null;
  oaUrl?: string | null;
  doiUrl?: string | null;
}

interface SelectPaperResult {
  paper_id: string;
  selected: boolean;
  persisted: boolean;
  error?: string;
  note?: string;
}

interface UpdateCommentResult {
  paper_id: string;
  comment: string | null;
  persisted: boolean;
  error?: string;
  note?: string;
}

/**
 * Search for papers.
 */
export async function searchPapers(
  query: string,
  mode: "foundational" | "recent",
  filters: {
    limit: number;
    sortBy: "relevance" | "citations" | "year";
    yearMin?: number;
    yearMax?: number;
    oaOnly: boolean;
    surveyOnly: boolean;
    includePubmed: boolean;
    includeArxiv: boolean;
  }
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    mode,
    limit: filters.limit.toString(),
    sort_by: filters.sortBy,
    oa_only: filters.oaOnly.toString(),
    survey_only: filters.surveyOnly.toString(),
    include_pubmed: filters.includePubmed.toString(),
    include_arxiv: filters.includeArxiv.toString(),
  });

  if (filters.yearMin) {
    params.append("year_min", filters.yearMin.toString());
  }
  if (filters.yearMax) {
    params.append("year_max", filters.yearMax.toString());
  }

  const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Search failed: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Get related papers for a given paper.
 */
export async function getRelatedPapers(
  paperId: string,
  sourceIds?: Record<string, string>
): Promise<RelatedPaper[]> {
  const params = new URLSearchParams({
    limit: "20",
  });

  if (sourceIds) {
    if (sourceIds.semantic_scholar) {
      params.append("s2_id", sourceIds.semantic_scholar);
    }
    if (sourceIds.openalex) {
      params.append("oa_id", sourceIds.openalex);
    }
  }

  const response = await fetch(
    `${API_BASE_URL}/paper/${encodeURIComponent(paperId)}/related?${params.toString()}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      return [];
    }
    const errorText = await response.text();
    throw new Error(`Failed to fetch related papers: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Select or deselect a paper (bookmark).
 */
export async function selectPaper(
  paperId: string,
  selected: boolean,
  paper: Paper
): Promise<SelectPaperResult> {
  const params = new URLSearchParams({
    selected: selected.toString(),
  });

  // Prepare paper data for the request
  const paperData = {
    title: paper.title,
    doi: paper.doi,
    abstract: paper.abstract,
    year: paper.year,
    venue: paper.venue,
    authors: paper.authors,
    citationCount: paper.citationCount,
    citationSource: paper.citationSource,
    oaUrl: paper.oaUrl,
    publisherUrl: paper.publisherUrl,
    doiUrl: paper.doiUrl,
    topics: paper.topics,
    keywords: paper.keywords,
    sourceIds: paper.sourceIds,
  };

  const response = await fetch(
    `${API_BASE_URL}/paper/${encodeURIComponent(paperId)}/select?${params.toString()}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(paperData),
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to bookmark paper: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Update comment/notes on a paper.
 */
export async function updatePaperComment(
  paperId: string,
  comment: string | null,
  paper: Paper
): Promise<UpdateCommentResult> {
  const params = new URLSearchParams();
  if (comment !== null) {
    params.append("comment", comment);
  }

  // Prepare paper data for the request
  const paperData = {
    title: paper.title,
    doi: paper.doi,
    abstract: paper.abstract,
    year: paper.year,
    venue: paper.venue,
    authors: paper.authors,
    citationCount: paper.citationCount,
    citationSource: paper.citationSource,
    oaUrl: paper.oaUrl,
    publisherUrl: paper.publisherUrl,
    doiUrl: paper.doiUrl,
    topics: paper.topics,
    keywords: paper.keywords,
    sourceIds: paper.sourceIds,
  };

  const response = await fetch(
    `${API_BASE_URL}/paper/${encodeURIComponent(paperId)}/comment?${params.toString()}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(paperData),
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to update comment: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Get all bookmarked papers.
 */
export async function getBookmarkedPapers(): Promise<Paper[]> {
  const response = await fetch(`${API_BASE_URL}/papers/bookmarked?limit=500`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch bookmarked papers: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Get all papers with notes/comments.
 */
export async function getPapersWithNotes(): Promise<Paper[]> {
  const response = await fetch(`${API_BASE_URL}/papers/with-notes?limit=500`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch papers with notes: ${response.status} ${errorText}`);
  }

  return response.json();
}
