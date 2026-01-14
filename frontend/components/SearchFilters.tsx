"use client";

import type { Filters, SortBy } from "@/app/page";
import { ToggleSwitch } from "./ToggleSwitch";

interface SearchFiltersProps {
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
}

const LIMIT_OPTIONS = [10, 20, 50, 100];

const SORT_OPTIONS: { value: SortBy; label: string; description: string }[] = [
  { value: "relevance", label: "Relevance", description: "Best match to your query" },
  { value: "citations", label: "Citations", description: "Highest cited first" },
  { value: "year", label: "Year", description: "Newest first" },
];

export function SearchFilters({ filters, onFiltersChange }: SearchFiltersProps) {
  const currentYear = new Date().getFullYear();

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-scholar-700 uppercase tracking-wide mb-4">
        Filters
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
        {/* Results Count */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-scholar-600">
            Results
          </label>
          <div className="flex gap-1">
            {LIMIT_OPTIONS.map((num) => (
              <button
                key={num}
                onClick={() => onFiltersChange({ ...filters, limit: num })}
                className={`flex-1 px-2 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                  filters.limit === num
                    ? "bg-primary-500 text-white shadow-md"
                    : "bg-scholar-100 text-scholar-600 hover:bg-scholar-200"
                }`}
              >
                {num}
              </button>
            ))}
          </div>
        </div>

        {/* Sort By */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-scholar-600">
            Sort By
          </label>
          <select
            value={filters.sortBy}
            onChange={(e) =>
              onFiltersChange({ ...filters, sortBy: e.target.value as SortBy })
            }
            className="w-full px-3 py-2 text-sm rounded-lg border border-scholar-300 focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-scholar-400">
            {SORT_OPTIONS.find((o) => o.value === filters.sortBy)?.description}
          </p>
        </div>

        {/* Year Range */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-scholar-600">
            Year Range
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              placeholder="From"
              min={1900}
              max={currentYear}
              value={filters.yearMin || ""}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  yearMin: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              className="w-full px-3 py-2 text-sm rounded-lg border border-scholar-300 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <span className="text-scholar-400">–</span>
            <input
              type="number"
              placeholder="To"
              min={1900}
              max={currentYear}
              value={filters.yearMax || ""}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  yearMax: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              className="w-full px-3 py-2 text-sm rounded-lg border border-scholar-300 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Toggles */}
        <div className="space-y-3">
          <ToggleSwitch
            label="Open Access Only"
            checked={filters.oaOnly}
            onChange={(checked) => onFiltersChange({ ...filters, oaOnly: checked })}
          />
          <ToggleSwitch
            label="Survey/Review Only"
            checked={filters.surveyOnly}
            onChange={(checked) => onFiltersChange({ ...filters, surveyOnly: checked })}
          />
        </div>

        {/* Source Toggles */}
        <div className="space-y-3">
          <ToggleSwitch
            label="Include PubMed"
            checked={filters.includePubmed}
            onChange={(checked) =>
              onFiltersChange({ ...filters, includePubmed: checked })
            }
          />
          <ToggleSwitch
            label="Include arXiv"
            checked={filters.includeArxiv}
            onChange={(checked) =>
              onFiltersChange({ ...filters, includeArxiv: checked })
            }
          />
        </div>
      </div>
    </div>
  );
}

