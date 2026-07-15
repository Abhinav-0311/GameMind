"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { api, type DecisionCoverageResponse, type DesignDecision, type DocumentResponse } from "@/lib/api";

function decisionTone(decision: DesignDecision) {
  if (decision.status === "resolved") return "border-emerald-500/35";
  if (decision.severity === "conflict") return "border-amber-500";
  return "border-[var(--accent)]";
}

export default function DecisionsPage() {
  return (
    <Suspense fallback={<DecisionsLoadingState />}>
      <DecisionsContent />
    </Suspense>
  );
}

function DecisionsContent() {
  const searchParams = useSearchParams();
  const requestedDocumentId = searchParams.get("document");
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [decisions, setDecisions] = useState<DesignDecision[]>([]);
  const [coverage, setCoverage] = useState<DecisionCoverageResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId),
    [documents, selectedDocumentId]
  );
  const openCount = decisions.filter((decision) => decision.status === "open").length;

  useEffect(() => {
    let active = true;
    api
      .getDocuments()
      .then((loaded) => {
        if (!active) return;
        setDocuments(loaded);
        setSelectedDocumentId((current) => {
          if (current) return current;
          if (requestedDocumentId && loaded.some((document) => document.id === requestedDocumentId)) return requestedDocumentId;
          return loaded[0]?.id || "";
        });
      })
      .catch(() => active && setError("Could not load sources. Start Docker and refresh this page."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [requestedDocumentId]);

  useEffect(() => {
    if (!selectedDocumentId) {
      Promise.resolve().then(() => {
        setDecisions([]);
        setDrafts({});
        setCoverage(null);
      });
      return;
    }
    let active = true;
    Promise.all([api.getDesignDecisions(selectedDocumentId), api.getDecisionCoverage(selectedDocumentId)])
      .then(([loaded, assessed]) => {
        if (!active) return;
        setDecisions(loaded);
        setDrafts(Object.fromEntries(loaded.map((decision) => [decision.id, decision.decision || ""])));
        setCoverage(assessed);
      })
      .catch(() => active && setError("Could not load decisions for this source."));
    return () => {
      active = false;
    };
  }, [selectedDocumentId]);

  const syncFromReview = async () => {
    if (!selectedDocumentId) return;
    setSyncing(true);
    setError(null);
    try {
      const updated = await api.syncDesignDecisions(selectedDocumentId);
      const assessed = await api.getDecisionCoverage(selectedDocumentId);
      setDecisions(updated);
      setDrafts(Object.fromEntries(updated.map((decision) => [decision.id, decision.decision || ""])));
      setCoverage(assessed);
      setNotice(updated.length === 0 ? "The source review found no unresolved decisions." : "Open decisions are ready to resolve.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create decisions from this source review.");
    } finally {
      setSyncing(false);
    }
  };

  const saveDecision = async (decision: DesignDecision, nextStatus = decision.status) => {
    setSavingId(decision.id);
    setError(null);
    try {
      const updated = await api.updateDesignDecision(decision.id, {
        decision: drafts[decision.id] || "",
        status: nextStatus,
      });
      setDecisions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDrafts((current) => ({ ...current, [updated.id]: updated.decision || "" }));
      if (selectedDocumentId) setCoverage(await api.getDecisionCoverage(selectedDocumentId));
      setNotice(nextStatus === "resolved" ? "Decision resolved and retained with this source revision." : "Decision saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this decision.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <main className="page-shell">
      <section className="flex flex-col gap-6 py-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="page-kicker">Design decisions</p>
          <h1 className="display-title mt-4 text-[2.15rem] leading-tight sm:text-[3rem]">Turn open questions into build choices.</h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Decisions stay attached to one source revision. They clarify scope without rewriting your original GDD or inventing requirements.
          </p>
        </div>
        <p className="text-sm font-semibold text-[var(--text-secondary)]">{openCount} open decision{openCount === 1 ? "" : "s"}</p>
      </section>

      {(error || notice) && (
        <p className={`mt-6 border-l-2 px-4 py-3 text-sm ${error ? "border-amber-500 text-[var(--foreground)]" : "border-emerald-500 text-[var(--foreground)]"}`} role={error ? "alert" : "status"}>
          {error || notice}
        </p>
      )}

      <section className="mt-8 grid gap-8 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-t border-[var(--border)] pt-5 xl:border-r xl:pr-8">
          <label htmlFor="decision-source" className="text-sm font-semibold text-[var(--foreground)]">Source revision</label>
          <select
            id="decision-source"
            value={selectedDocumentId}
            onChange={(event) => {
              setSelectedDocumentId(event.target.value);
              setNotice(null);
              setError(null);
            }}
            disabled={loading || documents.length === 0}
            className="mt-3 min-h-11 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
          >
            {documents.map((document) => <option key={document.id} value={document.id}>{document.title} · revision {document.revision_number}</option>)}
          </select>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            {selectedDocument ? `${selectedDocument.chunks_count} indexed chunks` : "Choose a source to begin."}
          </p>
          <button type="button" onClick={syncFromReview} disabled={!selectedDocumentId || syncing} className="btn-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50">
            {syncing ? "Checking source" : "Find open decisions"}
          </button>
          {coverage && coverage.items.length > 0 && (
            <div className="mt-6 border-t border-[var(--border)] pt-5 text-sm">
              <p className="page-kicker">Evidence in this revision</p>
              <dl className="mt-3 space-y-2 text-[var(--text-secondary)]">
                <div className="flex justify-between gap-3"><dt>Source-backed</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.source_backed}</dd></div>
                <div className="flex justify-between gap-3"><dt>Needs evidence</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.needs_source_evidence}</dd></div>
                <div className="flex justify-between gap-3"><dt>Still open</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.decision_open}</dd></div>
              </dl>
            </div>
          )}
        </aside>

        <section aria-live="polite">
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse border-y border-[var(--border)] bg-[var(--card-muted)]" />)}
            </div>
          ) : !selectedDocumentId ? (
            <div className="border-y border-[var(--border)] py-16 text-center">
              <h2 className="text-xl font-semibold text-[var(--foreground)]">Add a source before making decisions.</h2>
              <p className="mt-3 text-sm text-[var(--text-secondary)]">Upload a GDD in Sources, then return here for a guided first-pass review.</p>
            </div>
          ) : decisions.length === 0 ? (
            <div className="border-y border-[var(--border)] py-16 text-center">
              <p className="page-kicker">No decision records</p>
              <h2 className="mt-3 text-xl font-semibold text-[var(--foreground)]">Review this source to create its open questions.</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">GameMind will create only missing or conflicting decisions. Your GDD stays unchanged.</p>
            </div>
          ) : (
            <div className="border-t border-[var(--border)]">
              {decisions.map((decision) => (
                <article key={decision.id} className={`border-b border-[var(--border)] border-l-2 py-6 pl-5 ${decisionTone(decision)}`}>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="page-kicker">
                        {decision.priority} priority · {decision.severity === "conflict" ? "scope conflict" : "open decision"}
                      </p>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--foreground)]">{decision.title}</h2>
                      {decision.guidance && <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{decision.guidance}</p>}
                      {decision.recommended_source_kind && (
                        <Link
                          href={`/knowledge?source_kind=${encodeURIComponent(decision.recommended_source_kind)}`}
                          className="mt-3 inline-flex text-sm font-semibold text-[var(--accent)] underline-offset-4 transition hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]"
                        >
                          Add {decision.recommended_source_kind.replaceAll("_", " ")}
                        </Link>
                      )}
                    </div>
                    <span className="shrink-0 text-xs font-semibold text-[var(--text-secondary)]">
                      {coverage?.items.find((item) => item.decision_id === decision.id)?.evidence_status.replaceAll("_", " ") || (decision.status === "resolved" ? "Resolved" : "Open")}
                    </span>
                  </div>
                  <label className="mt-5 block text-sm font-semibold text-[var(--foreground)]" htmlFor={`decision-${decision.id}`}>
                    Your decision
                    <textarea
                      id={`decision-${decision.id}`}
                      value={drafts[decision.id] || ""}
                      onChange={(event) => setDrafts((current) => ({ ...current, [decision.id]: event.target.value }))}
                      placeholder="Record the choice, its scope, and why it was made."
                      className="mt-2 min-h-28 w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-sm leading-6 text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
                    />
                  </label>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button type="button" onClick={() => saveDecision(decision)} disabled={savingId === decision.id} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                      {savingId === decision.id ? "Saving" : "Save"}
                    </button>
                    {decision.status === "open" ? (
                      <button type="button" onClick={() => saveDecision(decision, "resolved")} disabled={savingId === decision.id || !drafts[decision.id]?.trim()} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                        Mark resolved
                      </button>
                    ) : (
                      <button type="button" onClick={() => saveDecision(decision, "open")} disabled={savingId === decision.id} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                        Reopen
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function DecisionsLoadingState() {
  return (
    <main className="page-shell" aria-busy="true" aria-label="Loading design decisions">
      <section className="py-3">
        <div className="h-3 w-28 animate-pulse rounded bg-[var(--card-muted)]" />
        <div className="mt-5 h-12 max-w-xl animate-pulse rounded bg-[var(--card-muted)]" />
      </section>
      <section className="mt-8 space-y-4">
        {[1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse border-y border-[var(--border)] bg-[var(--card-muted)]" />)}
      </section>
    </main>
  );
}
