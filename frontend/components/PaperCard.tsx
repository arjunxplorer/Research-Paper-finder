"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  BookOpen,
  Quote,
  Sparkles,
  Unlock,
  Star,
  MessageSquare,
  Tag,
  Calendar,
  FileText,
} from "lucide-react";
import type { Paper } from "@/lib/api";
import { RelatedPapers } from "./RelatedPapers";
import { selectPaper, updatePaperComment } from "@/lib/api";

interface PaperCardProps {
  paper: Paper;
  rank: number;
}

export function PaperCard({ paper, rank }: PaperCardProps) {
  const [showAbstract, setShowAbstract] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [commentText, setCommentText] = useState(paper.comments || "");
  const [isSelected, setIsSelected] = useState(paper.selected || false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSelect = async () => {
    // Prevent multiple rapid clicks
    if (isSaving) return;
    
    setIsSaving(true);
    setSaveError(null);
    const newSelectedState = !isSelected;
    
    try {
      // Validate paper data before sending
      if (!paper.title || paper.title.trim() === "") {
        throw new Error("Paper title is required to bookmark");
      }
      
      // Pass paper data so it can be saved to database
      const result = await selectPaper(paper.id, newSelectedState, paper);
      console.log("Bookmark result:", result);
      
      if (result.persisted) {
        setIsSelected(newSelectedState);
        console.log("✓ Paper bookmarked successfully");
        // Clear error on success
        setSaveError(null);
        // Notify other pages/tabs about bookmark update
        if (typeof window !== "undefined") {
          localStorage.setItem("bookmark_updated", Date.now().toString());
          // Trigger storage event for same-tab listeners
          window.dispatchEvent(new StorageEvent("storage", {
            key: "bookmark_updated",
            newValue: Date.now().toString(),
          }));
        }
      } else {
        // Show error to user
        const errorMsg = result.error || result.note || "Failed to save bookmark";
        setSaveError(errorMsg);
        console.warn("⚠ Bookmark may not have been persisted:", errorMsg);
        // Don't update state if persistence failed
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to bookmark paper. Please try again.";
      console.error("Failed to select paper:", error);
      setSaveError(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCommentSave = async () => {
    // Prevent multiple rapid clicks
    if (isSaving) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    try {
      // Validate paper data before sending
      if (!paper.title || paper.title.trim() === "") {
        throw new Error("Paper title is required to save comment");
      }
      
      // Pass paper data so it can be saved to database
      const result = await updatePaperComment(paper.id, commentText || null, paper);
      console.log("Comment result:", result);
      
      if (result.persisted) {
        setShowComments(false);
        console.log("✓ Comment saved successfully");
        // Clear error on success
        setSaveError(null);
        // Notify other pages/tabs about note update
        if (typeof window !== "undefined") {
          localStorage.setItem("note_updated", Date.now().toString());
          // Trigger storage event for same-tab listeners
          window.dispatchEvent(new StorageEvent("storage", {
            key: "note_updated",
            newValue: Date.now().toString(),
          }));
        }
        // Note: We don't mutate paper.comments - it will be updated when the component re-renders with new data
      } else {
        // Show error to user
        const errorMsg = result.error || result.note || "Failed to save comment";
        setSaveError(errorMsg);
        console.warn("⚠ Comment may not have been persisted:", errorMsg);
        // Don't close editor if persistence failed
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to save comment. Please try again.";
      console.error("Failed to update comment:", error);
      setSaveError(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
    } catch {
      return null;
    }
  };

  const formatAuthors = (authors: Paper["authors"]) => {
    if (authors.length === 0) return "Unknown authors";
    if (authors.length <= 3) {
      return authors.map((a) => a.name).join(", ");
    }
    return `${authors[0].name}, ${authors[1].name}, ... +${authors.length - 2} more`;
  };

  return (
    <article
      className="card p-6 animate-slide-up"
      style={{ animationDelay: `${rank * 50}ms` }}
    >
      {/* Header */}
      <div className="flex items-start gap-4">
        {/* Rank Badge */}
        <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center text-white font-bold shadow-lg shadow-primary-500/20">
          {rank}
        </div>

        <div className="flex-1 min-w-0">
          {/* Title */}
          <h3 className="text-lg font-semibold text-scholar-900 leading-snug mb-2 font-serif">
            {paper.doiUrl || paper.publisherUrl || paper.oaUrl ? (
              <a
                href={paper.doiUrl || paper.publisherUrl || paper.oaUrl || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary-600 transition-colors"
              >
                {paper.title}
              </a>
            ) : (
              paper.title
            )}
          </h3>

          {/* Authors */}
          <p className="text-sm text-scholar-600 mb-2">
            {formatAuthors(paper.authors)}
          </p>

          {/* Venue & Year */}
          <div className="flex items-center gap-3 text-sm text-scholar-500 mb-3 flex-wrap">
            {paper.venue && (
              <span className="flex items-center gap-1">
                <BookOpen className="w-3.5 h-3.5" />
                {paper.venue}
              </span>
            )}
            {paper.publicationDate ? (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                {formatDate(paper.publicationDate) || paper.year}
              </span>
            ) : (
              paper.year && <span>• {paper.year}</span>
            )}
            {paper.pages && (
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                {paper.pages}
                {paper.numberOfPages && ` (${paper.numberOfPages} pages)`}
              </span>
            )}
            {paper.citationCount != null && (
              <span className="flex items-center gap-1">
                <Quote className="w-3.5 h-3.5" />
                {paper.citationCount.toLocaleString()} citations
                {paper.citationSource && (
                  <span className="text-xs text-scholar-400">
                    ({paper.citationSource})
                  </span>
                )}
              </span>
            )}
            {paper.citationKey && (
              <span className="text-xs text-scholar-400" title="Citation key">
                [{paper.citationKey}]
              </span>
            )}
          </div>

          {/* Keywords */}
          {paper.keywords && paper.keywords.length > 0 && (
            <div className="mb-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-scholar-600 mb-1.5">
                <Tag className="w-3.5 h-3.5" />
                Keywords
              </div>
              <div className="flex flex-wrap gap-1.5">
                {paper.keywords.map((keyword, i) => (
                  <span
                    key={i}
                    className="text-xs bg-scholar-100 text-scholar-700 px-2 py-0.5 rounded"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Publication Quality Metrics */}
          {paper.publication && (
            <div className="mb-3 text-xs text-scholar-600">
              {paper.publication.category && (
                <span className="mr-2">Type: {paper.publication.category}</span>
              )}
              {paper.publication.citeScore !== null && paper.publication.citeScore !== undefined && (
                <span className="mr-2">CiteScore: {paper.publication.citeScore.toFixed(2)}</span>
              )}
              {paper.publication.sjr !== null && paper.publication.sjr !== undefined && (
                <span className="mr-2">SJR: {paper.publication.sjr.toFixed(2)}</span>
              )}
              {paper.publication.isPotentiallyPredatory && (
                <span className="text-red-600 font-medium">⚠ Potentially Predatory</span>
              )}
            </div>
          )}

          {/* Why Recommended */}
          {paper.whyRecommended.length > 0 && (
            <div className="mb-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-primary-600 mb-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                Why recommended
              </div>
              <ul className="flex flex-wrap gap-2">
                {paper.whyRecommended.map((reason, i) => (
                  <li
                    key={i}
                    className="text-xs bg-primary-50 text-primary-700 px-2.5 py-1 rounded-full"
                  >
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Abstract Toggle */}
          {paper.abstract && (
            <div>
              <button
                onClick={() => setShowAbstract(!showAbstract)}
                className="flex items-center gap-1 text-sm text-scholar-600 hover:text-scholar-900 transition-colors"
              >
                {showAbstract ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Hide abstract
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    Show abstract
                  </>
                )}
              </button>
              {showAbstract && (
                <p className="mt-2 text-sm text-scholar-700 leading-relaxed animate-fade-in">
                  {paper.abstract}
                </p>
              )}
            </div>
          )}

          {/* Error Message */}
          {saveError && (
            <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              <span className="font-medium">Error:</span> {saveError}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-scholar-100">
            {/* Select/Bookmark Button */}
            <button
              onClick={handleSelect}
              disabled={isSaving}
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                isSelected
                  ? "bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                  : "bg-scholar-100 text-scholar-700 hover:bg-scholar-200"
              } ${isSaving ? "opacity-50 cursor-not-allowed" : ""}`}
              title={isSelected ? "Remove from bookmarks" : "Add to bookmarks"}
            >
              <Star className={`w-3.5 h-3.5 ${isSelected ? "fill-current" : ""}`} />
              {isSaving ? "Saving..." : isSelected ? "Bookmarked" : "Bookmark"}
            </button>

            {/* Comment Button */}
            <button
              onClick={() => setShowComments(!showComments)}
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-scholar-100 text-scholar-700 hover:bg-scholar-200 transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              {paper.comments ? "Edit Note" : "Add Note"}
            </button>

            {/* Links */}
            {paper.doiUrl && (
              <a
                href={paper.doiUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-scholar-100 text-scholar-700 hover:bg-scholar-200 transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                DOI
              </a>
            )}
            {paper.publisherUrl && paper.publisherUrl !== paper.doiUrl && (
              <a
                href={paper.publisherUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-scholar-100 text-scholar-700 hover:bg-scholar-200 transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Publisher
              </a>
            )}
            {paper.oaUrl && (
              <a
                href={paper.oaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
              >
                <Unlock className="w-3.5 h-3.5" />
                Open Access
              </a>
            )}
          </div>

          {/* Comment Editor */}
          {showComments && (
            <div className="mt-4 pt-4 border-t border-scholar-100 animate-fade-in">
              <label className="block text-xs font-medium text-scholar-700 mb-2">
                Notes/Comments
              </label>
              <textarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add your notes about this paper..."
                className="w-full text-sm p-2 border border-scholar-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                rows={3}
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={handleCommentSave}
                  disabled={isSaving}
                  className="text-xs font-medium px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
                <button
                  onClick={() => {
                    setShowComments(false);
                    setCommentText(paper.comments || "");
                  }}
                  className="text-xs font-medium px-3 py-1.5 bg-scholar-100 text-scholar-700 rounded-lg hover:bg-scholar-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Display existing comment */}
          {paper.comments && !showComments && (
            <div className="mt-3 pt-3 border-t border-scholar-100">
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 text-scholar-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-scholar-600 mb-1">Your Note</p>
                  <p className="text-sm text-scholar-700">{paper.comments}</p>
                </div>
              </div>
            </div>
          )}

          {/* Related Papers */}
          <RelatedPapers paperId={paper.id} sourceIds={paper.sourceIds} />
        </div>
      </div>
    </article>
  );
}

