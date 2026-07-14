"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api, DocumentDetailResponse, DocumentResponse } from "@/lib/api";
import { asSourceKind, sourceKindMeta, sourceKinds } from "@/lib/sourceKinds";

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
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceGroupKey(document: DocumentResponse) {
  return document.source_document_id || document.id;
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
  const [revising, setRevising] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [savingSourceKind, setSavingSourceKind] = useState(false);
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const [uploadSourceKind, setUploadSourceKind] = useState("gdd");
  const [reviewReadyId, setReviewReadyId] = useState<string | null>(null);
  const handledTrace = useRef<string | null>(null);

  const sourceGroups = useMemo(() => groupSources(documents), [documents]);
  const totalChunks = useMemo(() => documents.reduce((sum, doc) => sum + doc.chunks_count, 0), [documents]);
  const visibleChunks = useMemo(() => {
    if (!selectedDoc) return [];
    const initialChunks = selectedDoc.chunks.slice(0, 6);
    const targetChunk = highlightedChunkId ? selectedDoc.chunks.find((chunk) => chunk.id === highlightedChunkId) : undefined;
    if (!targetChunk || initialChunks.some((chunk) => chunk.id === targetChunk.id)) return initialChunks;
    return [targetChunk, ...initialChunks].slice(0, 6);
  }, [highlightedChunkId, selectedDoc]);

  const handleViewDetails = useCallback(async (id: string) => {
    setLoadingDetail(true);
    setError(null);

    try {
      const detail = await api.getDocument(id);
      setSelectedDoc(detail);
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        console.warn("Could not load selected source:", err);
      }
      setError("Could not load the selected source.");
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
      if (process.env.NODE_ENV === "development") {
        console.warn("Could not load source library:", err);
      }
      setError("Could not load sources. Start Docker and refresh this page.");
    } finally {
      setLoadingList(false);
    }
  }, [handleViewDetails, selectedDoc]);

  useEffect(() => {
    Promise.resolve().then(fetchDocuments);
  }, [fetchDocuments]);

  useEffect(() => {
    if (!documents.length || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const documentId = params.get("document");
    const chunkId = params.get("chunk");
    if (!documentId || !documents.some((document) => document.id === documentId)) return;
    const traceKey = `${documentId}:${chunkId || ""}`;
    if (handledTrace.current === traceKey) return;
    handledTrace.current = traceKey;

    Promise.resolve().then(async () => {
      setHighlightedChunkId(chunkId);
      await handleViewDetails(documentId);
    });
  }, [documents, handleViewDetails]);

  useEffect(() => {
    if (!highlightedChunkId || selectedDoc?.id === undefined) return;
    document.getElementById(`source-chunk-${highlightedChunkId}`)?.scrollIntoView({ block: "nearest" });
  }, [highlightedChunkId, selectedDoc?.id]);

  const handleFileUpload = async (file: File) => {
    setError(null);
    setSuccessMsg(null);

    if (file.size > MAX_FILE_SIZE) {
      setError(`${file.name} is ${formatFileSize(file.size)}. The current limit is 5 MB.`);
      return;
    }

    setUploading(true);

    try {
      const newDoc = await api.uploadDocument(file, uploadSourceKind);
      setReviewReadyId(newDoc.id);
      setSuccessMsg(`${file.name} was indexed as ${sourceKindMeta[asSourceKind(newDoc.source_kind)].label}. Review it before generating a blueprint.`);
      await fetchDocuments();
      await handleViewDetails(newDoc.id);
    } catch (err) {
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

  const handleRevisionUpload = async (file: File) => {
    if (!selectedDoc) return;
    setError(null);
    setSuccessMsg(null);

    if (file.size > MAX_FILE_SIZE) {
      setError(`${file.name} is ${formatFileSize(file.size)}. The current limit is 5 MB.`);
      return;
    }

    setRevising(true);
    try {
      const revised = await api.uploadDocumentRevision(selectedDoc.id, file);
      setSuccessMsg(`${file.name} is indexed as revision ${revised.revision_number}. Generate a new blueprint to compare it with the earlier plan.`);
      await fetchDocuments();
      await handleViewDetails(revised.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload the source revision.");
    } finally {
      setRevising(false);
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
      if (process.env.NODE_ENV === "development") {
        console.warn("Could not delete source:", err);
      }
      setError("Could not delete the selected source.");
    }
  };

  const handleLoadDemo = async () => {
    setLoadingDemo(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const demoDoc = await api.loadFrostpeakDemoDocument();
      setReviewReadyId(demoDoc.id);
      setSuccessMsg("Frostpeak demo GDD is indexed. Review it before generating a blueprint.");
      await fetchDocuments();
      await handleViewDetails(demoDoc.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the Frostpeak demo document.");
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleSourceKindChange = async (sourceKind: string) => {
    if (!selectedDoc) return;
    setSavingSourceKind(true);
    setError(null);
    try {
      const updated = await api.updateDocumentSourceKind(selectedDoc.id, sourceKind);
      setDocuments((current) => current.map((document) => (document.id === updated.id ? updated : document)));
      setSelectedDoc((current) => current && current.id === updated.id ? { ...current, source_kind: updated.source_kind } : current);
      setSuccessMsg("Source type updated. Blueprint impact guidance is refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update source type.");
    } finally {
      setSavingSourceKind(false);
    }
  };

  return (
    <main className="page-shell">
      <section className="grid items-end gap-6 py-3 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-3xl">
          <p className="page-kicker">Sources</p>
          <h1 className="display-title mt-4 text-[2.15rem] leading-tight sm:text-[3rem]">
            Start with source truth.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Upload a GDD, lore brief, NPC sheet, quest outline, or level notes. GameMind indexes the file so every
            blueprint and lore answer can point back to evidence.
          </p>
        </div>

        <div className="panel-muted rounded-3xl p-5">
          <p className="page-kicker">Library</p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Fact label="Sources" value={loadingList ? "--" : String(sourceGroups.length)} />
            <Fact label="Chunks" value={loadingList ? "--" : String(totalChunks)} />
          </div>
        </div>
      </section>

      {(error || successMsg) && (
        <section
          className={`mt-6 rounded-2xl border px-4 py-3 text-sm ${
            error
              ? "border-amber-500/30 bg-amber-500/10 text-[var(--foreground)]"
              : "border-emerald-500/25 bg-emerald-500/10 text-[var(--foreground)]"
          }`}
          role={error ? "alert" : "status"}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{error || successMsg}</span>
            {!error && reviewReadyId && (
              <Link href={`/decisions?document=${reviewReadyId}`} className="btn-secondary shrink-0">
                Review this source
              </Link>
            )}
          </div>
        </section>
      )}

      <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`panel rounded-3xl p-6 transition ${
            dragOver ? "border-[var(--accent)] bg-[var(--accent-soft)]" : ""
          }`}
        >
          <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <p className="page-kicker">Add source</p>
              <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[var(--foreground)]">
                Drop a game document here.
              </h2>
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                Supported for the MVP: TXT, Markdown, and PDF under 5 MB. Identical source text is kept out of the
                index, even when the file has a different name.
              </p>
            </div>

            <div className="w-full space-y-3 lg:w-[22rem]">
              <div>
                <label htmlFor="upload-source-kind" className="text-sm font-semibold text-[var(--foreground)]">
                  This source is a
                </label>
                <select
                  id="upload-source-kind"
                  value={uploadSourceKind}
                  disabled={uploading || loadingDemo}
                  onChange={(event) => setUploadSourceKind(event.target.value)}
                  className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {sourceKinds.map((kind) => <option key={kind} value={kind}>{sourceKindMeta[kind].label}</option>)}
                </select>
                <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                  {sourceKindMeta[asSourceKind(uploadSourceKind)].description}
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo || uploading}
                className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading demo" : "Load Frostpeak demo"}
              </button>
              <label
                className={`inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-xl px-4 text-sm font-semibold transition focus-within:ring-2 focus-within:ring-[var(--accent)] focus-within:ring-offset-2 focus-within:ring-offset-[var(--card)] ${
                  uploading
                    ? "bg-[var(--border-strong)] text-[var(--text-tertiary)]"
                    : "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
                }`}
              >
                {uploading ? "Uploading" : "Choose file"}
                <input
                  type="file"
                  className="sr-only"
                  accept=".txt,.md,.pdf"
                  disabled={uploading}
                  onChange={handleFileChange}
                />
              </label>
              </div>
            </div>
          </div>
        </div>

        <aside className="panel-muted rounded-3xl p-6">
          <p className="page-kicker">Why this matters</p>
          <h2 className="mt-4 text-xl font-semibold text-[var(--foreground)]">Good source creates useful output.</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            A weak GDD gives generic blueprints. A clear source lets GameMind cite lore, extract NPCs, propose quests,
            and build runtime data that stays consistent.
          </p>
        </aside>
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel overflow-hidden rounded-3xl">
          <div className="flex flex-col gap-4 border-b border-[var(--border)] p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="page-kicker">Indexed library</p>
              <h2 className="mt-3 text-2xl font-semibold text-[var(--foreground)]">Uploaded sources</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                Repeated uploads are grouped by title. Select one to inspect its indexed chunks.
              </p>
            </div>
            <button type="button" onClick={fetchDocuments} className="btn-secondary shrink-0">
              Refresh
            </button>
          </div>

          {loadingList ? (
            <div className="space-y-3 p-5">
              {[1, 2, 3].map((item) => (
                <div key={item} className="h-20 animate-pulse rounded-2xl bg-[var(--card-muted)]" />
              ))}
            </div>
          ) : sourceGroups.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="page-kicker">Empty state</p>
              <h3 className="mt-4 text-2xl font-semibold text-[var(--foreground)]">No source documents yet.</h3>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Load Frostpeak or upload your own notes to begin the GameMind workflow.
              </p>
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo}
                className="btn-primary mt-5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading demo" : "Load Frostpeak demo"}
              </button>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {sourceGroups.map((source) => {
                const selected = Boolean(selectedDoc && source.documents.some((doc) => doc.id === selectedDoc.id));
                const hasRevisions = source.documents.length > 1;

                return (
                  <article
                    key={source.key}
                    className={`grid gap-4 px-5 py-4 transition sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${
                      selected ? "bg-[var(--card-muted)]" : "hover:bg-[var(--card-muted)]"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleViewDetails(source.latest.id)}
                      className="min-w-0 text-left focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                    >
                      <p className="truncate text-base font-semibold text-[var(--foreground)]">{source.title}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                        <span>{source.latest.chunks_count} latest chunks</span>
                        <span>{source.totalChunks} total chunks</span>
                        <span>Latest {formatDate(source.latest.created_at)}</span>
                        <span>{sourceKindMeta[asSourceKind(source.latest.source_kind)].label}</span>
                      </div>
                    </button>

                    <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                      {hasRevisions && (
                        <span className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                          {source.documents.length} revisions
                        </span>
                      )}
                      <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-[var(--foreground)]">
                        Indexed
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteDoc(source.latest.id, source.latest.title)}
                        className="rounded-xl px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-rose-500/10 hover:text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500/30"
                      >
                        Delete latest
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside className="panel overflow-hidden rounded-3xl">
          <div className="border-b border-[var(--border)] p-6">
            <p className="page-kicker">Inspect</p>
            <h2 className="mt-3 text-2xl font-semibold text-[var(--foreground)]">Source chunks</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              These fragments are what GameMind can cite during lore search and blueprint generation.
            </p>
          </div>

          <div className="max-h-[40rem] overflow-y-auto p-5">
            {loadingDetail ? (
              <div className="space-y-3">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-24 animate-pulse rounded-2xl bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : selectedDoc ? (
              <div className="space-y-5">
                <div>
                  <p className="truncate text-sm font-semibold text-[var(--foreground)]">{selectedDoc.title}</p>
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">Revision {selectedDoc.revision_number} · {selectedDoc.chunks_count} indexed chunks</p>
                </div>

                <div className="border-y border-[var(--border)] py-4">
                  <label htmlFor="source-kind" className="text-sm font-semibold text-[var(--foreground)]">Source type</label>
                  <select
                    id="source-kind"
                    value={asSourceKind(selectedDoc.source_kind)}
                    disabled={savingSourceKind}
                    onChange={(event) => handleSourceKindChange(event.target.value)}
                    className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sourceKinds.map((kind) => <option key={kind} value={kind}>{sourceKindMeta[kind].label}</option>)}
                  </select>
                  <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{sourceKindMeta[asSourceKind(selectedDoc.source_kind)].description}</p>
                  <p className="mt-3 text-xs font-semibold text-[var(--text-secondary)]">Can improve: {sourceKindMeta[asSourceKind(selectedDoc.source_kind)].impact.join(" · ")}</p>
                </div>

                <div className="space-y-3">
                  {visibleChunks.map((chunk) => (
                    <div
                      id={`source-chunk-${chunk.id}`}
                      key={chunk.id}
                      className={`rounded-2xl p-4 ${chunk.id === highlightedChunkId ? "border border-[var(--accent)] bg-[var(--accent-soft)]" : "panel-muted"}`}
                    >
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <p className="page-kicker">Chunk {chunk.chunk_index + 1}</p>
                        <span className="text-xs text-[var(--text-secondary)]">{chunk.content.length} chars</span>
                      </div>
                      <p className="line-clamp-6 text-sm leading-6 text-[var(--text-secondary)]">{chunk.content}</p>
                    </div>
                  ))}
                </div>

                <Link href="/blueprints" className="btn-primary w-full">
                  Generate blueprint
                </Link>
                <label className={`inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-xl border border-[var(--border)] px-4 text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] focus-within:ring-2 focus-within:ring-[var(--accent)] focus-within:ring-offset-2 focus-within:ring-offset-[var(--card)] ${
                  revising ? "cursor-not-allowed opacity-50" : ""
                }`}>
                  {revising ? "Indexing revision" : "Upload revision"}
                  <input
                    type="file"
                    className="sr-only"
                    accept=".txt,.md,.pdf"
                    disabled={revising}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) handleRevisionUpload(file);
                      event.target.value = "";
                    }}
                  />
                </label>
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
    </main>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="page-kicker">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-[var(--foreground)]">{value}</p>
    </div>
  );
}
