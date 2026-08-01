"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  type DesignAgentCritiqueFinding,
  type DesignAgentEvaluation,
  type DesignAgentRun,
  type DesignAgentTrace,
  type DocumentResponse,
} from "@/lib/api";

const DEFAULT_OBJECTIVE =
  "Create a cited, reviewable game-design blueprint that identifies unsupported decisions before implementation.";

const sections = [
  { key: "summary", label: "Summary", description: "Premise, player role, and core direction." },
  { key: "narrative_direction", label: "Narrative", description: "Conflict, themes, factions, and stakes." },
  { key: "art_style_direction", label: "Art style", description: "Visual language, palette, and presentation cues." },
  { key: "npc_archetypes", label: "NPCs", description: "Character roles and behavior foundations." },
  { key: "npc_memory_design", label: "Memory", description: "Continuity facts that should shape later behavior." },
  { key: "level_design_suggestions", label: "Levels", description: "Spaces, progression, gates, and objectives." },
  { key: "gameplay_systems", label: "Systems", description: "Player loop, mechanics, and constraints." },
  { key: "quest_hooks", label: "Quests", description: "Playable hooks, objectives, and rewards." },
  { key: "unity_runtime_preview", label: "Runtime", description: "Engine-facing output prepared for export." },
] as const;

const workflowStages = ["Plan", "Evidence", "Draft", "Critique", "Review", "Final"];

function titleCase(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(milliseconds: number) {
  if (milliseconds < 1000) return `${milliseconds}ms`;
  return `${(milliseconds / 1000).toFixed(milliseconds >= 10000 ? 0 : 1)}s`;
}

function statusMeta(run: DesignAgentRun) {
  if (run.status === "completed") {
    return { label: "Approved", detail: "Final artifact locked", tone: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" };
  }
  if (run.status === "awaiting_review") {
    return { label: "Review needed", detail: `Version ${run.current_artifact?.version ?? 1} is ready`, tone: "bg-amber-500/12 text-amber-800 dark:text-amber-200" };
  }
  if (run.status === "failed") {
    return { label: "Run failed", detail: "Open the trace for the failure", tone: "bg-rose-500/10 text-rose-700 dark:text-rose-300" };
  }
  if (run.status === "queued" || run.status === "review_queued") {
    return { label: "Queued", detail: "A worker will continue this run shortly", tone: "bg-amber-500/10 text-amber-700 dark:text-amber-200" };
  }
  return { label: titleCase(run.status), detail: run.current_node ? `Working on ${titleCase(run.current_node)}` : "Workflow in progress", tone: "bg-[var(--accent-soft)] text-[var(--accent)]" };
}

function activeStageIndex(run: DesignAgentRun) {
  if (run.status === "completed") return 5;
  if (run.status === "awaiting_review") return 4;
  const nodeStages: Record<string, number> = {
    plan: 0,
    retrieve_evidence: 1,
    generate_blueprint: 2,
    revise: 2,
    critique: 3,
    human_review: 4,
    finalize: 5,
  };
  return nodeStages[run.current_node || ""] ?? 0;
}

function downloadText(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function ValueView({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-[var(--text-tertiary)]">Not specified</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[var(--text-tertiary)]">None specified</span>;
    return (
      <ul className="space-y-2">
        {value.map((item, index) => (
          <li key={index} className="flex gap-3">
            <span className="mt-[0.62rem] h-1 w-1 shrink-0 rounded-full bg-[var(--accent)]" aria-hidden="true" />
            <div className="min-w-0 flex-1"><ValueView value={item} depth={depth + 1} /></div>
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    return (
      <dl className={depth > 0 ? "space-y-2" : "divide-y divide-[var(--border)]"}>
        {Object.entries(value as Record<string, unknown>).map(([key, entry]) => (
          <div key={key} className={depth > 0 ? "grid gap-1 sm:grid-cols-[8rem_1fr]" : "grid gap-2 py-5 first:pt-0 last:pb-0 sm:grid-cols-[10rem_1fr]"}>
            <dt className="text-xs font-semibold text-[var(--text-secondary)]">{titleCase(key)}</dt>
            <dd className="min-w-0 text-sm leading-6 text-[var(--foreground)]">
              <ValueView value={entry} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return <span className="whitespace-pre-wrap break-words">{String(value)}</span>;
}

function SeverityMark({ severity }: { severity: DesignAgentCritiqueFinding["severity"] }) {
  const color = severity === "high" ? "bg-rose-500" : severity === "medium" ? "bg-amber-500" : "bg-sky-500";
  return <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${color}`} aria-label={`${severity} severity`} />;
}

function LoadingView() {
  return (
    <div className="page-shell" aria-busy="true" aria-label="Loading design-agent workspace">
      <div className="space-y-3">
        <div className="h-3 w-24 animate-pulse rounded bg-[var(--border)]" />
        <div className="h-9 w-72 max-w-full animate-pulse rounded bg-[var(--border)]" />
        <div className="h-4 w-[34rem] max-w-full animate-pulse rounded bg-[var(--border)]" />
      </div>
      <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="h-[28rem] animate-pulse rounded-lg border border-[var(--border)] bg-[var(--card)]" />
        <div className="h-[22rem] animate-pulse rounded-lg border border-[var(--border)] bg-[var(--card)]" />
      </div>
    </div>
  );
}

export default function DesignAgentPage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [runs, setRuns] = useState<DesignAgentRun[]>([]);
  const [activeRun, setActiveRun] = useState<DesignAgentRun | null>(null);
  const [trace, setTrace] = useState<DesignAgentTrace | null>(null);
  const [evaluation, setEvaluation] = useState<DesignAgentEvaluation | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE);
  const [activeSection, setActiveSection] = useState<(typeof sections)[number]["key"]>("summary");
  const [setupOpen, setSetupOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [action, setAction] = useState<"start" | "approve" | "reject" | "refresh" | "brief" | "runtime" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const indexedDocuments = useMemo(() => documents.filter((document) => document.chunks_count > 0), [documents]);
  const activeSectionMeta = sections.find((section) => section.key === activeSection) ?? sections[0];
  const activeSectionData = activeRun?.current_artifact?.content?.[activeSection];
  const critiqueFindings = activeRun?.critique?.content.findings ?? [];
  const currentStatus = activeRun ? statusMeta(activeRun) : null;
  const currentStage = activeRun ? activeStageIndex(activeRun) : 0;
  const reviewable = activeRun?.status === "awaiting_review";
  const completed = activeRun?.status === "completed";
  const activeRunId = activeRun?.id;
  const activeRunStatus = activeRun?.status;

  useEffect(() => {
    let mounted = true;
    Promise.all([api.getDocuments(), api.getDesignAgentRuns()])
      .then(([loadedDocuments, loadedRuns]) => {
        if (!mounted) return;
        setDocuments(loadedDocuments);
        setRuns(loadedRuns);
        const firstIndexed = loadedDocuments.find((document) => document.chunks_count > 0);
        setSelectedDocumentId(firstIndexed?.id ?? "");
        setActiveRun(loadedRuns[0] ?? null);
        setSetupOpen(loadedRuns.length === 0);
      })
      .catch((loadError) => {
        if (!mounted) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load the design-agent workspace.");
      })
      .finally(() => {
        if (mounted) setInitialLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!activeRun) return;
    let mounted = true;
    api.getDesignAgentTrace(activeRun.id)
      .then((loadedTrace) => {
        if (mounted) setTrace(loadedTrace);
      })
      .catch(() => {
        if (mounted) setTrace(null);
      });
    return () => {
      mounted = false;
    };
  }, [activeRun]);

  useEffect(() => {
    if (!activeRunId || !activeRunStatus || !["created", "queued", "review_queued", "running", "revision_requested", "approved"].includes(activeRunStatus)) return;
    let mounted = true;
    const refresh = async () => {
      try {
        const [run, loadedTrace] = await Promise.all([
          api.getDesignAgentRun(activeRunId),
          api.getDesignAgentTrace(activeRunId),
        ]);
        if (!mounted) return;
        setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
        setActiveRun(run);
        setTrace(loadedTrace);
        if (run.status === "awaiting_review") setNotice("Draft and independent critique are ready for review.");
        if (run.status === "completed") setNotice("Blueprint approved and final artifact locked.");
      } catch {
        // Manual refresh remains available if a transient polling request fails.
      }
    };
    const timer = window.setInterval(refresh, 2000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [activeRunId, activeRunStatus]);

  useEffect(() => {
    if (!activeRun || activeRun.status !== "completed") return;
    let mounted = true;
    api.getDesignAgentEvaluation(activeRun.id)
      .then((loadedEvaluation) => {
        if (mounted) setEvaluation(loadedEvaluation);
      })
      .catch(() => {
        if (mounted) setEvaluation(null);
      });
    return () => {
      mounted = false;
    };
  }, [activeRun]);

  function replaceRun(updatedRun: DesignAgentRun) {
    setEvaluation(null);
    setRuns((current) => [updatedRun, ...current.filter((run) => run.id !== updatedRun.id)]);
    setActiveRun(updatedRun);
  }

  async function startRun() {
    if (!selectedDocumentId) {
      setError("Choose an indexed source before starting.");
      return;
    }
    if (objective.trim().length < 10) {
      setError("Describe the design objective in at least 10 characters.");
      return;
    }

    setAction("start");
    setError(null);
    setNotice(null);
    try {
      const run = await api.createDesignAgentRun({
        objective: objective.trim(),
        document_ids: [selectedDocumentId],
        max_revisions: 2,
      });
      replaceRun(run);
      setSetupOpen(false);
      setActiveSection("summary");
      setNotice(run.status === "queued" ? "Run queued. A worker is preparing the draft." : "Draft and independent critique are ready for review.");
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Could not start the design-agent run.");
    } finally {
      setAction(null);
    }
  }

  async function refreshRun() {
    if (!activeRun) return;
    setAction("refresh");
    setError(null);
    try {
      const [run, loadedTrace] = await Promise.all([
        api.getDesignAgentRun(activeRun.id),
        api.getDesignAgentTrace(activeRun.id),
      ]);
      replaceRun(run);
      setTrace(loadedTrace);
      setNotice("Run state refreshed.");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Could not refresh this run.");
    } finally {
      setAction(null);
    }
  }

  async function submitReview(decision: "approve" | "reject") {
    if (!activeRun) return;
    if (decision === "reject" && !rejectionReason.trim()) {
      setError("Explain what must change before requesting a revision.");
      return;
    }

    setAction(decision);
    setError(null);
    setNotice(null);
    try {
      const run = await api.reviewDesignAgentRun(activeRun.id, {
        decision,
        reason: decision === "reject" ? rejectionReason.trim() : undefined,
      });
      replaceRun(run);
      setRejectOpen(false);
      setRejectionReason("");
      setNotice(
        run.status === "review_queued"
          ? "Review recorded. A worker will continue the run."
          : decision === "approve"
            ? "Blueprint approved and final artifact locked."
            : "Revision and critique are ready for another review.",
      );
      const loadedTrace = await api.getDesignAgentTrace(run.id);
      setTrace(loadedTrace);
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Could not submit the review decision.");
    } finally {
      setAction(null);
    }
  }

  async function exportArtifact(kind: "brief" | "runtime") {
    if (!activeRun) return;
    setAction(kind);
    setError(null);
    try {
      if (kind === "brief") {
        const exported = await api.getDesignAgentTechnicalBrief(activeRun.id);
        downloadText(exported.markdown, exported.filename, "text/markdown;charset=utf-8");
      } else {
        const exported = await api.getDesignAgentRuntimeExport(activeRun.id);
        downloadText(
          JSON.stringify(exported, null, 2),
          `gamemind-runtime-${activeRun.id.slice(0, 8)}.json`,
          "application/json",
        );
      }
      setNotice(kind === "brief" ? "Technical brief downloaded." : "Runtime bundle downloaded.");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Could not export this artifact.");
    } finally {
      setAction(null);
    }
  }

  if (initialLoading) return <LoadingView />;

  return (
    <div className="page-shell">
      <header className="flex flex-col gap-6 border-b border-[var(--border)] pb-8 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <p className="page-kicker">Governed workflow</p>
          <h1 className="display-title mt-3 text-3xl sm:text-[2rem]">Design agent</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
            Review a cited design draft, its independent critique, and the decision trail before anything becomes final.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary self-start sm:self-auto"
          onClick={() => setSetupOpen((open) => !open)}
          aria-expanded={setupOpen}
        >
          {setupOpen ? "Close setup" : "New run"}
        </button>
      </header>

      <div className="mt-6 space-y-3" aria-live="polite">
        {error && (
          <div role="alert" className="flex items-start justify-between gap-4 rounded-lg border border-rose-500/25 bg-rose-500/8 px-4 py-3 text-sm text-[var(--foreground)]">
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} className="font-semibold text-[var(--text-secondary)] hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
              Dismiss
            </button>
          </div>
        )}
        {notice && (
          <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/8 px-4 py-3 text-sm text-[var(--foreground)]">
            {notice}
          </div>
        )}
      </div>

      {setupOpen && (
        <section className="mt-8 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <div className="grid lg:grid-cols-[16rem_1fr]">
            <div className="border-b border-[var(--border)] bg-[var(--card-muted)] p-6 lg:border-b-0 lg:border-r">
              <p className="page-kicker">New run</p>
              <h2 className="mt-3 text-xl font-bold">Set the source of truth</h2>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                The selected indexed document becomes the fixed evidence set for this review cycle.
              </p>
            </div>
            <div className="grid gap-5 p-6 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              <label className="block">
                <span className="text-xs font-semibold text-[var(--foreground)]">Source document</span>
                <select
                  value={selectedDocumentId}
                  onChange={(event) => setSelectedDocumentId(event.target.value)}
                  className="mt-2 min-h-11 w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                >
                  {indexedDocuments.length === 0 && <option value="">No indexed sources</option>}
                  {indexedDocuments.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.title} · {document.chunks_count} chunks
                    </option>
                  ))}
                </select>
                {indexedDocuments.length === 0 && (
                  <Link href="/knowledge" className="mt-3 inline-block text-sm font-semibold text-[var(--accent)] hover:underline">
                    Upload and index a source
                  </Link>
                )}
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-[var(--foreground)]">Design objective</span>
                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  rows={3}
                  maxLength={2000}
                  className="mt-2 w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-3 text-sm leading-6 text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                />
              </label>
              <div className="md:col-span-2 flex flex-col gap-3 border-t border-[var(--border)] pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-[var(--text-secondary)]">
                  Up to two review revisions. Evidence is reused unless a future workflow explicitly requests more.
                </p>
                <button
                  type="button"
                  onClick={startRun}
                  disabled={action !== null || indexedDocuments.length === 0}
                  className="btn-primary min-w-36 disabled:cursor-not-allowed disabled:opacity-55"
                >
                  {action === "start" ? "Running agent…" : "Start design run"}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {!activeRun ? (
        <section className="mt-10 flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--card)] px-6 text-center">
          <p className="page-kicker">No runs yet</p>
          <h2 className="mt-3 text-xl font-bold">Your first governed draft starts here.</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
            Choose an indexed GDD, set the design objective, and let the workflow pause when a review decision is needed.
          </p>
          {!setupOpen && (
            <button type="button" className="btn-primary mt-6" onClick={() => setSetupOpen(true)}>
              Configure first run
            </button>
          )}
        </section>
      ) : (
        <>
          <section className="mt-8 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
            <div className="flex flex-col gap-5 p-6 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 max-w-3xl">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${currentStatus?.tone}`}>
                    {currentStatus?.label}
                  </span>
                  {activeRun.degraded && (
                    <span className="rounded-full border border-amber-500/25 px-2.5 py-1 text-xs font-semibold text-[var(--foreground)]">
                      Local fallback
                    </span>
                  )}
                  <span className="text-xs text-[var(--text-secondary)]">{currentStatus?.detail}</span>
                </div>
                <h2 className="mt-4 text-xl font-bold leading-8">{activeRun.objective}</h2>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">
                  Started {formatDate(activeRun.created_at)} · {activeRun.provider_name} · Evidence revision {activeRun.retrieval_revision}
                </p>
                {activeRun.degraded && (
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                    NVIDIA did not complete this run in time, so GameMind preserved the workflow using deterministic local output. Review the result as orchestration proof, not hosted-model quality.
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row lg:justify-end">
                <label className="sr-only" htmlFor="run-history">Run history</label>
                <select
                  id="run-history"
                  value={activeRun.id}
                  onChange={(event) => {
                    const selected = runs.find((run) => run.id === event.target.value);
                    if (selected) {
                      setTrace(null);
                      setEvaluation(null);
                      setActiveRun(selected);
                      setActiveSection("summary");
                      setRejectOpen(false);
                    }
                  }}
                  className="min-h-11 max-w-64 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                >
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {formatDate(run.created_at)} · {titleCase(run.status)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={refreshRun}
                  disabled={action !== null}
                >
                  {action === "refresh" ? "Refreshing…" : "Refresh"}
                </button>
              </div>
            </div>
            <ol className="grid grid-cols-3 border-t border-[var(--border)] sm:grid-cols-6" aria-label="Workflow progress">
              {workflowStages.map((stage, index) => {
                const reached = index <= currentStage;
                const current = index === currentStage && !completed;
                return (
                  <li key={stage} className="border-r border-[var(--border)] px-3 py-3 last:border-r-0">
                    <div className={`mb-2 h-1 rounded-full ${reached ? "bg-[var(--accent)]" : "bg-[var(--border)]"}`} />
                    <span className={`text-[0.6875rem] font-semibold ${current ? "text-[var(--accent)]" : reached ? "text-[var(--foreground)]" : "text-[var(--text-tertiary)]"}`}>
                      {stage}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>

          <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="border-b border-[var(--border)] px-5 pt-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="page-kicker">Artifact · version {activeRun.current_artifact?.version ?? "—"}</p>
                    <h2 className="mt-2 text-xl font-bold">{activeSectionMeta.label}</h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{activeSectionMeta.description}</p>
                  </div>
                  {activeSectionData && (
                    <div className="flex items-center gap-2 pb-1 text-xs text-[var(--text-secondary)]">
                      <span>{activeSectionData.confidence} confidence</span>
                      <span aria-hidden="true">·</span>
                      <span>{activeSectionData.citations.length} citations</span>
                    </div>
                  )}
                </div>
                <div className="-mx-1 mt-5 flex gap-1 overflow-x-auto pb-3" role="tablist" aria-label="Blueprint sections">
                  {sections.map((section) => (
                    <button
                      key={section.key}
                      type="button"
                      role="tab"
                      aria-selected={activeSection === section.key}
                      onClick={() => setActiveSection(section.key)}
                      className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--accent)] ${
                        activeSection === section.key
                          ? "bg-[var(--accent)] text-white"
                          : "text-[var(--text-secondary)] hover:bg-[var(--card-muted)] hover:text-[var(--foreground)]"
                      }`}
                    >
                      {section.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-5 sm:p-7">
                {!activeSectionData ? (
                  <div className="py-16 text-center text-sm text-[var(--text-secondary)]">
                    This artifact does not contain the selected section.
                  </div>
                ) : (
                  <>
                    <ValueView value={activeSectionData.content} />
                    {activeSectionData.warnings.length > 0 && (
                      <div className="mt-7 border-l-2 border-amber-500 pl-4">
                        <p className="text-xs font-bold text-[var(--foreground)]">Review before approval</p>
                        <ul className="mt-2 space-y-1 text-sm leading-6 text-[var(--text-secondary)]">
                          {activeSectionData.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                        </ul>
                      </div>
                    )}
                  </>
                )}
              </div>
            </section>

            <aside className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="border-b border-[var(--border)] p-5">
                <p className="page-kicker">Independent critique</p>
                <h2 className="mt-2 text-lg font-bold">
                  {completed
                    ? "Critique reviewed"
                    : activeRun.critique?.content.verdict === "needs_revision"
                      ? "Changes recommended"
                      : "Ready for your judgment"}
                </h2>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  {activeRun.critique?.content.summary || "No critique was recorded for this artifact."}
                </p>
              </div>

              <div className="max-h-[28rem] divide-y divide-[var(--border)] overflow-y-auto">
                {critiqueFindings.length === 0 ? (
                  <p className="p-5 text-sm leading-6 text-[var(--text-secondary)]">No critique findings were recorded.</p>
                ) : (
                  critiqueFindings.map((finding, index) => (
                    <div key={`${finding.section}-${index}`} className="p-5">
                      <div className="flex gap-3">
                        <SeverityMark severity={finding.severity} />
                        <div>
                          <p className="text-xs font-bold text-[var(--foreground)]">{titleCase(finding.section)}</p>
                          <p className="mt-2 text-sm leading-5 text-[var(--foreground)]">{finding.issue}</p>
                          <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">{finding.recommendation}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="border-t border-[var(--border)] bg-[var(--card-muted)] p-5">
                {reviewable && !rejectOpen && (
                  <div className="grid gap-2">
                    <button
                      type="button"
                      className="btn-primary w-full"
                      onClick={() => submitReview("approve")}
                      disabled={action !== null}
                    >
                      {action === "approve" ? "Finalizing…" : "Approve run"}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary w-full"
                      onClick={() => setRejectOpen(true)}
                      disabled={action !== null}
                    >
                      Request revision
                    </button>
                  </div>
                )}
                {reviewable && rejectOpen && (
                  <div>
                    <label htmlFor="rejection-reason" className="text-xs font-bold text-[var(--foreground)]">
                      What must change?
                    </label>
                    <textarea
                      id="rejection-reason"
                      value={rejectionReason}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      rows={5}
                      maxLength={4000}
                      autoFocus
                      placeholder="Be specific enough to verify the revision."
                      className="mt-2 w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-3 text-sm leading-6 text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                    />
                    <div className="mt-3 grid gap-2">
                      <button
                        type="button"
                        className="btn-primary w-full"
                        onClick={() => submitReview("reject")}
                        disabled={action !== null || !rejectionReason.trim()}
                      >
                        {action === "reject" ? "Revising and critiquing…" : "Send revision request"}
                      </button>
                      <button type="button" className="btn-secondary w-full" onClick={() => setRejectOpen(false)} disabled={action !== null}>
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                {completed && (
                  <div className="grid gap-2">
                    <p className="mb-2 text-sm font-semibold text-[var(--foreground)]">Approved artifact</p>
                    <button type="button" className="btn-primary w-full" onClick={() => exportArtifact("brief")} disabled={action !== null}>
                      {action === "brief" ? "Preparing…" : "Download technical brief"}
                    </button>
                    <button type="button" className="btn-secondary w-full" onClick={() => exportArtifact("runtime")} disabled={action !== null}>
                      {action === "runtime" ? "Preparing…" : "Download runtime JSON"}
                    </button>
                  </div>
                )}
                {!reviewable && !completed && (
                  <p className="text-sm leading-6 text-[var(--text-secondary)]">
                    Review controls appear when the workflow reaches its human checkpoint.
                  </p>
                )}
              </div>
            </aside>
          </div>

          {evaluation && (
            <section className="mt-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex flex-col gap-4 border-b border-[var(--border)] px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="page-kicker">CyberRakshak rubric · {evaluation.rubric_version}</p>
                  <h2 className="mt-2 text-lg font-bold">Quality scorecard</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Human judgments are stored beside system-verified persistence checks.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    evaluation.passed
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "bg-rose-500/10 text-rose-700 dark:text-rose-300"
                  }`}>
                    {evaluation.passed ? "Acceptance passed" : "Needs improvement"}
                  </span>
                  <span className="text-lg font-bold">{Math.round(evaluation.overall_score * 100)}%</span>
                </div>
              </div>
              <div className="grid sm:grid-cols-2 xl:grid-cols-5">
                {evaluation.metrics.map((metric) => (
                  <div key={metric.key} className="border-b border-[var(--border)] px-5 py-5 last:border-b-0 sm:border-r xl:border-b-0 xl:last:border-r-0">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs font-bold leading-5 text-[var(--foreground)]">{metric.label}</p>
                      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${metric.passed ? "bg-emerald-500" : "bg-rose-500"}`} aria-label={metric.passed ? "Passed" : "Failed"} />
                    </div>
                    <p className="mt-3 text-2xl font-bold">{Math.round(metric.value * 100)}%</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                      Target {metric.target} · {metric.source === "system_verified" ? "System verified" : "Human reviewed"}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <details className="mt-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent)]">
              <span>
                <span className="text-sm font-bold">Workflow trace</span>
                <span className="ml-3 text-xs text-[var(--text-secondary)]">
                  {trace?.items.length ?? 0} events · {trace?.items.reduce((total, item) => total + item.input_tokens + item.output_tokens, 0).toLocaleString() ?? 0} tokens
                </span>
              </span>
              <span className="text-xs font-semibold text-[var(--accent)]">Inspect</span>
            </summary>
            <div className="border-t border-[var(--border)]">
              {!trace ? (
                <p className="p-5 text-sm text-[var(--text-secondary)]">Trace data is unavailable for this run.</p>
              ) : (
                <ol className="divide-y divide-[var(--border)]">
                  {trace.items.map((item) => (
                    <li key={item.id} className="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(9rem,1fr)_7rem_7rem_5rem] sm:items-center">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{titleCase(item.node_name)}</p>
                        <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">
                          Attempt {item.attempt} · {item.provider_name || "system"}{item.model_name ? ` · ${item.model_name}` : ""}
                        </p>
                        {item.error && <p className="mt-2 text-xs leading-5 text-rose-600 dark:text-rose-300">{item.error}</p>}
                      </div>
                      <span className="text-xs text-[var(--text-secondary)]">{formatDuration(item.latency_ms)}</span>
                      <span className="text-xs text-[var(--text-secondary)]">{(item.input_tokens + item.output_tokens).toLocaleString()} tokens</span>
                      <span className={`text-xs font-semibold ${item.status === "failed" ? "text-rose-600 dark:text-rose-300" : item.status === "waiting" ? "text-amber-700 dark:text-amber-200" : "text-[var(--foreground)]"}`}>
                        {titleCase(item.status)}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </details>
        </>
      )}
    </div>
  );
}
