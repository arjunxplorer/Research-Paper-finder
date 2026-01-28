"use client";

import { BookOpen, ArrowLeft, Lightbulb, Filter, TrendingUp, Search, Star, Sparkles } from "lucide-react";
import Link from "next/link";

export default function GuidePage() {
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
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/25">
                  <Lightbulb className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-scholar-900">
                    Search Guide
                  </h1>
                  <p className="text-xs text-scholar-500">
                    Tips for getting the best results
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {/* Understanding Search Modes */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <BookOpen className="w-5 h-5 text-primary-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  Understanding Search Modes
                </h2>
                <p className="text-scholar-600 mb-4">
                  PaperMesh offers two distinct search modes, each optimized for different research needs:
                </p>
              </div>
            </div>

            <div className="space-y-4 ml-13">
              <div className="border-l-4 border-primary-500 pl-4 py-2">
                <h3 className="font-semibold text-scholar-900 mb-1">
                  Foundational Mode
                </h3>
                <p className="text-sm text-scholar-600 mb-2">
                  Finds classic, highly-cited papers that shaped the field. Prioritizes citation count (35%), 
                  relevance (45%), and venue quality (10%).
                </p>
                <p className="text-xs text-scholar-500 italic">
                  Best for: Literature reviews, understanding field history, finding seminal works
                </p>
              </div>

              <div className="border-l-4 border-green-500 pl-4 py-2">
                <h3 className="font-semibold text-scholar-900 mb-1">
                  Recent Mode
                </h3>
                <p className="text-sm text-scholar-600 mb-2">
                  Discovers papers with fast-rising citations and momentum. Prioritizes relevance (55%), 
                  citation velocity (25%), and recency (15%).
                </p>
                <p className="text-xs text-scholar-500 italic">
                  Best for: Staying current, finding emerging trends, discovering hot topics
                </p>
              </div>
            </div>
          </section>

          {/* Query Tips */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Search className="w-5 h-5 text-purple-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  Writing Effective Queries
                </h2>
                <p className="text-scholar-600 mb-4">
                  The search engine uses intelligent query detection to understand your intent and adjust rankings accordingly.
                </p>
              </div>
            </div>

            <div className="space-y-4 ml-13">
              <div>
                <h3 className="font-semibold text-scholar-900 mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-yellow-500" />
                  Be Specific
                </h3>
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <span className="text-green-600 font-bold mt-0.5">✓</span>
                    <div>
                      <p className="text-sm text-scholar-700 font-medium">
                        "graph neural networks for molecule prediction"
                      </p>
                      <p className="text-xs text-scholar-500">
                        Specific topic with application domain
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-red-600 font-bold mt-0.5">✗</span>
                    <div>
                      <p className="text-sm text-scholar-700 font-medium">
                        "neural networks"
                      </p>
                      <p className="text-xs text-scholar-500">
                        Too broad, will return generic results
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-scholar-900 mb-2">
                  Use Smart Keywords
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-xs font-semibold text-blue-900 mb-1">For Surveys</p>
                    <p className="text-xs text-blue-700">
                      Include: "survey", "review", "overview", "state of the art"
                    </p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="text-xs font-semibold text-green-900 mb-1">For Recent Papers</p>
                    <p className="text-xs text-green-700">
                      Include: "recent", "latest", "2024", "emerging", "trending"
                    </p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3">
                    <p className="text-xs font-semibold text-purple-900 mb-1">For Classic Papers</p>
                    <p className="text-xs text-purple-700">
                      Include: "foundational", "seminal", "classic", "pioneering"
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="text-sm text-yellow-900">
                  <strong>Pro Tip:</strong> The system automatically detects your intent from query keywords 
                  and adjusts rankings to better match what you're looking for.
                </p>
              </div>
            </div>
          </section>

          {/* Using Filters */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Filter className="w-5 h-5 text-orange-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  Advanced Filtering
                </h2>
                <p className="text-scholar-600 mb-4">
                  Click the filter icon next to the search button to access powerful filtering options.
                </p>
              </div>
            </div>

            <div className="space-y-3 ml-13">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Sort By</h4>
                  <ul className="text-xs text-scholar-600 space-y-1">
                    <li><strong>Relevance:</strong> Best match to your query (default)</li>
                    <li><strong>Citations:</strong> Highest cited papers first</li>
                    <li><strong>Year:</strong> Newest papers first</li>
                  </ul>
                </div>

                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Year Range</h4>
                  <p className="text-xs text-scholar-600">
                    Filter papers by publication year. Useful for historical research or focusing on recent developments.
                  </p>
                </div>

                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Open Access Only</h4>
                  <p className="text-xs text-scholar-600">
                    Show only papers with free, full-text access. Papers with available PDF links will be prioritized.
                  </p>
                </div>

                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Survey/Review Only</h4>
                  <p className="text-xs text-scholar-600">
                    Filter to show only survey and review papers. Great for getting field overviews.
                  </p>
                </div>

                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Data Sources</h4>
                  <p className="text-xs text-scholar-600">
                    Toggle PubMed (biomedical) and arXiv (preprints) sources on/off. Semantic Scholar and OpenAlex are always included.
                  </p>
                </div>

                <div className="border border-scholar-200 rounded-lg p-3">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">Results Count</h4>
                  <p className="text-xs text-scholar-600">
                    Choose 10, 20, 50, or 100 results. Higher counts allow deeper exploration but may include less relevant papers.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* How Ranking Works */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <TrendingUp className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  How Papers Are Ranked
                </h2>
                <p className="text-scholar-600 mb-4">
                  PaperMesh uses a sophisticated two-stage ranking algorithm to find the best papers for your query.
                </p>
              </div>
            </div>

            <div className="space-y-4 ml-13">
              <div>
                <h3 className="font-semibold text-scholar-900 mb-2">Stage 1: Relevance Pre-filtering</h3>
                <p className="text-sm text-scholar-600">
                  First, we fetch papers from multiple databases (Semantic Scholar, OpenAlex, PubMed, arXiv) 
                  and filter to the top 200 most relevant candidates based on semantic similarity to your query.
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-scholar-900 mb-2">Stage 2: Mode-Specific Ranking</h3>
                <p className="text-sm text-scholar-600 mb-2">
                  Then, we re-rank these candidates using mode-specific weights:
                </p>
                <div className="bg-scholar-50 rounded-lg p-4 space-y-2">
                  <p className="text-xs text-scholar-700">
                    <strong>Foundational:</strong> Relevance (45%) + Citations (35%) + Venue (10%) + Survey Boost (5%) + Open Access (5%)
                  </p>
                  <p className="text-xs text-scholar-700">
                    <strong>Recent:</strong> Relevance (55%) + Citation Velocity (25%) + Recency (15%) + Venue (3%) + Open Access (2%)
                  </p>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-scholar-900 mb-2">Diversity Filters</h3>
                <p className="text-sm text-scholar-600">
                  To ensure result variety, we automatically apply:
                </p>
                <ul className="text-sm text-scholar-600 list-disc list-inside space-y-1 mt-2">
                  <li>Maximum 2 papers per first author</li>
                  <li>Maximum 3 papers per venue</li>
                  <li>Maximum 6 survey papers (unless Survey Only mode)</li>
                  <li>Balanced temporal distribution across decades</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Best Practices */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Star className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  Best Practices
                </h2>
              </div>
            </div>

            <div className="space-y-3 ml-13">
              <div className="flex items-start gap-3">
                <span className="text-2xl">1️⃣</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">
                    Start with Foundational Mode
                  </h4>
                  <p className="text-sm text-scholar-600">
                    When exploring a new topic, begin with Foundational mode to understand the seminal papers 
                    and establish a knowledge base.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="text-2xl">2️⃣</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">
                    Switch to Recent for Updates
                  </h4>
                  <p className="text-sm text-scholar-600">
                    After understanding the basics, switch to Recent mode to discover the latest developments 
                    and emerging trends.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="text-2xl">3️⃣</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">
                    Iterate Your Query
                  </h4>
                  <p className="text-sm text-scholar-600">
                    If results aren't quite right, try refining your query with more specific terms or different keywords. 
                    Your search history is saved automatically.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="text-2xl">4️⃣</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">
                    Use Bookmarks and Notes
                  </h4>
                  <p className="text-sm text-scholar-600">
                    Bookmark interesting papers and add notes to build your personal research library. 
                    Access them anytime from the header menu.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="text-2xl">5️⃣</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-scholar-900 text-sm mb-1">
                    Explore Related Papers
                  </h4>
                  <p className="text-sm text-scholar-600">
                    Click on any paper to see related works, citations, and references to expand your research.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Data Sources */}
          <section className="card p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <BookOpen className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-scholar-900 mb-2">
                  Data Sources
                </h2>
                <p className="text-scholar-600 mb-4">
                  PaperMesh aggregates and deduplicates papers from multiple authoritative sources:
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 ml-13">
              <div className="border border-scholar-200 rounded-lg p-3">
                <h4 className="font-semibold text-scholar-900 text-sm mb-1">Semantic Scholar</h4>
                <p className="text-xs text-scholar-600">
                  AI-powered academic search with 200M+ papers and citation graphs. Always included.
                </p>
              </div>
              <div className="border border-scholar-200 rounded-lg p-3">
                <h4 className="font-semibold text-scholar-900 text-sm mb-1">OpenAlex</h4>
                <p className="text-xs text-scholar-600">
                  Open bibliographic catalog with 250M+ works and comprehensive metadata. Always included.
                </p>
              </div>
              <div className="border border-scholar-200 rounded-lg p-3">
                <h4 className="font-semibold text-scholar-900 text-sm mb-1">PubMed</h4>
                <p className="text-xs text-scholar-600">
                  Biomedical and life sciences literature. Toggle on/off in filters. Best for health/bio research.
                </p>
              </div>
              <div className="border border-scholar-200 rounded-lg p-3">
                <h4 className="font-semibold text-scholar-900 text-sm mb-1">arXiv</h4>
                <p className="text-xs text-scholar-600">
                  Open-access preprint repository. Toggle on/off in filters. Great for cutting-edge research.
                </p>
              </div>
            </div>
          </section>

          {/* Back to Search CTA */}
          <div className="text-center pt-4">
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors shadow-lg shadow-primary-600/25"
            >
              <Search className="w-4 h-4" />
              Start Searching
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
