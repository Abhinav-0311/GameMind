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
  if (normalized.includes("high")) return "border-emerald-500/20 bg-emerald-500/10 text-emerald-800";
  if (normalized.includes("medium")) return "border-amber-500/20 bg-amber-500/10 text-amber-800";
  return "border-[var(--border-strong)] bg-[var(--card-muted)] text-[var(--text-secondary)]";
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
    <div className="page-shell space-y-10">
      <section className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-8">
          <div className="space-y-4">
            <div className="page-kicker">
              Lore Search
            </div>
            <div className="max-w-3xl space-y-3">
              <h1 className="display-title text-[2.05rem] leading-tight sm:text-[2.85rem]">
                Search the lore before you generate.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                Ask a direct question and inspect the cited source fragments. This keeps blueprints, NPCs, and quests
                grounded in the uploaded game document.
              </p>
            </div>
          </div>

          <form
            onSubmit={onSubmit}
            className="panel rounded-xl p-3"
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
                className="min-h-12 flex-1 rounded-lg border border-[var(--border-strong)] bg-[var(--card)] px-4 text-base text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/15"
              />

              <label className="sr-only" htmlFor="match-limit">
                Number of citations
              </label>
              <select
                id="match-limit"
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
                className="min-h-12 rounded-lg border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/15 sm:w-36"
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
                className="btn-primary min-h-12 rounded-lg px-6 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Searching" : "Search lore"}
              </button>
            </div>
          </form>

          {error && (
            <div className="rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="space-y-4">
              <div className="h-48 animate-pulse rounded-md border border-[var(--border)] bg-[var(--card)]" />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="h-32 animate-pulse rounded-md border border-[var(--border)] bg-[var(--card)]" />
                <div className="h-32 animate-pulse rounded-md border border-[var(--border)] bg-[var(--card)]" />
              </div>
            </div>
          ) : bestMatch ? (
            <div className="space-y-6">
              <section className="panel overflow-hidden rounded-xl">
                <div className="border-b border-[var(--border)] px-6 py-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                      <div className="mono-label text-[var(--text-secondary)]">
                        Best grounded match
                      </div>
                      <h2 className="font-display text-3xl font-semibold text-[var(--foreground)]">
                        {bestMatch.title}
                      </h2>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] px-3 py-1 text-xs font-medium text-[var(--foreground)]">
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
                  <p className="max-w-3xl text-lg leading-8 text-[var(--foreground)]">
                    {bestMatch.content}
                  </p>

                <div className="flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1">
                      Chunk {bestMatch.chunk_index + 1}
                    </span>
                    <span className="rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1">
                      {results.length} citations found
                    </span>
                    {message && (
                      <span className="rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1">
                        {message}
                      </span>
                    )}
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-[var(--foreground)]">Citations</h2>
                  <span className="text-xs text-[var(--text-secondary)]">Grounding for &quot;{query}&quot;</span>
                </div>

                <div className="space-y-3">
                  {results.map((result, index) => (
                    <article
                      key={result.chunk_id}
                      className="panel-muted rounded-xl px-5 py-4 transition hover:border-[var(--accent)]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-medium text-[var(--text-secondary)]">#{index + 1}</span>
                            <h3 className="truncate text-sm font-semibold text-[var(--foreground)]">{result.title}</h3>
                            <span className="text-xs text-[var(--text-secondary)]">Chunk {result.chunk_index + 1}</span>
                          </div>
                          <p className="line-clamp-3 text-sm leading-6 text-[var(--text-secondary)]">{result.content}</p>
                        </div>

                        <div className="flex shrink-0 items-center gap-2 text-xs">
                          <span className="font-medium text-[var(--foreground)]">{formatPercent(result.similarity)}</span>
                          <span className={`rounded-full border px-2.5 py-1 ${confidenceTone(result.confidence)}`}>
                            {result.confidence}
                          </span>
                        </div>
                      </div>

                  <details className="mt-3 border-t border-[var(--border)] pt-3">
                    <summary className="cursor-pointer text-xs font-medium text-[var(--accent)] outline-none transition hover:text-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]/30">
                          Citation metadata
                        </summary>
                        <div className="mt-3 grid gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
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
            <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-6 py-12 text-center">
              <h2 className="text-lg font-semibold text-[var(--foreground)]">No matching lore found</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Upload a GDD or lore document first, then ask a question that appears in the source material.
              </p>
            </div>
          ) : (
            <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-6 py-14">
              <div className="mx-auto max-w-lg text-center">
                <h2 className="text-lg font-semibold text-[var(--foreground)]">Start with a lore question</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  Try asking about a ruler, faction, location, conflict, or NPC. Results come from your uploaded
                  documents, not from an external paid provider.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {SAMPLE_QUERIES.slice(0, 3).map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => handleSearch(sample)}
                      className="rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] px-3 py-1.5 text-xs text-[var(--foreground)] transition hover:border-[var(--accent)]/50 hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
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
          <section className="panel rounded-xl p-5">
            <h2 className="font-display text-xl font-semibold tracking-[-0.01em] text-[var(--foreground)]">Why this matters</h2>
            <div className="mt-4 space-y-4 text-sm leading-6 text-[var(--text-secondary)]">
              <p>
                Lore Search is the trust check. If citations are weak, the generated blueprint will also be weak.
              </p>
              <div className="grid grid-cols-2 gap-3 border-t border-[var(--border)] pt-4">
                <div>
                  <div className="mono-label text-[var(--text-secondary)]">Mode</div>
                  <div className="mt-1 font-medium text-[var(--foreground)]">Local demo</div>
                </div>
                <div>
                  <div className="mono-label text-[var(--text-secondary)]">Paid API cost</div>
                  <div className="mt-1 font-medium text-[var(--foreground)]">$0</div>
                </div>
              </div>
            </div>
          </section>

          {groupedSources.length > 0 && (
            <section className="panel rounded-xl p-5">
            <h2 className="font-display text-xl font-semibold tracking-[-0.01em] text-[var(--foreground)]">Sources used</h2>
              <div className="mt-4 space-y-3">
                {groupedSources.map((source) => (
                  <div key={source.title} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-[var(--foreground)]">{source.title}</span>
                    <span className="shrink-0 rounded-full border border-[var(--border-strong)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                      {source.count}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="panel rounded-xl p-5">
            <h2 className="font-display text-xl font-semibold tracking-[-0.01em] text-[var(--foreground)]">Recent questions</h2>
            <div className="mt-4 space-y-2">
              {history.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => handleSearch(item)}
                  className="block w-full rounded-md px-2 py-2 text-left text-sm leading-5 text-[var(--text-secondary)] transition hover:bg-[var(--card-muted)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
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
