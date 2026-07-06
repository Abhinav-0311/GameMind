"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, DocumentDetailResponse, DocumentResponse } from "@/lib/api";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

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

  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + doc.chunks_count, 0),
    [documents]
  );

  const latestDocuments = useMemo(
    () =>
      [...documents].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      ),
    [documents]
  );

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
              Knowledge Base
            </div>
            <div className="space-y-3">
              <h1 className="display-title text-[2.65rem] leading-tight sm:text-6xl">
                Start with the game documents.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[#9aa5b4]">
                Upload a GDD, lore brief, NPC sheet, quest outline, or level notes. GameMind chunks and indexes the
                source so Blueprint Studio and Query Studio can use it without paid API calls.
              </p>
            </div>
          </div>

          <Link
            href="/blueprints"
            className="inline-flex min-h-10 items-center rounded-md border border-[#2f3742] px-4 text-sm font-semibold text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
          >
            Open Blueprint Studio
          </Link>
        </div>

        {(error || successMsg) && (
          <div
            className={`rounded-md border px-4 py-3 text-sm ${
              error
                ? "border-rose-500/25 bg-rose-500/10 text-rose-200"
                : "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
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
              ? "border-[#8bdff0] bg-[#111922]"
              : "panel"
          }`}
        >
          <div className="grid gap-6 lg:grid-cols-[1fr_280px] lg:items-center">
            <div className="space-y-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[#2f3742] bg-[#15191f] text-sm font-semibold text-[#8bdff0]">
                GDD
              </div>
              <div className="space-y-2">
                <h2 className="font-display text-3xl font-semibold text-[#f5f7fa]">
                  {uploading ? "Indexing source material" : "Drop your game design document here"}
                </h2>
                <p className="max-w-2xl text-sm leading-6 text-[#9aa5b4]">
                  Supported formats: TXT, Markdown, and PDF. Keep files under 5 MB for this MVP.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo || uploading}
                className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-[#8bdff0]/40 bg-[#8bdff0]/10 text-sm font-semibold text-[#b7eef7] transition hover:border-[#8bdff0] hover:bg-[#8bdff0]/15 focus:outline-none focus:ring-2 focus:ring-[#8bdff0] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading Frostpeak" : "Load Frostpeak demo"}
              </button>
              <label
                className={`inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-md text-sm font-semibold transition focus-within:ring-2 focus-within:ring-[#f5f7fa] focus-within:ring-offset-2 focus-within:ring-offset-[#090b0e] ${
                  uploading
                    ? "bg-[#252b34] text-[#66717f]"
                    : "bg-[#f5f7fa] text-[#090b0e] hover:bg-white"
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
              <p className="text-center text-xs leading-5 text-[#7f8b9a]">
                Start with the bundled sample, or upload your own GDD.
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {[
            ["Documents", loadingList ? "--" : String(documents.length)],
            ["Searchable chunks", loadingList ? "--" : String(totalChunks)],
            ["AI cost", "$0 local"],
          ].map(([label, value]) => (
            <div key={label} className="panel-muted rounded-xl p-4">
              <div className="mono-label text-[#7f8b9a]">{label}</div>
              <div className="mt-3 text-2xl font-semibold tracking-tight text-[#f5f7fa]">{value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <main className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="font-display text-2xl font-semibold text-[#f5f7fa]">Source library</h2>
              <p className="mt-1 text-sm leading-6 text-[#9aa5b4]">
                These documents can power lore search and blueprint generation.
              </p>
            </div>
            <button
              type="button"
              onClick={fetchDocuments}
              className="inline-flex min-h-10 items-center rounded-md border border-[#2f3742] px-4 text-sm font-semibold text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
            >
              Refresh
            </button>
          </div>

          <div className="panel overflow-hidden rounded-xl">
            {loadingList ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-20 animate-pulse rounded-md bg-[#15191f]" />
                ))}
              </div>
            ) : latestDocuments.length === 0 ? (
              <div className="px-6 py-14 text-center">
              <h3 className="text-lg font-semibold text-[#f5f7fa]">No sources uploaded</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#9aa5b4]">
                Upload the Frostpeak sample GDD or your own notes to begin the full GameMind flow.
              </p>
              <button
                type="button"
                onClick={handleLoadDemo}
                disabled={loadingDemo}
                className="mt-5 inline-flex min-h-10 items-center justify-center rounded-md bg-[#f5f7fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa] focus:ring-offset-2 focus:ring-offset-[#101419] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingDemo ? "Loading demo" : "Load Frostpeak demo"}
              </button>
            </div>
            ) : (
              <div className="divide-y divide-[#20262e]">
                {latestDocuments.map((doc) => {
                  const selected = selectedDoc?.id === doc.id;

                  return (
                    <article
                      key={doc.id}
                      className={`grid gap-4 px-5 py-4 transition sm:grid-cols-[1fr_auto] sm:items-center ${
                        selected ? "bg-[#15191f]" : "hover:bg-[#121820]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => handleViewDetails(doc.id)}
                        className="min-w-0 text-left focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
                      >
                        <div className="truncate text-sm font-semibold text-[#f5f7fa]">{doc.title}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#7f8b9a]">
                          <span>{doc.chunks_count} chunks</span>
                          <span>Indexed {formatDate(doc.created_at)}</span>
                          <span>{doc.content_type}</span>
                        </div>
                      </button>

                      <div className="flex items-center gap-3">
                        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-300">
                          Ready
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDeleteDoc(doc.id, doc.title)}
                          className="rounded-md px-2 py-1 text-xs font-semibold text-[#7f8b9a] transition hover:bg-rose-500/10 hover:text-rose-300 focus:outline-none focus:ring-2 focus:ring-rose-500/30"
                        >
                          Delete
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
          <div className="border-b border-[#242a32] p-5">
            <h2 className="font-display text-2xl font-semibold text-[#f5f7fa]">Chunk preview</h2>
            <p className="mt-2 text-sm leading-6 text-[#9aa5b4]">
              Inspect the fragments available for local retrieval and blueprint citations.
            </p>
          </div>

          <div className="max-h-[38rem] overflow-y-auto p-5">
            {loadingDetail ? (
              <div className="space-y-3">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-24 animate-pulse rounded-md bg-[#15191f]" />
                ))}
              </div>
            ) : selectedDoc ? (
              <div className="space-y-5">
                <div>
                  <div className="truncate text-sm font-semibold text-[#f5f7fa]">{selectedDoc.title}</div>
                  <div className="mt-2 text-xs text-[#7f8b9a]">{selectedDoc.chunks_count} indexed chunks</div>
                </div>

                <div className="space-y-3">
                  {selectedDoc.chunks.slice(0, 6).map((chunk) => (
                    <div key={chunk.id} className="panel-muted rounded-xl p-4">
                      <div className="mono-label mb-3 flex items-center justify-between text-[#7f8b9a]">
                        <span>Chunk {chunk.chunk_index + 1}</span>
                        <span>{chunk.content.length} chars</span>
                      </div>
                      <p className="line-clamp-6 text-sm leading-6 text-[#aab4c0]">{chunk.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex min-h-56 items-center justify-center text-center">
                <p className="max-w-xs text-sm leading-6 text-[#7f8b9a]">
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
