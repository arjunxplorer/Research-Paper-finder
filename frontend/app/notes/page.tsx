"use client";

import { useState, useEffect } from "react";
import { MessageSquare, BookOpen, ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { PaperCard } from "@/components/PaperCard";
import { getPapersWithNotes } from "@/lib/api";
import type { Paper } from "@/lib/api";

export default function NotesPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  async function fetchNotes() {
    setIsLoading(true);
    setError(null);
    try {
      const papersWithNotes = await getPapersWithNotes();
      console.log("Fetched papers with notes:", papersWithNotes.length);
      setPapers(papersWithNotes);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load notes";
      setError(new Error(errorMessage));
      console.error("Error fetching papers with notes:", err);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchNotes();
  }, [refreshKey]);

  // Refresh when page becomes visible or focused (user returns from another tab/page)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        setRefreshKey((k) => k + 1);
      }
    };
    const handleFocus = () => {
      setRefreshKey((k) => k + 1);
    };
    // Listen for storage events (when notes are updated from other tabs/pages)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "note_updated") {
        setRefreshKey((k) => k + 1);
      }
    };
    
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", handleFocus);
    window.addEventListener("storage", handleStorageChange);
    
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-scholar-50 via-white to-primary-50/30">
      {/* Header */}
      <header className="border-b border-scholar-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="p-2 hover:bg-scholar-100 rounded-lg transition-colors"
                title="Back to search"
              >
                <ArrowLeft className="w-5 h-5 text-scholar-600" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
                  <MessageSquare className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-scholar-900">
                    Papers with Notes
                  </h1>
                  <p className="text-xs text-scholar-500">
                    Your annotated research papers
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading ? (
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
        ) : error ? (
          <div className="max-w-3xl mx-auto">
            <div className="card p-8 text-center">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <MessageSquare className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-scholar-900 mb-2">
                Error Loading Notes
              </h3>
              <p className="text-scholar-600">{error.message}</p>
            </div>
          </div>
        ) : papers.length === 0 ? (
          <div className="max-w-3xl mx-auto">
            <div className="card p-12 text-center">
              <div className="w-16 h-16 bg-scholar-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <MessageSquare className="w-8 h-8 text-scholar-400" />
              </div>
              <h3 className="text-lg font-semibold text-scholar-900 mb-2">
                No Papers with Notes
              </h3>
              <p className="text-scholar-600 max-w-md mx-auto mb-6">
                Add notes to papers from search results to see them here.
              </p>
              <Link
                href="/"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                Go to Search
              </Link>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-scholar-900">
                {papers.length} {papers.length === 1 ? "Paper" : "Papers"} with Notes
              </h2>
              <button
                onClick={() => setRefreshKey((k) => k + 1)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg hover:bg-scholar-100 transition-colors text-scholar-700"
                title="Refresh notes"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
            <div className="space-y-4">
              {papers.map((paper, index) => (
                <PaperCard key={paper.id} paper={paper} rank={index + 1} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
