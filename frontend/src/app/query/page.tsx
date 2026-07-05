"use client";

import React, { useMemo, useState } from "react";
import { api, QueryResult } from "@/lib/api";

const SAMPLE_QUERIES = [
  "Who is King Arven?",
  "What caused the Ember Siege?",
  "Which faction controls Frostpeak?",
  "What should Eldrin remember?",
];

function confidenceTone(confidence: string) {
  const normalized = confidence.toLowerCase();
  if (normalized.includes("high")) return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  if (normalized.includes("medium")) return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  return "border-[#2f3742] bg-[#15191f] text-[#aab4c0]";
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default function QueryStudioPage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>(SAMPLE_QUERIES);

  const bestMatch = results[0];

  const groupedSources = useMemo(() => {
    const sourceMap = new Map<string, number>();
    results.forEach((result) => {
      sourceMap.set(result.title, (sourceMap.get(result.title) || 0) + 1);
    });
    return Array.from(sourceMap.entries()).map(([title, count]) => ({ title, count }));
  }, [results]);

  const handleSearch = async (searchQuery: string) => {
    const trimmed = searchQuery.trim();
    if (!trimmed) return;

    setQuery(trimmed);
    setLoading(true);
    setError(null);
    setMessage(null);
    setSearched(true);

    setHistory((prev) => {
      const filtered = prev.filter((item) => item !== trimmed);
      return [trimmed, ...filtered].slice(0, 8);
    });

    try {
      const response = await api.queryLore(trimmed, limit);
      setResults(response.results);
      setMessage(response.message || null);
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setError(errMsg || "Failed to search the local vector index. Check that the backend and Chroma are running.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    handleSearch(query);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-10 pb-12">
      <section className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-8">
          <div className="space-y-4">
            <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-[#7f8b9a]">
              Query Studio
            </div>
            <div className="max-w-3xl space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight text-[#f5f7fa]">
                Ask your lore base a direct question.
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-[#9aa5b4]">
                Search uploaded GDDs and lore files using local Chroma embeddings. GameMind returns the best grounded
                match first, with citations kept close for inspection.
              </p>
            </div>
          </div>

          <form
            onSubmit={onSubmit}
            className="rounded-md border border-[#242a32] bg-[#0f1216] p-3 shadow-[0_18px_60px_rgba(0,0,0,0.24)]"
          >
            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="sr-only" htmlFor="lore-query">
                Lore question
              </label>
              <input
                id="lore-query"
                type="text"
                placeholder="Ask about characters, factions, locations, quests..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-h-11 flex-1 rounded-md border border-[#252b34] bg-[#090b0e] px-4 text-sm text-[#f5f7fa] outline-none transition placeholder:text-[#66717f] hover:border-[#38414d] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/15"
              />

              <label className="sr-only" htmlFor="match-limit">
                Number of citations
              </label>
              <select
                id="match-limit"
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
                className="min-h-11 rounded-md border border-[#252b34] bg-[#090b0e] px-3 text-sm text-[#dbe2ea] outline-none transition hover:border-[#38414d] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/15 sm:w-32"
              >
                {[3, 5, 8, 10].map((value) => (
                  <option key={value} value={value}>
                    {value} citations
                  </option>
                ))}
              </select>

              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="min-h-11 rounded-md bg-[#f5f7fa] px-5 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:bg-[#252b34] disabled:text-[#66717f]"
              >
                {loading ? "Searching" : "Search lore"}
              </button>
            </div>
          </form>

          {error && (
            <div className="rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          {loading ? (
            <div className="space-y-4">
              <div className="h-48 animate-pulse rounded-md border border-[#242a32] bg-[#101419]" />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="h-32 animate-pulse rounded-md border border-[#242a32] bg-[#101419]" />
                <div className="h-32 animate-pulse rounded-md border border-[#242a32] bg-[#101419]" />
              </div>
            </div>
          ) : bestMatch ? (
            <div className="space-y-6">
              <section className="rounded-md border border-[#242a32] bg-[#0f1216]">
                <div className="border-b border-[#242a32] px-6 py-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                      <div className="text-[11px] font-medium uppercase tracking-[0.2em] text-[#7f8b9a]">
                        Best grounded match
                      </div>
                      <h2 className="text-xl font-semibold tracking-tight text-[#f5f7fa]">
                        {bestMatch.title}
                      </h2>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-[#2f3742] bg-[#15191f] px-3 py-1 text-xs font-medium text-[#dbe2ea]">
                        {formatPercent(bestMatch.similarity)} match
                      </span>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-medium ${confidenceTone(bestMatch.confidence)}`}
                      >
                        {bestMatch.confidence} confidence
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-5 px-6 py-6">
                  <p className="max-w-3xl text-base leading-8 text-[#f5f7fa]">
                    {bestMatch.content}
                  </p>

                  <div className="flex flex-wrap gap-2 text-xs text-[#9aa5b4]">
                    <span className="rounded-md border border-[#242a32] bg-[#090b0e] px-2.5 py-1">
                      Chunk {bestMatch.chunk_index + 1}
                    </span>
                    <span className="rounded-md border border-[#242a32] bg-[#090b0e] px-2.5 py-1">
                      {results.length} citations found
                    </span>
                    {message && (
                      <span className="rounded-md border border-[#242a32] bg-[#090b0e] px-2.5 py-1">
                        {message}
                      </span>
                    )}
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-[#f5f7fa]">Citations</h2>
                  <span className="text-xs text-[#7f8b9a]">Grounding for &quot;{query}&quot;</span>
                </div>

                <div className="space-y-3">
                  {results.map((result, index) => (
                    <article
                      key={result.chunk_id}
                      className="rounded-md border border-[#242a32] bg-[#0f1216] px-5 py-4 transition hover:border-[#38414d]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-medium text-[#7f8b9a]">#{index + 1}</span>
                            <h3 className="truncate text-sm font-semibold text-[#f5f7fa]">{result.title}</h3>
                            <span className="text-xs text-[#7f8b9a]">Chunk {result.chunk_index + 1}</span>
                          </div>
                          <p className="line-clamp-3 text-sm leading-6 text-[#aab4c0]">{result.content}</p>
                        </div>

                        <div className="flex shrink-0 items-center gap-2 text-xs">
                          <span className="font-medium text-[#dbe2ea]">{formatPercent(result.similarity)}</span>
                          <span className={`rounded-full border px-2.5 py-1 ${confidenceTone(result.confidence)}`}>
                            {result.confidence}
                          </span>
                        </div>
                      </div>

                      <details className="mt-3 border-t border-[#20262e] pt-3">
                        <summary className="cursor-pointer text-xs font-medium text-[#8bdff0] outline-none transition hover:text-[#b7eef7] focus-visible:ring-2 focus-visible:ring-[#8bdff0]/30">
                          Technical details
                        </summary>
                        <div className="mt-3 grid gap-2 text-xs text-[#7f8b9a] sm:grid-cols-2">
                          <div>Document ID: {result.document_id}</div>
                          <div>Vector ID: {result.chunk_id}</div>
                        </div>
                      </details>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : searched ? (
            <div className="rounded-md border border-[#242a32] bg-[#0f1216] px-6 py-12 text-center">
              <h2 className="text-lg font-semibold text-[#f5f7fa]">No matching lore found</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#9aa5b4]">
                Upload a GDD or lore document first, then ask a question that appears in the source material.
              </p>
            </div>
          ) : (
            <div className="rounded-md border border-[#242a32] bg-[#0f1216] px-6 py-14">
              <div className="mx-auto max-w-lg text-center">
                <div className="mx-auto mb-5 flex h-10 w-10 items-center justify-center rounded-full border border-[#2f3742] bg-[#15191f] text-sm font-semibold text-[#8bdff0]">
                  R
                </div>
                <h2 className="text-lg font-semibold text-[#f5f7fa]">Start with a lore question</h2>
                <p className="mt-2 text-sm leading-6 text-[#9aa5b4]">
                  Try asking about a ruler, faction, location, conflict, or NPC. Results come from your uploaded
                  documents, not from a paid model.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {SAMPLE_QUERIES.slice(0, 3).map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => handleSearch(sample)}
                      className="rounded-full border border-[#2f3742] bg-[#15191f] px-3 py-1.5 text-xs text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
                    >
                      {sample}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-5">
          <section className="rounded-md border border-[#242a32] bg-[#0f1216] p-5">
            <h2 className="text-sm font-semibold text-[#f5f7fa]">Local retrieval</h2>
            <div className="mt-4 space-y-4 text-sm leading-6 text-[#9aa5b4]">
              <p>
                Query Studio searches local Chroma embeddings. It is zero-cost and citation-first, so results show
                source evidence before generation.
              </p>
              <div className="grid grid-cols-2 gap-3 border-t border-[#242a32] pt-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-[#7f8b9a]">Mode</div>
                  <div className="mt-1 font-medium text-[#f5f7fa]">Local demo</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-[#7f8b9a]">Cost</div>
                  <div className="mt-1 font-medium text-[#f5f7fa]">$0</div>
                </div>
              </div>
            </div>
          </section>

          {groupedSources.length > 0 && (
            <section className="rounded-md border border-[#242a32] bg-[#0f1216] p-5">
              <h2 className="text-sm font-semibold text-[#f5f7fa]">Sources used</h2>
              <div className="mt-4 space-y-3">
                {groupedSources.map((source) => (
                  <div key={source.title} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-[#dbe2ea]">{source.title}</span>
                    <span className="shrink-0 rounded-full border border-[#2f3742] px-2 py-0.5 text-xs text-[#9aa5b4]">
                      {source.count}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="rounded-md border border-[#242a32] bg-[#0f1216] p-5">
            <h2 className="text-sm font-semibold text-[#f5f7fa]">Recent questions</h2>
            <div className="mt-4 space-y-2">
              {history.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => handleSearch(item)}
                  className="block w-full rounded-md px-2 py-2 text-left text-sm leading-5 text-[#aab4c0] transition hover:bg-[#15191f] hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
                >
                  {item}
                </button>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}
