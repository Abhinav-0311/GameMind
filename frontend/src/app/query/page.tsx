"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { api, QueryResult } from "@/lib/api";

const SAMPLE_QUERIES = [
  "Who is King Arven?",
  "What caused the Ember Siege?",
  "Which faction controls Frostpeak?",
  "What should Eldrin remember?",
];

function confidenceTone(confidence: string) {
  const normalized = confidence.toLowerCase();
  if (normalized.includes("high")) return "border-emerald-500/25 bg-emerald-500/10 text-[var(--foreground)]";
  if (normalized.includes("medium")) return "border-amber-500/25 bg-amber-500/10 text-[var(--foreground)]";
  return "border-[var(--border)] bg-[var(--card-muted)] text-[var(--text-secondary)]";
}

function confidenceCopy(confidence?: string) {
  const normalized = (confidence || "").toLowerCase();
  if (normalized.includes("high")) return "Good grounding. This answer is safe to use as blueprint evidence.";
  if (normalized.includes("medium")) return "Usable, but review the cited chunks before generating from it.";
  if (confidence) return "Weak grounding. Improve the source document or ask a more specific question.";
  return "Ask a question to test whether your source material is ready.";
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
      if (process.env.NODE_ENV === "development") {
        console.warn("Lore search unavailable:", err);
      }
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
    <main className="page-shell">
      <section className="grid items-end gap-6 py-3 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-3xl">
          <p className="page-kicker">Lore Search</p>
          <h1 className="display-title mt-4 text-[2.15rem] leading-tight sm:text-[3rem]">
            Check the lore before you trust the output.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Ask a direct question and inspect cited source fragments. This keeps blueprints, NPCs, quests, and runtime
            behavior grounded in your uploaded documents.
          </p>
        </div>

        <aside className="panel-muted rounded-3xl p-5">
          <p className="page-kicker">Trust signal</p>
          <h2 className="mt-4 text-xl font-semibold text-[var(--foreground)]">
            {bestMatch ? `${bestMatch.confidence} confidence` : "No check yet"}
          </h2>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            {confidenceCopy(bestMatch?.confidence)}
          </p>
        </aside>
      </section>

      <section className="mt-8 panel rounded-3xl p-4 sm:p-5">
        <form onSubmit={onSubmit} className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_160px_150px]">
          <div>
            <label className="mb-2 block text-sm font-semibold text-[var(--foreground)]" htmlFor="lore-query">
              Lore question
            </label>
            <input
              id="lore-query"
              type="text"
              placeholder="Ask about characters, factions, locations, quests..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="min-h-12 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-4 text-base text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-[var(--foreground)]" htmlFor="match-limit">
              Citations
            </label>
            <select
              id="match-limit"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="min-h-12 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
            >
              {[3, 5, 8, 10].map((value) => (
                <option key={value} value={value}>
                  {value} matches
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="btn-primary min-h-12 w-full disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Searching" : "Search"}
            </button>
          </div>
        </form>

        <div className="mt-4 flex flex-wrap gap-2">
          {SAMPLE_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => handleSearch(sample)}
              className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            >
              {sample}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <section className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-[var(--foreground)]" role="alert">
          {error}
        </section>
      )}

      <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {loading ? (
            <LoadingState />
          ) : bestMatch ? (
            <>
              <section className="panel overflow-hidden rounded-3xl">
                <div className="border-b border-[var(--border)] p-6">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="page-kicker">Best match</p>
                      <h2 className="mt-3 text-2xl font-semibold tracking-normal text-[var(--foreground)]">{bestMatch.title}</h2>
                      <p className="mt-2 text-sm text-[var(--text-secondary)]">Answer evidence for &quot;{query}&quot;</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold text-[var(--foreground)]">
                        {formatPercent(bestMatch.similarity)} match
                      </span>
                      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${confidenceTone(bestMatch.confidence)}`}>
                        {bestMatch.confidence} confidence
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  <p className="max-w-4xl text-lg leading-8 text-[var(--foreground)]">{bestMatch.content}</p>

                  <div className="mt-5 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1">
                      Chunk {bestMatch.chunk_index + 1}
                    </span>
                    <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1">
                      {results.length} citations found
                    </span>
                    {message && (
                      <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1">
                        {message}
                      </span>
                    )}
                  </div>

                  <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                    <Link href="/blueprints" className="btn-primary">
                      Use source in Blueprint
                    </Link>
                    <Link href="/knowledge" className="btn-secondary">
                      Improve sources
                    </Link>
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="page-kicker">Citations</p>
                    <h2 className="mt-2 text-2xl font-semibold text-[var(--foreground)]">Evidence found</h2>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)]">{results.length} cited fragments</p>
                </div>

                <div className="grid gap-3">
                  {results.map((result, index) => (
                    <CitationCard key={result.chunk_id} result={result} index={index} />
                  ))}
                </div>
              </section>
            </>
          ) : searched ? (
            <section className="panel rounded-3xl px-6 py-16 text-center">
              <p className="page-kicker">No match</p>
              <h2 className="mt-4 text-2xl font-semibold text-[var(--foreground)]">No matching lore found.</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Upload a source document, ask a more specific question, or add more detail to the GDD before generating.
              </p>
              <Link href="/knowledge" className="btn-primary mt-5">
                Add source
              </Link>
            </section>
          ) : (
            <section className="panel rounded-3xl px-6 py-16 text-center">
              <p className="page-kicker">Ready</p>
              <h2 className="mt-4 text-2xl font-semibold text-[var(--foreground)]">Ask one precise lore question.</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Start with a ruler, faction, location, conflict, or NPC memory. Results come from local indexed source
                chunks, not a paid model.
              </p>
            </section>
          )}
        </div>

        <aside className="space-y-5">
          <section className="panel-muted rounded-3xl p-5">
            <p className="page-kicker">How to read results</p>
            <div className="mt-4 space-y-4 text-sm leading-6 text-[var(--text-secondary)]">
              <p>
                Use this page before generation. If the system cannot cite the fact, the blueprint should not invent it.
              </p>
              <div className="grid grid-cols-2 gap-3 border-t border-[var(--border)] pt-4">
                <Fact label="Mode" value="Local demo" />
                <Fact label="API cost" value="$0" />
              </div>
            </div>
          </section>

          {groupedSources.length > 0 && (
            <section className="panel rounded-3xl p-5">
              <p className="page-kicker">Sources used</p>
              <div className="mt-4 space-y-3">
                {groupedSources.map((source) => (
                  <div key={source.title} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate font-semibold text-[var(--foreground)]">{source.title}</span>
                    <span className="shrink-0 rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                      {source.count}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="panel rounded-3xl p-5">
            <p className="page-kicker">Recent questions</p>
            <div className="mt-4 space-y-2">
              {history.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => handleSearch(item)}
                  className="block min-h-10 w-full rounded-xl px-3 py-2 text-left text-sm leading-5 text-[var(--text-secondary)] transition hover:bg-[var(--card-muted)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  {item}
                </button>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function CitationCard({ result, index }: { result: QueryResult; index: number }) {
  return (
    <article className="panel-muted rounded-2xl p-5 transition hover:border-[var(--accent)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="page-kicker">#{index + 1}</span>
            <h3 className="truncate text-base font-semibold text-[var(--foreground)]">{result.title}</h3>
            <span className="text-xs text-[var(--text-secondary)]">Chunk {result.chunk_index + 1}</span>
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-[var(--text-secondary)]">{result.content}</p>
        </div>

        <div className="flex shrink-0 items-center gap-2 text-xs">
          <span className="font-semibold text-[var(--foreground)]">{formatPercent(result.similarity)}</span>
          <span className={`rounded-full border px-2.5 py-1 font-semibold ${confidenceTone(result.confidence)}`}>
            {result.confidence}
          </span>
        </div>
      </div>

      <details className="mt-4 border-t border-[var(--border)] pt-3">
        <summary className="cursor-pointer text-xs font-semibold text-[var(--accent)] outline-none transition hover:text-[var(--accent-hover)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
          Technical metadata
        </summary>
        <div className="mt-3 grid gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
          <div className="break-all">Document ID: {result.document_id}</div>
          <div className="break-all">Vector ID: {result.chunk_id}</div>
        </div>
      </details>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="page-kicker">{label}</p>
      <p className="mt-1 font-semibold text-[var(--foreground)]">{value}</p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="h-56 animate-pulse rounded-3xl border border-[var(--border)] bg-[var(--card)]" />
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="h-36 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--card)]" />
        <div className="h-36 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--card)]" />
      </div>
    </div>
  );
}
