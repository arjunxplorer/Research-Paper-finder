"use client";

import { useState, useEffect } from "react";
import { Search, BookOpen, TrendingUp, Filter, Star, MessageSquare, Lightbulb } from "lucide-react";
import Link from "next/link";
import { SearchFilters } from "@/components/SearchFilters";
import { ResultsList } from "@/components/ResultsList";
import { useSearch } from "@/lib/hooks/useSearch";

export type SearchMode = "foundational" | "recent";
export type SortBy = "relevance" | "citations" | "year";

export interface Filters {
  limit: number;
  sortBy: SortBy;
  yearMin?: number;
  yearMax?: number;
  oaOnly: boolean;
  surveyOnly: boolean;
  includePubmed: boolean;
  includeArxiv: boolean;
}

const STORAGE_KEY = "research_tool_search_state";

function loadSearchState() {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error("Failed to load search state:", e);
  }
  return null;
}

function saveSearchState(query: string, mode: SearchMode, filters: Filters) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ query, mode, filters }));
  } catch (e) {
    console.error("Failed to save search state:", e);
  }
}

export default function Home() {
  const savedState = loadSearchState();
  const [query, setQuery] = useState(savedState?.query || "");
  const [mode, setMode] = useState<SearchMode>(savedState?.mode || "foundational");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>(
    savedState?.filters || {
      limit: 20,
      sortBy: "relevance",
      oaOnly: false,
      surveyOnly: false,
      includePubmed: true,
      includeArxiv: true,
    }
  );

  const { data, isLoading, error, refetch } = useSearch(query, mode, filters);

  // Save state when it changes
  useEffect(() => {
    if (query || mode || filters) {
      saveSearchState(query, mode, filters);
    }
  }, [query, mode, filters]);

  // Restore search results if we have a saved query
  useEffect(() => {
    if (savedState?.query && query === savedState.query) {
      // Refetch if we have a saved query
      refetch();
    }
  }, []); // Only run on mount

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      refetch();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-scholar-50 via-white to-primary-50/30">
      {/* Header */}
      <header className="border-b border-scholar-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/25">
                <BookOpen className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-scholar-900">
                  PaperMesh
                </h1>
                <p className="text-xs text-scholar-500">
                  Discover top research papers
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/guide"
                className="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-scholar-100 transition-colors text-scholar-700"
                title="Search tips and guide"
              >
                <Lightbulb className="w-4 h-4" />
                <span className="hidden sm:inline">Guide</span>
              </Link>
              <Link
                href="/bookmarks"
                className="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-scholar-100 transition-colors text-scholar-700"
                title="View bookmarked papers"
              >
                <Star className="w-4 h-4" />
                <span className="hidden sm:inline">Bookmarks</span>
              </Link>
              <Link
                href="/notes"
                className="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-scholar-100 transition-colors text-scholar-700"
                title="View papers with notes"
              >
                <MessageSquare className="w-4 h-4" />
                <span className="hidden sm:inline">Notes</span>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search Section */}
        <div className="max-w-3xl mx-auto mb-8">
          {/* Mode Toggle */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex bg-scholar-100 rounded-xl p-1.5 gap-1">
              <button
                onClick={() => setMode("foundational")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                  mode === "foundational" ? "toggle-active" : "toggle-inactive"
                }`}
              >
                <BookOpen className="w-4 h-4" />
                Foundational
              </button>
              <button
                onClick={() => setMode("recent")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                  mode === "recent" ? "toggle-active" : "toggle-inactive"
                }`}
              >
                <TrendingUp className="w-4 h-4" />
                Recent
              </button>
            </div>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearch} className="relative">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-scholar-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a research topic, e.g. 'graph neural networks for molecule prediction'"
                className="input-field pl-12 pr-32 py-4 text-lg"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowFilters(!showFilters)}
                  className={`p-2.5 rounded-lg transition-colors ${
                    showFilters
                      ? "bg-primary-100 text-primary-600"
                      : "hover:bg-scholar-100 text-scholar-500"
                  }`}
                >
                  <Filter className="w-5 h-5" />
                </button>
                <button
                  type="submit"
                  disabled={!query.trim() || isLoading}
                  className="btn-primary px-5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? "Searching..." : "Search"}
                </button>
              </div>
            </div>
          </form>

          {/* Mode Description */}
          <p className="text-center text-sm text-scholar-500 mt-3">
            {mode === "foundational"
              ? "Classic, highly-cited papers that shaped the field"
              : "Recent papers with fast-rising citations and momentum"}
          </p>
        </div>

        {/* Filters Sidebar */}
        {showFilters && (
          <div className="max-w-3xl mx-auto mb-6 animate-fade-in">
            <SearchFilters filters={filters} onFiltersChange={setFilters} />
          </div>
        )}

        {/* Results */}
        <ResultsList results={data?.results} isLoading={isLoading} error={error} />
      </main>

      {/* Footer */}
      <footer className="border-t border-scholar-200 bg-white mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-scholar-500">
            Data sourced from Semantic Scholar, OpenAlex, PubMed, and arXiv
          </p>
        </div>
      </footer>
    </div>
  );
}

