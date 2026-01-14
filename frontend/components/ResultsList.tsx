"use client";

import { AlertCircle, FileSearch } from "lucide-react";
import { PaperCard } from "./PaperCard";
import type { Paper } from "@/lib/api";

interface ResultsListProps {
  results?: Paper[];
  isLoading: boolean;
  error: Error | null;
}

export function ResultsList({ results, isLoading, error }: ResultsListProps) {
  if (error) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-8 text-center">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="text-lg font-semibold text-scholar-900 mb-2">
            Search Error
          </h3>
          <p className="text-scholar-600">{error.message}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="card p-6 animate-pulse"
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="h-6 bg-scholar-200 rounded w-3/4 mb-3" />
              <div className="h-4 bg-scholar-100 rounded w-1/2 mb-4" />
              <div className="space-y-2">
                <div className="h-3 bg-scholar-100 rounded w-full" />
                <div className="h-3 bg-scholar-100 rounded w-5/6" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-12 text-center">
          <div className="w-16 h-16 bg-scholar-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileSearch className="w-8 h-8 text-scholar-400" />
          </div>
          <h3 className="text-lg font-semibold text-scholar-900 mb-2">
            Start Your Search
          </h3>
          <p className="text-scholar-600 max-w-md mx-auto">
            Enter a research topic above to discover the top 20 papers in that
            field. Toggle between Foundational and Recent modes to find classic
            or trending research.
          </p>
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-8 text-center">
          <div className="w-12 h-12 bg-scholar-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileSearch className="w-6 h-6 text-scholar-400" />
          </div>
          <h3 className="text-lg font-semibold text-scholar-900 mb-2">
            No Papers Found
          </h3>
          <p className="text-scholar-600">
            Try adjusting your search query or filters.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-scholar-900">
          Top {results.length} Papers
        </h2>
      </div>
      <div className="space-y-4">
        {results.map((paper, index) => (
          <PaperCard key={paper.id} paper={paper} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}

