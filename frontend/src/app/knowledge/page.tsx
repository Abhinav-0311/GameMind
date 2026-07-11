"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, DocumentDetailResponse, DocumentResponse } from "@/lib/api";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

interface SourceGroup {
  key: string;
  title: string;
  contentType: string;
  latest: DocumentResponse;
  documents: DocumentResponse[];
  totalChunks: number;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceGroupKey(document: DocumentResponse) {
  return `${document.title.trim().toLowerCase()}::${document.content_type}`;
}

function groupSources(documents: DocumentResponse[]): SourceGroup[] {
  const groups = new Map<string, DocumentResponse[]>();

  documents.forEach((document) => {
    const key = sourceGroupKey(document);
    groups.set(key, [...(groups.get(key) || []), document]);
  });

  return Array.from(groups.entries())
    .map(([key, groupDocuments]) => {
      const sorted = [...groupDocuments].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      const latest = sorted[0];

      return {
        key,
        title: latest.title,
        contentType: latest.content_type,
        latest,
        documents: sorted,
        totalChunks: sorted.reduce((sum, document) => sum + document.chunks_count, 0),
      };
    })
    .sort((a, b) => new Date(b.latest.created_at).getTime() - new Date(a.latest.created_at).getTime());
}

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetailResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const sourceGroups = useMemo(() => groupSources(documents), [documents]);

  const handleViewDetails = useCallback(async (id: string) => {
    setLoadingDetail(true);
    setError(null);

    try {
      const detail = await api.getDocument(id);
      setSelectedDoc(detail);
    } catch (err) {
      console.error(err);
      setError("Could not load the selected document.");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    setLoadingList(true);

    try {
      const docs = await api.getDocuments();
      setDocuments(docs);

      if (docs.length === 0) {
        setSelectedDoc(null);
        return;
      }

      const selectedStillExists = selectedDoc && docs.some((doc) => doc.id === selectedDoc.id);
      if (!selectedStillExists) {
        await handleViewDetails(docs[0].id);
      }
    } catch (err) {
      console.error(err);
      setError("Could not load the knowledge library.");
    } finally {
      setLoadingList(false);
    }
  }, [handleViewDetails, selectedDoc]);

  useEffect(() => {
    Promise.resolve().then(fetchDocuments);
  }, [fetchDocuments]);

  const handleFileUpload = async (file: File) => {
    setError(null);
    setSuccessMsg(null);

    if (file.size > MAX_FILE_SIZE) {
      setError(`${file.name} is ${formatFileSize(file.size)}. The current limit is 5 MB.`);
      return;
    }

    setUploading(true);

    try {
      const newDoc = await api.uploadDocument(file);
      setSuccessMsg(`${file.name} was uploaded, chunked, and indexed.`);
      await fetchDocuments();
      await handleViewDetails(newDoc.id);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Document upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileUpload(file);
      event.target.value = "";
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);

    const file = event.dataTransfer.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDeleteDoc = async (id: string, title: string) => {
    if (!confirm(`Delete "${title}" from the knowledge base?`)) return;

    setError(null);
    setSuccessMsg(null);

    try {
      await api.deleteDocument(id);
      setSuccessMsg(`${title} was removed.`);
      await fetchDocuments();
    } catch (err) {
      console.error(err);
      setError("Could not delete the document.");
    }
  };

  const handleLoadDemo = async () => {
    setLoadingDemo(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const demoDoc = await api.loadFrostpeakDemoDocument();
      setSuccessMsg("Frostpeak demo GDD is ready. Generate a blueprint from it next.");
      await fetchDocuments();
      await handleViewDetails(demoDoc.id);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Could not load the Frostpeak demo document.");
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div className="page-shell space-y-10">
      <section className="space-y-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <div className="page-kicker">
              Sources
            </div>
            <div className="space-y-3">
              <h1 className="display-title text-[2.05rem] leading-tight sm:text-[2.85rem]">
                Upload the source of truth.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                Add a GDD, lore brief, NPC sheet, quest outline, or level notes. GameMind turns the document into
                searchable source evidence for blueprints, lore answers, and runtime tests.
              </p>
            </div>
          </div>

          <Link
            href="/blueprints"
            className="btn-secondary"
          >
            Continue to Blueprints
          </Link>
        </div>

        {(error || successMsg) && (
          <div
            className={`rounded-md border px-4 py-3 text-sm ${
              error
                ? "border-rose-500/25 bg-rose-500/10 text-rose-700"
                : "border-emerald-500/25 bg-emerald-500/10 text-emerald-800"
            }`}
          >
            {error || successMsg}
          </div>
        )}

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`rounded-md border p-6 transition ${
            dragOver
              ? "border-[var(--accent)] bg-[var(--accent-soft)]"
              : "panel"
          }`}
        >
          <div className="grid gap-6 lg:grid-cols-[1fr_280px] lg:items-center">
            <div className="space-y-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] text-sm font-semibold text-[var(--accent)]">
                GDD
              </div>
              <div className="space-y-2">
                <h2 className="font-display text-[1.65rem] font-semibold tracking-[-0.01em] text-[var(--foreground)]">
                  {uploading ? "Indexing source material" : "Drop your game document here"}
                </h2>
                <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                  Supported formats: TXT, Markdown, and PDF. Keep files under 5 MB for this MVP.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo || uploading}
                className="btn-secondary w-full disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading Frostpeak" : "Load Frostpeak demo"}
              </button>
              <label
                  className={`inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-xl text-sm font-semibold transition focus-within:ring-2 focus-within:ring-[var(--accent)] focus-within:ring-offset-2 focus-within:ring-offset-[var(--card)] ${
                  uploading
                    ? "bg-[var(--border-strong)] text-[var(--text-tertiary)]"
                    : "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
                }`}
              >
                {uploading ? "Uploading" : "Choose your own file"}
                <input
                  type="file"
                  className="sr-only"
                  accept=".txt,.md,.pdf"
                  disabled={uploading}
                  onChange={handleFileChange}
                />
              </label>
              <p className="text-center text-xs leading-5 text-[var(--text-secondary)]">
                Start with the bundled sample, or upload your own GDD.
              </p>
            </div>
          </div>
        </div>

      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <main className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="font-display text-xl font-semibold tracking-[-0.01em] text-[var(--foreground)]">Uploaded sources</h2>
              <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                Repeated uploads are grouped by title. Use the latest copy for generation, or delete it if it was a test.
              </p>
            </div>
            <button
              type="button"
              onClick={fetchDocuments}
              className="btn-secondary min-h-10"
            >
              Refresh
            </button>
          </div>

          <div className="panel overflow-hidden rounded-xl">
            {loadingList ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-20 animate-pulse rounded-md bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : sourceGroups.length === 0 ? (
              <div className="px-6 py-14 text-center">
              <h3 className="text-lg font-semibold text-[var(--foreground)]">No sources uploaded</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Upload the Frostpeak sample GDD or your own notes to begin the full GameMind flow.
              </p>
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo}
                className="btn-primary mt-5 min-h-10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading demo" : "Load Frostpeak demo"}
              </button>
            </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {sourceGroups.map((source) => {
                  const selected = Boolean(selectedDoc && source.documents.some((doc) => doc.id === selectedDoc.id));
                  const hasCopies = source.documents.length > 1;

                  return (
                    <article
                      key={source.key}
                      className={`grid gap-4 px-5 py-4 transition sm:grid-cols-[1fr_auto] sm:items-center ${
                        selected ? "bg-[var(--card-muted)]" : "hover:bg-[var(--card-muted)]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => handleViewDetails(source.latest.id)}
                        className="min-w-0 text-left focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
                      >
                        <div className="truncate text-sm font-semibold text-[var(--foreground)]">{source.title}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                          <span>{source.latest.chunks_count} chunks in latest</span>
                          <span>{source.totalChunks} total chunks</span>
                          <span>Latest {formatDate(source.latest.created_at)}</span>
                          <span>{source.contentType}</span>
                        </div>
                      </button>

                      <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                        {hasCopies && (
                          <span className="rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                            {source.documents.length} copies
                          </span>
                        )}
                        <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-[var(--foreground)]">
                          Ready
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDeleteDoc(source.latest.id, source.latest.title)}
                          className="rounded-md px-2 py-1 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-rose-500/10 hover:text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500/30"
                        >
                          Delete latest
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        </main>

        <aside className="panel overflow-hidden rounded-xl">
          <div className="border-b border-[var(--border)] p-5">
            <h2 className="font-display text-xl font-semibold tracking-[-0.01em] text-[var(--foreground)]">Source preview</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              These are the source fragments GameMind can cite while generating plans and runtime behavior.
            </p>
          </div>

          <div className="max-h-[38rem] overflow-y-auto p-5">
            {loadingDetail ? (
              <div className="space-y-3">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-24 animate-pulse rounded-md bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : selectedDoc ? (
              <div className="space-y-5">
                <div>
                  <div className="truncate text-sm font-semibold text-[var(--foreground)]">{selectedDoc.title}</div>
                  <div className="mt-2 text-xs text-[var(--text-secondary)]">{selectedDoc.chunks_count} indexed chunks</div>
                </div>

                <div className="space-y-3">
                  {selectedDoc.chunks.slice(0, 6).map((chunk) => (
                    <div key={chunk.id} className="panel-muted rounded-xl p-4">
                      <div className="mono-label mb-3 flex items-center justify-between text-[var(--text-secondary)]">
                        <span>Chunk {chunk.chunk_index + 1}</span>
                        <span>{chunk.content.length} chars</span>
                      </div>
                      <p className="line-clamp-6 text-sm leading-6 text-[var(--text-secondary)]">{chunk.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex min-h-56 items-center justify-center text-center">
                <p className="max-w-xs text-sm leading-6 text-[var(--text-secondary)]">
                  Select a source document to inspect its generated chunks.
                </p>
              </div>
            )}
          </div>
        </aside>
      </section>
    </div>
  );
}
