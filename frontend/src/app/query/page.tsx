"use client";

import React, { useState } from "react";
import { api, QueryResult } from "@/lib/api";

export default function QueryStudioPage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [searched, setSearched] = useState(false);

  // Queries History Log
  const [history, setHistory] = useState<string[]>([
    "Who is King Arven?",
    "When did King Arven die?",
    "What caused the Ember Siege?",
    "What faction controls Frostpeak ruins today?",
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery || !searchQuery.trim()) return;
    
    setQuery(searchQuery);
    setLoading(true);
    setError(null);
    setSearched(true);

    // Add search query to history list (de-duplicate)
    setHistory((prev) => {
      const filtered = prev.filter((h) => h !== searchQuery);
      return [searchQuery, ...filtered].slice(0, 8);
    });

    try {
      const response = await api.queryLore(searchQuery, limit);
      setResults(response.results);
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setError(errMsg || "Failed to search the vector index. Verify that GEMINI_API_KEY is configured.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 max-w-7xl mx-auto animate-fade-in pb-12">
      {/* Search Console (3 cols wide on lg) */}
      <div className="lg:col-span-3 space-y-8">
        
        {/* Title Header */}
        <div className="space-y-1.5 border-b border-[#262626] pb-4">
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
            Query Studio
          </h2>
          <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
            Execute natural language semantic queries against the lore vector indexes. The engine computes matching weights and extracts citations.
          </p>
        </div>

        {/* Stripe-style Input Box */}
        <div className="p-5 rounded border border-[#262626] bg-[#111111]/30">
          <form onSubmit={onSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Ask a question about the game world..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-[#0a0a0a] border border-[#262626] hover:border-slate-700 focus:border-[#fafafa] focus:ring-1 focus:ring-slate-850 rounded px-3 py-2 text-xs text-[#fafafa] placeholder-slate-600 transition duration-150 outline-none"
              />
            </div>
            
            <div className="sm:w-28">
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#fafafa] rounded px-2.5 py-2 text-xs text-[#a1a1aa] outline-none transition"
              >
                {[3, 5, 8, 10].map((val) => (
                  <option key={val} value={val}>
                    {val} matches
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded bg-[#b9ff66] text-[#0a0a0a] text-xs font-bold font-sans hover:opacity-90 active:opacity-95 transition shadow-sm disabled:bg-[#262626] disabled:text-slate-500"
            >
              {loading ? "Searching..." : "Run Query"}
            </button>
          </form>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-3.5 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs flex gap-2.5 items-center font-sans font-medium">
            <svg className="w-5 h-5 flex-shrink-0 text-rose-450" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Results List */}
        <div className="space-y-4">
          {loading ? (
            <div className="space-y-4">
              {[1, 2].map((i) => (
                <div key={i} className="animate-pulse p-5 rounded border border-[#262626] bg-[#171717]/40 space-y-3">
                  <div className="flex justify-between items-center border-b border-[#262626]/40 pb-2.5">
                    <div className="h-3 bg-slate-800 rounded w-1/4"></div>
                    <div className="h-3 bg-slate-800 rounded w-1/6"></div>
                  </div>
                  <div className="h-2.5 bg-slate-800 rounded w-3/4"></div>
                  <div className="h-2.5 bg-slate-800 rounded w-5/6"></div>
                </div>
              ))}
            </div>
          ) : results.length === 0 ? (
            searched && !loading ? (
              <div className="text-center p-12 rounded border border-[#262626] bg-[#111111]/10 text-slate-500 text-xs font-mono">
                No matching lore fragments found in vector database.
              </div>
            ) : (
              <div className="text-center p-16 rounded border border-[#262626] bg-[#111111]/10 space-y-3 select-none">
                <div className="h-8 w-8 rounded bg-[#171717] border border-[#262626] text-[#b9ff66] flex items-center justify-center mx-auto">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.0" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
                  </svg>
                </div>
                <h4 className="font-semibold text-slate-300 text-xs font-sans">Awaiting Narrative Queries</h4>
                <p className="text-[10px] text-slate-500 max-w-xs mx-auto leading-normal">
                  Enter a question in the search input above or select a preset history prompt on the right side-panel.
                </p>
              </div>
            )
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 px-1 uppercase tracking-wider select-none">
                <span>FOUND {results.length} CITATIONS FOR &quot;{query}&quot;</span>
              </div>

              {results.map((result, idx) => (
                <div
                  key={result.chunk_id}
                  className="p-5 rounded border border-[#262626] bg-[#171717]/40 space-y-3 hover:border-slate-800 transition duration-150"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#262626]/40 pb-2.5">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-slate-500">#{idx + 1}</span>
                      <span className="font-semibold text-[#fafafa] font-mono">{result.title}</span>
                      <span className="text-[10px] font-mono text-slate-500">
                        (Chunk #{result.chunk_index + 1})
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-[10px] font-mono">
                      <span className="text-[#fafafa] font-semibold">{(result.similarity * 100).toFixed(1)}% Match</span>
                      <span className="px-1.5 py-0.5 rounded border border-[#262626] bg-[#111111] text-[#a1a1aa] text-[9px] uppercase tracking-wide">
                        {result.confidence} Confidence
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-[#a1a1aa] leading-relaxed font-sans select-all py-0.5 pl-3 border-l border-slate-700">
                    {result.content}
                  </p>

                  <div className="text-[9px] font-mono text-slate-500 flex justify-between pt-2 border-t border-[#262626]/20">
                    <span>VECTOR ID: {result.chunk_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Query History Sidebar */}
      <div className="space-y-6">
        <div className="rounded border border-[#262626] bg-[#111111] p-5 h-[calc(100vh-140px)] flex flex-col justify-between">
          <div className="flex-1 flex flex-col min-h-0">
            <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-3 block">
              Search History
            </span>

            <div className="flex-1 overflow-y-auto mt-4 space-y-1 pr-1">
              {history.map((hist, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSearch(hist)}
                  className="w-full text-left px-2.5 py-2 rounded border border-transparent text-xs text-slate-400 hover:text-[#fafafa] hover:bg-[#171717] transition flex items-start gap-2 font-sans leading-relaxed group"
                >
                  <span className="text-slate-600 font-mono group-hover:text-[#b9ff66]">&rarr;</span>
                  <span className="truncate">{hist}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
