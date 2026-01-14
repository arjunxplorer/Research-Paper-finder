import { useQuery } from "@tanstack/react-query";
import { searchPapers, getRelatedPapers, type SearchResponse, type RelatedPaper } from "@/lib/api";
import type { Filters, SearchMode } from "@/app/page";

export function useSearch(query: string, mode: SearchMode, filters: Filters) {
  return useQuery<SearchResponse>({
    queryKey: ["search", query, mode, filters],
    queryFn: () => searchPapers(query, mode, filters),
    enabled: false, // Only search on explicit refetch
    retry: 2,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useRelatedPapers(
  paperId: string,
  sourceIds?: Record<string, string>
) {
  return useQuery<RelatedPaper[]>({
    queryKey: ["related", paperId, sourceIds],
    queryFn: () => getRelatedPapers(paperId, sourceIds),
    enabled: !!paperId,
    retry: 1,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

