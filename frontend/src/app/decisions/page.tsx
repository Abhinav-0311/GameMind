"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import ModalDialog from "@/components/ModalDialog";

import { api, ApiRequestError, requestFailureMessage, type DecisionCoverageResponse, type DesignDecision, type DocumentResponse } from "@/lib/api";

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
  const [evidenceSelections, setEvidenceSelections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [attachingId, setAttachingId] = useState<string | null>(null);
  const [downloadingTemplate, setDownloadingTemplate] = useState(false);
  const [agentRunId, setAgentRunId] = useState<string | null>(null);
  const [agentConsentOpen, setAgentConsentOpen] = useState(false);
  const [startingAgentReview, setStartingAgentReview] = useState(false);
  const [deferRuntime, setDeferRuntime] = useState(false);
  const [allowUnspecifiedMemory, setAllowUnspecifiedMemory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [decisionsError, setDecisionsError] = useState<string | null>(null);
  const [decisionsLoading, setDecisionsLoading] = useState(false);
  const [retry, setRetry] = useState(0);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId),
    [documents, selectedDocumentId]
  );
  const openCount = decisions.filter((decision) => decision.status === "open").length;
  const hasOpenTechnicalDecision = decisions.some(
    (decision) => decision.status === "open" && decision.recommended_source_kind === "technical_brief"
  );

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (!active) return [];
      setLoading(true);
      setSourcesError(null);
      return api.getDocuments();
    })
      .then((loaded) => {
        if (!active) return;
        setDocuments(loaded);
        setSelectedDocumentId((current) => {
          if (current && loaded.some((document) => document.id === current)) return current;
          if (requestedDocumentId && loaded.some((document) => document.id === requestedDocumentId)) return requestedDocumentId;
          return loaded[0]?.id || "";
        });
      })
      .catch((reason) => active && setSourcesError(requestFailureMessage(reason, "Sources")))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [requestedDocumentId, retry]);

  useEffect(() => {
    let active = true;
    if (!selectedDocumentId) {
      Promise.resolve().then(() => {
        if (!active) return;
        setDecisions([]);
        setDrafts({});
        setEvidenceSelections({});
        setCoverage(null);
        setDecisionsLoading(false);
        setDecisionsError(null);
      });
      return () => { active = false; };
    }
    Promise.resolve().then(() => {
      if (!active) return null;
      setDecisionsLoading(true);
      setDecisionsError(null);
      setCoverage(null);
      return Promise.all([api.getDesignDecisions(selectedDocumentId), api.getDecisionCoverage(selectedDocumentId)]);
    })
      .then((result) => {
        if (!active || !result) return;
        const [loaded, assessed] = result;
        setDecisions(loaded);
        setDrafts(Object.fromEntries(loaded.map((decision) => [decision.id, decision.decision || ""])));
        setEvidenceSelections(Object.fromEntries(loaded.map((decision) => [decision.id, decision.evidence_document_id || ""])));
        setCoverage(assessed);
      })
      .catch((reason) => {
        if (active) {
          setDecisionsError(requestFailureMessage(reason, "Decisions for this source"));
          setCoverage(null);
        }
      })
      .finally(() => active && setDecisionsLoading(false));
    return () => {
      active = false;
    };
  }, [selectedDocumentId, retry]);

  const syncFromReview = async () => {
    if (!selectedDocumentId) return;
    setSyncing(true);
    setError(null);
    try {
      const updated = await api.syncDesignDecisions(selectedDocumentId);
      const assessed = await api.getDecisionCoverage(selectedDocumentId);
      setDecisions(updated);
      setDrafts(Object.fromEntries(updated.map((decision) => [decision.id, decision.decision || ""])));
      setEvidenceSelections(Object.fromEntries(updated.map((decision) => [decision.id, decision.evidence_document_id || ""])));
      setCoverage(assessed);

      let agentNotice = "";
      if (selectedDocument?.source_kind === "gdd") {
        try {
          const runs = await api.getDesignAgentRuns();
          const existingRun = runs.find((run) => run.document_ids.includes(selectedDocumentId) && run.status !== "failed");
          if (existingRun) {
            setAgentRunId(existingRun.id);
            agentNotice = " A governed review is already attached to this GDD.";
          } else {
            setAllowUnspecifiedMemory(false);
            setAgentConsentOpen(true);
            agentNotice = " Start the governed review when you want a cited draft and independent critique.";
          }
        } catch {
          agentNotice = " The local review is ready; the governed review can be started from this checkpoint.";
        }
      }

      setNotice((updated.some((decision) => decision.status === "open") ? "Open decisions are ready to resolve." : "The source review found no unresolved decisions.") + agentNotice);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create decisions from this source review.");
    } finally {
      setSyncing(false);
    }
  };

  const startAgentReview = async () => {
    if (!selectedDocumentId) return;
    setStartingAgentReview(true);
    setError(null);
    try {
      const run = await api.createDesignAgentRun({
        objective: "Review this GDD for missing or conflicting implementation decisions, then create a cited, reviewable design blueprint for the team to approve.",
        document_ids: [selectedDocumentId],
        hosted_provider_consent: true,
        defer_runtime: deferRuntime,
        allow_unspecified_memory: allowUnspecifiedMemory,
      });
      setAgentRunId(run.id);
      setAgentConsentOpen(false);
      setNotice(run.degraded
        ? "The NVIDIA review fell back to local mock output. Inspect the review trace before relying on it."
        : "A governed review is now preparing a cited draft and independent critique.");
    } catch (reason) {
      setAgentConsentOpen(false);
      if (reason instanceof ApiRequestError && reason.runId) setAgentRunId(reason.runId);
      setError(reason instanceof Error ? reason.message : "Could not start the governed review.");
    } finally {
      setStartingAgentReview(false);
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

  const attachEvidence = async (decision: DesignDecision) => {
    const evidenceDocumentId = evidenceSelections[decision.id];
    if (!evidenceDocumentId) return;
    setAttachingId(decision.id);
    setError(null);
    try {
      const updated = await api.attachDecisionEvidence(decision.id, evidenceDocumentId);
      setDecisions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedDocumentId) setCoverage(await api.getDecisionCoverage(selectedDocumentId));
      setNotice("Evidence attached. Resolve the decision once the source records the final choice.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not attach the evidence source.");
    } finally {
      setAttachingId(null);
    }
  };

  const downloadTechnicalBriefTemplate = async () => {
    if (!selectedDocumentId) return;
    setDownloadingTemplate(true);
    setError(null);
    try {
      const template = await api.getTechnicalBriefTemplate(selectedDocumentId);
      const url = URL.createObjectURL(new Blob([template.content], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = template.filename;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Technical brief template downloaded. Complete the placeholders, then upload it as a technical brief.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not prepare the technical brief template.");
    } finally {
      setDownloadingTemplate(false);
    }
  };

  return (
    <main className="page-shell">
      <section className="workbench-header flex flex-col gap-6 pt-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="page-kicker">Design decisions</p>
          <h1 className="display-title mt-4 text-[2.15rem] leading-tight sm:text-[3rem]">Turn open questions into build choices.</h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Decisions stay attached to one source revision. They clarify scope without rewriting your original GDD or inventing requirements.
          </p>
        </div>
        <p className="text-sm font-semibold text-[var(--text-secondary)]">{loading || decisionsLoading ? "Loading decisions" : sourcesError || decisionsError || !selectedDocumentId ? "Decision count unavailable" : `${openCount} open decision${openCount === 1 ? "" : "s"}`}</p>
      </section>

      {(error || notice) && (
        <div className={`mt-6 flex flex-wrap items-center justify-between gap-3 border-l-2 px-4 py-3 text-sm ${error ? "border-amber-500 text-[var(--foreground)]" : "border-emerald-500 text-[var(--foreground)]"}`} role={error ? "alert" : "status"}>
          <span>{error || notice}</span>
          {agentRunId && (
            <Link href={`/design-agent?document=${encodeURIComponent(selectedDocumentId)}&run=${encodeURIComponent(agentRunId)}`} className="shrink-0 font-semibold text-[var(--accent)] underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
              View review trace
            </Link>
          )}
        </div>
      )}

      <section className="mt-8 grid gap-8 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-t border-[var(--border)] pt-5 xl:border-r xl:pr-8">
          <label htmlFor="decision-source" className="text-sm font-semibold text-[var(--foreground)]">Source revision</label>
          <select
            id="decision-source"
            value={selectedDocumentId}
                onChange={(event) => {
                  setSelectedDocumentId(event.target.value);
                  setAgentRunId(null);
                  setAgentConsentOpen(false);
                  setNotice(null);
                  setError(null);
                }}
            disabled={loading || Boolean(sourcesError) || documents.length === 0}
            className="mt-3 min-h-11 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
          >
            {documents.map((document) => <option key={document.id} value={document.id}>{document.title} · revision {document.revision_number}</option>)}
          </select>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            {selectedDocument ? `${selectedDocument.chunks_count} indexed chunks` : "Choose a source to begin."}
          </p>
          <button id="review-source" type="button" onClick={syncFromReview} disabled={!selectedDocumentId || syncing || loading || decisionsLoading || Boolean(sourcesError || decisionsError)} className="btn-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50">
            {syncing ? "Reviewing source" : selectedDocument?.source_kind === "gdd" ? "Review GDD" : "Find open decisions"}
          </button>
          {!sourcesError && !decisionsError && !decisionsLoading && hasOpenTechnicalDecision && (
            <button type="button" onClick={downloadTechnicalBriefTemplate} disabled={downloadingTemplate} className="btn-secondary mt-3 w-full disabled:cursor-not-allowed disabled:opacity-50">
              {downloadingTemplate ? "Preparing template" : "Download technical brief template"}
            </button>
          )}
          {coverage && coverage.items.length > 0 && (
            <div className="mt-6 border-t border-[var(--border)] pt-5 text-sm">
              <p className="page-kicker">Evidence in this revision</p>
              <dl className="mt-3 space-y-2 text-[var(--text-secondary)]">
                <div className="flex justify-between gap-3"><dt>Source-backed</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.source_backed}</dd></div>
                <div className="flex justify-between gap-3"><dt>Needs evidence</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.needs_source_evidence}</dd></div>
                <div className="flex justify-between gap-3"><dt>Still open</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.decision_open}</dd></div>
                {coverage.summary.evidence_attached > 0 && <div className="flex justify-between gap-3"><dt>Evidence attached</dt><dd className="font-semibold text-[var(--foreground)]">{coverage.summary.evidence_attached}</dd></div>}
              </dl>
            </div>
          )}
        </aside>

        <section aria-live="polite">
          {loading || decisionsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse border-y border-[var(--border)] bg-[var(--card-muted)]" />)}
            </div>
          ) : sourcesError || decisionsError ? (
            <div role="alert" className="border-y border-[var(--border)] py-10">
              <h2 className="text-xl font-semibold text-[var(--foreground)]">Decision workspace unavailable</h2>
              <p className="mt-3 text-sm text-[var(--text-secondary)]">{sourcesError || decisionsError}</p>
              <button className="btn-secondary mt-5" onClick={() => setRetry((value) => value + 1)}>Retry decisions</button>
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
                        {decision.status === "resolved" ? "resolved decision" : "open decision"} · {decision.priority} priority{decision.severity === "conflict" ? " · scope conflict" : ""}
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
                  {decision.recommended_source_kind && (
                    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                      <label className="min-w-0 flex-1 text-sm font-semibold text-[var(--foreground)]" htmlFor={`evidence-${decision.id}`}>
                        Supporting {decision.recommended_source_kind.replaceAll("_", " ")}
                        <select
                          id={`evidence-${decision.id}`}
                          value={evidenceSelections[decision.id] || ""}
                          onChange={(event) => setEvidenceSelections((current) => ({ ...current, [decision.id]: event.target.value }))}
                          className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm font-normal text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
                        >
                          <option value="">Choose an uploaded source</option>
                          {documents
                            .filter((document) => document.id !== selectedDocumentId && document.source_kind === decision.recommended_source_kind)
                            .map((document) => <option key={document.id} value={document.id}>{document.title} · revision {document.revision_number}</option>)}
                        </select>
                      </label>
                      <button type="button" onClick={() => attachEvidence(decision)} disabled={!evidenceSelections[decision.id] || attachingId === decision.id} className="btn-secondary shrink-0 disabled:cursor-not-allowed disabled:opacity-50">
                        {attachingId === decision.id ? "Attaching" : "Attach source"}
                      </button>
                    </div>
                  )}
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

      {agentConsentOpen && (
        <ModalDialog labelledBy="agent-review-title" returnFocusId="review-source" dismissible={!startingAgentReview} onClose={() => setAgentConsentOpen(false)}>
          <section className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <p className="page-kicker">Governed AI review</p>
            <h2 id="agent-review-title" className="mt-3 text-2xl font-semibold text-[var(--foreground)]">Add a cited AI review to this GDD?</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              GameMind will use the configured AI provider to review selected source evidence, prepare a cited draft, and run an independent critique. Your local source review and decisions stay available either way.
            </p>
            <label className="mt-4 flex min-h-11 cursor-pointer items-center gap-3 text-sm text-[var(--foreground)]">
              <input type="checkbox" checked={deferRuntime} onChange={(event) => setDeferRuntime(event.target.checked)}
                disabled={startingAgentReview} aria-describedby="defer-runtime-help"
                className="h-5 w-5 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]" />
              Design only — defer runtime integration
            </label>
            <p id="defer-runtime-help" className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
              Runtime preview stays empty; runtime export and materialization stay blocked. Fixed for this run; all other design checks still apply.
            </p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <div className="w-full">
                <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-[var(--foreground)]">
                  <input type="checkbox" checked={allowUnspecifiedMemory} onChange={(event) => setAllowUnspecifiedMemory(event.target.checked)}
                    disabled={startingAgentReview} aria-describedby="memory-scope-help"
                    className="h-5 w-5 shrink-0 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]" />
                  Allow NPC memory to remain unspecified for this run
                </label>
                <p id="memory-scope-help" className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                  Empty, uncited memory with a warning is not assessed—not certified complete. Source-backed omissions and other design checks still block approval. Fixed for this run.
                </p>
              </div>
              <button type="button" onClick={() => setAgentConsentOpen(false)} disabled={startingAgentReview} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                Continue with local review
              </button>
              <button type="button" onClick={startAgentReview} disabled={startingAgentReview} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                {startingAgentReview ? "Starting review" : "Start governed review"}
              </button>
            </div>
          </section>
        </ModalDialog>
      )}
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
