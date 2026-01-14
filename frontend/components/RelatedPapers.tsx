"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, Loader2 } from "lucide-react";
import { useRelatedPapers } from "@/lib/hooks/useSearch";

interface RelatedPapersProps {
  paperId: string;
  sourceIds?: Record<string, string>;
}

export function RelatedPapers({ paperId, sourceIds }: RelatedPapersProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: papers, isLoading, error } = useRelatedPapers(paperId, sourceIds);

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="flex items-center gap-2 text-sm text-scholar-600 hover:text-primary-600 transition-colors"
      >
        <ChevronDown className="w-4 h-4" />
        Show related papers
      </button>
    );
  }

  return (
    <div className="mt-4 pt-4 border-t border-scholar-100 animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-scholar-700">
          Related Papers
        </h4>
        <button
          onClick={() => setIsExpanded(false)}
          className="flex items-center gap-1 text-xs text-scholar-500 hover:text-scholar-700"
        >
          <ChevronUp className="w-3 h-3" />
          Hide
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">Failed to load related papers</p>
      )}

      {papers && papers.length > 0 && (
        <ul className="space-y-2">
          {papers.slice(0, 5).map((paper: any) => (
            <li key={paper.id} className="text-sm">
              <a
                href={paper.doiUrl || paper.oaUrl || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-start gap-2"
              >
                <ExternalLink className="w-3.5 h-3.5 mt-0.5 text-scholar-400 group-hover:text-primary-500 flex-shrink-0" />
                <div>
                  <span className="text-scholar-800 group-hover:text-primary-600 transition-colors line-clamp-2">
                    {paper.title}
                  </span>
                  <span className="text-xs text-scholar-500 block">
                    {paper.year}
                    {paper.citationCount != null &&
                      ` • ${paper.citationCount.toLocaleString()} citations`}
                  </span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}

      {papers && papers.length === 0 && (
        <p className="text-sm text-scholar-500">No related papers found</p>
      )}
    </div>
  );
}

