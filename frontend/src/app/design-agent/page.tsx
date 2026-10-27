"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ModalDialog from "@/components/ModalDialog";
import FrozenDesignEvidence from "@/components/FrozenDesignEvidence";
import DesignFindingReviews from "@/components/DesignFindingReviews";
import {
  api,
  ApiRequestError,
  requestFailureMessage,
  getActiveProjectId,
  type DesignFindingReview,
  type DesignAgentEvaluation,
  type DesignAgentCritiqueFinding,
  type DesignAgentQualityScorecard,
  type DesignAgentProposalConfirmation,
  type DesignAgentRun,
  type DesignAgentTrace,
  type DesignAgentTraceItem,
  type DocumentResponse,
} from "@/lib/api";

const DEFAULT_OBJECTIVE =
  "Create a cited, reviewable game-design blueprint that identifies unsupported decisions before implementation.";

function traceTokenLabel(items: DesignAgentTraceItem[]) {
  const total = items.reduce((sum, item) => sum + item.input_tokens + item.output_tokens, 0).toLocaleString();
  if (items.some((item) => item.details.token_usage_scope === "unavailable"
    || (item.status === "failed" && item.details.token_usage_scope !== "completed_responses_only"))) {
    return "Token usage unknown";
  }
  return `${total} ${items.some((item) => item.details.token_usage_scope === "completed_responses_only") ? "reported tokens (total may be incomplete)" : "tokens"}`;
}

const sections = [
  { key: "summary", label: "Summary", description: "Premise, player role, and core direction." },
  { key: "narrative_direction", label: "Narrative", description: "Conflict, themes, factions, and stakes." },
  { key: "art_style_direction", label: "Art style", description: "Visual language, palette, and presentation cues." },
  { key: "npc_archetypes", label: "NPCs", description: "Character roles and behavior foundations." },
  { key: "npc_memory_design", label: "Memory", description: "Continuity facts that should shape later behavior." },
  { key: "level_design_suggestions", label: "Levels", description: "Spaces, progression, gates, and objectives." },
  { key: "gameplay_systems", label: "Systems", description: "Player loop, mechanics, and constraints." },
  { key: "quest_hooks", label: "Quests", description: "Playable hooks, objectives, and rewards." },
  { key: "unity_runtime_preview", label: "Runtime", description: "Integration preview, not proof of client-ready bindings." },
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
    return { label: "Approved", detail: "Final artifact locked", tone: "bg-emerald-500/10 text-[var(--success-text)]" };
  }
  if (run.status === "awaiting_review") {
    return { label: "Review needed", detail: `Version ${run.current_artifact?.version ?? 1} is ready`, tone: "bg-amber-500/12 text-[var(--warning-text)]" };
  }
  if (run.status === "revision_limit_reached") {
    return { label: "Revision budget exhausted", detail: "Start a new run; this draft is preserved", tone: "bg-amber-500/12 text-[var(--warning-text)]" };
  }
  if (run.status === "failed") {
    return { label: "Run failed", detail: "See the failed step in the trace", tone: "bg-rose-500/10 text-[var(--danger-text)]" };
  }
  if (run.status === "queued" || run.status === "review_queued") {
    return { label: "Queued", detail: "A worker will continue this run shortly", tone: "bg-amber-500/10 text-[var(--warning-text)]" };
  }
  return { label: titleCase(run.status), detail: run.current_node ? `Working on ${titleCase(run.current_node)}` : "Workflow in progress", tone: "bg-[var(--accent-soft)] text-[var(--accent)]" };
}

function activeStageIndex(run: DesignAgentRun) {
  if (run.status === "completed") return 5;
  if (run.status === "awaiting_review" || run.status === "revision_limit_reached") return 4;
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
            <dt className={`text-xs font-semibold ${key === "assumptions" ? "text-[var(--warning-text)]" : "text-[var(--text-secondary)]"}`}>
              {key === "assumptions" ? "Review required" : key === "source_chunk_ids" ? "Evidence references" : titleCase(key)}
            </dt>
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

function PreApprovalScorecard({ scorecard, current = false, findings = [] }: { scorecard: DesignAgentQualityScorecard; current?: boolean; findings?: DesignAgentCritiqueFinding[] }) {
  return (
    <section className="border-b border-[var(--border)] bg-[var(--card-muted)] p-5" aria-label="Pre-approval quality scorecard">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="page-kicker">{current ? "Current system checks" : "Saved system checks"}</p>
          <h3 className="mt-2 text-sm font-bold">Pre-approval quality{scorecard.unspecified_sections?.length ? " · assessed scope" : ""}</h3>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${scorecard.passed ? "bg-emerald-500/10 text-[var(--success-text)]" : "bg-amber-500/10 text-[var(--warning-text)]"}`}>
          {Math.round(scorecard.overall_score * 100)}%
        </span>
      </div>
      {current && <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">Recomputed for this draft and frozen evidence. The saved model critique below is unchanged.</p>}
      {scorecard.unspecified_sections?.includes("npc_memory_design") && <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">NPC memory: Unspecified—not assessed. This is not a complete memory design or proof of source absence.</p>}
      {findings.length > 0 && <ul aria-label="Current system blockers" className="mt-4 space-y-4 text-sm leading-6 [overflow-wrap:anywhere]">
        {findings.map((finding, index) => <li key={index}>
          <p>{finding.issue}</p>
          <details className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            <summary className="min-h-11 w-fit cursor-pointer rounded-md py-3 font-medium focus-visible:outline-2 focus-visible:outline-[var(--accent)]">Suggested fix</summary>
            <p>{finding.recommendation}</p>
          </details>
        </li>)}
      </ul>}
      <div className="mt-4 space-y-3">
        {scorecard.metrics.map((metric) => (
          <div key={metric.key}>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="font-semibold text-[var(--foreground)]">{metric.label}</span>
              <span className={metric.passed ? "text-[var(--success-text)]" : "text-[var(--warning-text)]"}>{Math.round(metric.value * 100)}%</span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--border)]"><div className={`h-full rounded-full ${metric.passed ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${Math.round(metric.value * 100)}%` }} /></div>
            <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{metric.detail}</p>
          </div>
        ))}
      </div>
      {scorecard.unresolved_assumptions.length > 0 && (
        <p className="mt-4 border-l-2 border-amber-500 pl-3 text-xs leading-5 text-[var(--text-secondary)]">
          {scorecard.unresolved_assumptions.length} assumption{scorecard.unresolved_assumptions.length === 1 ? "" : "s"} still need human confirmation.
        </p>
      )}
    </section>
  );
}

function ApprovalGate({ scorecard, needsRevision, status, revisionBudgetExhausted, proposalsSelected }: { scorecard?: DesignAgentQualityScorecard; needsRevision: boolean; status: string; revisionBudgetExhausted: boolean; proposalsSelected: boolean }) {
  const blockers = scorecard?.blockers ?? [];
  const blocked = needsRevision || (scorecard ? !scorecard.passed : false);
  if (status !== "awaiting_review") {
    const lifecycle = status === "completed"
      ? { title: "Review complete", body: "The final artifact is locked. Historical quality findings remain visible below." }
      : status === "failed"
        ? { title: "Review failed", body: "Inspect the workflow trace for the failure before starting another run. Approval is unavailable." }
        : status === "revision_limit_reached"
          ? { title: "Revision budget exhausted", body: "This historical run cannot continue. Its draft and trace are preserved. Start a new run with fresh provider consent." }
        : status === "queued" || status === "review_queued"
          ? { title: "Review queued", body: "The worker will continue this run. Approval is unavailable until the review checkpoint is ready." }
          : status === "approved"
            ? { title: "Finalizing approved review", body: "Your approval is recorded. The workflow is locking the final artifact." }
            : status === "revision_requested"
              ? { title: "Revision in progress", body: "The workflow is revising the draft before a new review checkpoint." }
              : { title: "Review in progress", body: "GameMind is preparing the draft and independent critique. Approval is unavailable until the review checkpoint is ready." };
    return (
      <section className="border-b border-[var(--border)] bg-[var(--card-muted)] p-5" aria-label="Approval status">
        <p className="page-kicker">Approval status</p>
        <p className="mt-2 text-sm font-bold text-[var(--foreground)]">{lifecycle.title}</p>
        <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{lifecycle.body}</p>
      </section>
    );
  }
  if (proposalsSelected) {
    return (
      <section className="border-b border-[var(--border)] bg-[var(--card-muted)] p-5" aria-label="Approval status">
        <p className="page-kicker">Approval status</p>
        <p className="mt-2 text-sm font-bold">Ready to submit for approval</p>
        <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">Your proposal choices are unsaved. The server will recheck this exact draft before recording approval.</p>
      </section>
    );
  }
  if (!blocked) {
    return (
      <section className="border-b border-emerald-500/25 bg-emerald-500/5 p-5" aria-label="Approval status">
        <p className="page-kicker">Approval status</p>
        <p className="mt-2 text-sm font-bold text-[var(--success-text)]">Ready for your judgment</p>
        <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">System checks are clear. Review the cited draft, then approve only when you agree with it.</p>
      </section>
    );
  }
  return (
    <section className="border-b border-amber-500/30 bg-amber-500/8 p-5" aria-label="Approval blocked">
      <p className="page-kicker">Approval status</p>
      <div className="mt-2 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-[var(--foreground)]">Approval is blocked</h3>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{revisionBudgetExhausted ? "This draft still needs changes. Start a new run before it can become runtime intent." : "Request a revision or resolve the review items before this draft can become runtime intent."}</p>
        </div>
        <span className="shrink-0 rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-bold text-[var(--warning-text)]">Review needed</span>
      </div>
      {blockers.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Approval blockers">
          {blockers.map((blocker) => <li key={blocker} className="rounded-md border border-amber-500/25 bg-[var(--surface)] px-2 py-1 text-xs font-semibold text-[var(--foreground)]">{blocker}</li>)}
        </ul>
      )}
    </section>
  );
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

function proposalKey(proposal: DesignAgentQualityScorecard["unresolved_assumptions"][number]) {
  return JSON.stringify([proposal.section, proposal.record_id, proposal.assumption]);
}

export default function DesignAgentPage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [runs, setRuns] = useState<DesignAgentRun[]>([]);
  const [activeRun, setActiveRun] = useState<DesignAgentRun | null>(null);
  const [trace, setTrace] = useState<DesignAgentTrace | null>(null);
  const [configuredProvider, setConfiguredProvider] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<DesignAgentEvaluation | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE);
  const [freshDialogue, setFreshDialogue] = useState(false);
  const [deferRuntime, setDeferRuntime] = useState(false);
  const [allowUnspecifiedMemory, setAllowUnspecifiedMemory] = useState(false);
  const [dialoguePolicy, setDialoguePolicy] = useState("");
  const [activeSection, setActiveSection] = useState<(typeof sections)[number]["key"]>("summary");
  const [setupOpen, setSetupOpen] = useState(false);
  const [startConsentOpen, setStartConsentOpen] = useState(false);
  const [critiqueRetryChoice, setCritiqueRetry] = useState<{ runId: string; artifactId: string; executionId: string } | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [revisionSections, setRevisionSections] = useState<(typeof sections)[number]["key"][]>(["summary"]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [action, setAction] = useState<"start" | "approve" | "reject" | "refresh" | "brief" | "runtime" | "critique" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [proposalChoices, setProposalChoices] = useState<{ artifactId: string; keys: string[] } | null>(null);
  const [degradedAcknowledgement, setDegradedAcknowledgement] = useState<string | null>(null);
  const [findingEpoch, setFindingEpoch] = useState(0);
  const [findingState, setFindingState] = useState<{ context: string; review: DesignFindingReview | null; busy: boolean } | null>(null);

  const indexedDocuments = useMemo(() => documents.filter((document) => document.chunks_count > 0), [documents]);
  const activeSectionMeta = sections.find((section) => section.key === activeSection) ?? sections[0];
  const activeSectionData = activeRun?.current_artifact?.content?.[activeSection];
  const critiqueFindings = activeRun?.critique?.content.findings ?? [];
  const artifactId = activeRun?.current_artifact?.id;
  const degradedAcknowledged = Boolean(artifactId && degradedAcknowledgement === `${activeRun?.id}:${artifactId}`);
  const critiqueIsCurrent = Boolean(artifactId && activeRun?.critique?.artifact_id === artifactId);
  const findingContext = useMemo(() => JSON.stringify([activeRun?.id, artifactId, activeRun?.current_artifact?.content, activeRun?.critique, findingEpoch]),
    [activeRun?.id, artifactId, activeRun?.current_artifact?.content, activeRun?.critique, findingEpoch]);
  const onFindingPolicy = useCallback((review: DesignFindingReview | null) => {
    setFindingState((current) => ({ context: findingContext, review, busy: current?.context === findingContext && current.busy }));
  }, [findingContext]);
  const onFindingBusy = useCallback((busy: boolean) => {
    setFindingState((current) => ({ context: findingContext, review: current?.context === findingContext ? current.review : null, busy }));
  }, [findingContext]);
  const findingReview = findingState?.context === findingContext && findingState.review && findingState.review.artifact_id === artifactId
    && findingState.review.critique_id === activeRun?.critique?.id ? findingState.review : null;
  const findingBusy = findingState?.context === findingContext && findingState.busy;
  const systemChecks = activeRun?.status === "awaiting_review" ? findingReview?.system_checks : null;
  const preApprovalScorecard = systemChecks?.quality_scorecard ?? (critiqueIsCurrent ? activeRun?.critique?.content.quality_scorecard : undefined);
  const pendingProposals = preApprovalScorecard?.unresolved_assumptions ?? [];
  const selectedKeys = proposalChoices?.artifactId === artifactId ? proposalChoices?.keys ?? [] : [];
  const selectedProposals: DesignAgentProposalConfirmation[] = pendingProposals.flatMap((proposal) =>
    proposal.section && proposal.record_id && selectedKeys.includes(proposalKey(proposal))
      ? [{ section: proposal.section, record_id: proposal.record_id, assumption: proposal.assumption }] : []);
  const rawCritiqueBlocked = activeRun?.critique?.content.verdict === "needs_revision"
    || critiqueFindings.some((finding) => finding.severity === "high")
    || (["nvidia", "gemini"].includes(activeRun?.provider_name ?? "") && (activeRun?.critique?.content.verdict !== "ready_for_review"
      || activeRun?.critique?.artifact_id !== artifactId || !preApprovalScorecard));
  const needsRevision = Boolean(activeRun?.critique && !critiqueIsCurrent)
    || (activeRun?.status === "awaiting_review" && Boolean(activeRun.critique?.id) && !findingReview)
    || (["nvidia", "gemini"].includes(activeRun?.provider_name ?? "") && (!preApprovalScorecard || activeRun?.critique?.artifact_id !== artifactId))
    || (findingReview ? findingReview.critique_blocked : rawCritiqueBlocked);
  const confirmationReady = Boolean(preApprovalScorecard && !preApprovalScorecard.passed
    && preApprovalScorecard.blockers.length === 1 && preApprovalScorecard.blockers[0] === "Integration readiness"
    && ["grounding", "completeness", "consistency"].every((key) => preApprovalScorecard.metrics.some((metric) => metric.key === key && metric.passed))
    && preApprovalScorecard.metrics.filter((metric) => metric.key !== "integration_readiness").every((metric) => metric.passed)
    && !preApprovalScorecard.unsupported_sections?.length && !preApprovalScorecard.incomplete_sections?.length
    && !preApprovalScorecard.quest_integration_gaps?.length
    && !preApprovalScorecard.recovered_sections?.length && pendingProposals.length > 0
    && pendingProposals.length <= 64 && selectedProposals.length === pendingProposals.length && !needsRevision);
  const approvalBlocked = findingBusy || needsRevision || (pendingProposals.length > 0 && !confirmationReady)
    || (activeRun?.degraded === true && !degradedAcknowledged)
    || Boolean(preApprovalScorecard && !preApprovalScorecard.passed && !confirmationReady);
  const currentStatus = activeRun ? statusMeta(activeRun) : null;
  const currentStage = activeRun ? activeStageIndex(activeRun) : 0;
  const reviewable = activeRun?.status === "awaiting_review";
  const revisionBudgetExhausted = Boolean(activeRun && activeRun.revision_count >= activeRun.max_revisions);
  const failedRevisions = activeRun?.consecutive_revision_failures ?? 0;
  const failedRevisionLimit = activeRun?.max_consecutive_revision_failures ?? 3;
  const failedRevisionLimitReached = failedRevisions >= failedRevisionLimit;
  const revisionBlocked = revisionBudgetExhausted || failedRevisionLimitReached;
  const completed = activeRun?.status === "completed";
  const activeRunId = activeRun?.id;
  const activeRunStatus = activeRun?.status;
  const latestCritiqueExecution = trace ? [...trace.items].reverse().find((item) => item.node_name === "critique") : undefined;
  const failedCritique = activeRun?.status === "failed" && activeRun.current_node === "critique"
    && artifactId && !critiqueIsCurrent && trace?.run_id === activeRun.id
    && latestCritiqueExecution?.status === "failed" ? latestCritiqueExecution : undefined;

  const critiqueRetry = critiqueRetryChoice && critiqueRetryChoice.runId === activeRunId && critiqueRetryChoice.artifactId === artifactId ? critiqueRetryChoice : null;
  const offlineConsent = (critiqueRetry ? activeRun?.provider_name : configuredProvider) === "mock";

  useEffect(() => {
    if (error && !startConsentOpen && !critiqueRetry) document.getElementById("design-run-error")?.focus();
  }, [error, startConsentOpen, critiqueRetry]);

  function replaceLocation(documentId: string, runId?: string) {
    const params = new URLSearchParams();
    params.set("document", documentId);
    if (runId) params.set("run", runId);
    window.history.replaceState(null, "", `/design-agent?${params.toString()}`);
  }

  useEffect(() => {
    let mounted = true;
    Promise.resolve().then(() => {
      if (!mounted) return null;
      setInitialLoading(true);
      setLoadError(null);
      return Promise.all([api.getDocuments(), api.getDesignAgentRuns(), api.getHealth().catch(() => null)]);
    })
      .then((result) => {
        if (!mounted || !result) return;
        const [loadedDocuments, loadedRuns, health] = result;
        setDocuments(loadedDocuments);
        setRuns(loadedRuns);
        setConfiguredProvider(health?.llm_provider ?? null);
        const params = new URLSearchParams(window.location.search);
        const requestedDocument = loadedDocuments.find(
          (document) => document.id === params.get("document") && document.chunks_count > 0,
        );
        const requestedRun = loadedRuns.find((run) => run.id === params.get("run"));
        const selectedRun = requestedRun ?? loadedRuns[0] ?? null;
        const runDocument = loadedDocuments.find(
          (document) => document.id === selectedRun?.document_ids[0] && document.chunks_count > 0,
        );
        setSelectedDocumentId(requestedDocument?.id ?? runDocument?.id ?? loadedDocuments.find((document) => document.chunks_count > 0)?.id ?? "");
        setActiveRun(selectedRun);
        setCritiqueRetry(null);
        setProposalChoices(null);
        setSetupOpen(!selectedRun);
      })
      .catch((loadError) => {
        if (!mounted) return;
        setLoadError(requestFailureMessage(loadError, "Design-agent workspace"));
      })
      .finally(() => {
        if (mounted) setInitialLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [retry]);

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
    setFindingEpoch((value) => value + 1);
    setProposalChoices(null);
    setEvaluation(null);
    setRuns((current) => [updatedRun, ...current.filter((run) => run.id !== updatedRun.id)]);
    setActiveRun(updatedRun);
  }

  function requestStartRun() {
    if (!selectedDocumentId) {
      setError("Choose an indexed source before starting.");
      return;
    }
    if (objective.trim().length < 10) {
      setError("Describe the design objective in at least 10 characters.");
      return;
    }
    if (dialoguePolicy.trim() && dialoguePolicy.trim().length < 10) {
      setError("Describe the repeat/reset policy in at least 10 characters, or leave it blank.");
      return;
    }
    setError(null);
    setStartConsentOpen(true);
  }

  async function startRun() {
    setAction("start");
    setError(null);
    setNotice(null);
    try {
      const run = await api.createDesignAgentRun({
        objective: objective.trim(),
        document_ids: [selectedDocumentId],
        max_revisions: 2,
        hosted_provider_consent: true,
        fresh_dialogue: freshDialogue,
        defer_runtime: deferRuntime,
        allow_unspecified_memory: allowUnspecifiedMemory,
        dialogue_policy: dialoguePolicy.trim() || null,
      });
      replaceRun(run);
      replaceLocation(selectedDocumentId, run.id);
      setSetupOpen(false);
      setStartConsentOpen(false);
      setActiveSection("summary");
      setNotice(run.status === "queued" ? "Run queued. A worker is preparing the draft." : "Draft and independent critique are ready for review.");
    } catch (runError) {
      setStartConsentOpen(false);
      setError(runError instanceof Error ? runError.message : "Could not start the design-agent run.");
      if (runError instanceof ApiRequestError && runError.runId) {
        replaceLocation(selectedDocumentId, runError.runId);
        try {
          const run = await api.getDesignAgentRun(runError.runId);
          replaceRun(run);
          setTrace(null);
          setSetupOpen(false);
          setActiveSection("summary");
        } catch {
          setError(`${runError.message} The failed run was saved, but could not be loaded. Reload this page to recover it.`);
        }
      }
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
    if (!artifactId || (decision === "approve" && approvalBlocked)) {
      setError(decision === "approve" ? "Review the current draft and resolve its blockers before approval."
        : "Review the current draft before requesting a revision.");
      return;
    }
    if (decision === "reject" && revisionBlocked) {
      setError(failedRevisionLimitReached ? "Consecutive failed revision limit reached. Start a new run with fresh provider consent."
        : "Revision budget exhausted. Start a new run with fresh provider consent.");
      return;
    }
    if (decision === "reject" && !rejectionReason.trim()) {
      setError("Explain what must change before requesting a revision.");
      return;
    }
    if (decision === "reject" && revisionSections.length === 0) {
      setError("Select at least one section to revise.");
      return;
    }

    setAction(decision);
    setError(null);
    setNotice(null);
    try {
      const run = await api.reviewDesignAgentRun(activeRun.id, {
        decision,
        reason: decision === "reject" ? rejectionReason.trim() : undefined,
        target_sections: decision === "reject" ? sections.filter((section) => revisionSections.includes(section.key)).map((section) => section.key) : undefined,
        artifact_id: artifactId,
        confirmed_proposals: decision === "approve" ? selectedProposals : undefined,
        acknowledge_degraded: decision === "approve" ? degradedAcknowledged : undefined,
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
      let message = reviewError instanceof Error ? reviewError.message : "Could not submit the review decision.";
      if (reviewError instanceof ApiRequestError && [409, 502, 503].includes(reviewError.status)) {
        setDegradedAcknowledgement(null);
        setProposalChoices(null);
        setFindingEpoch((value) => value + 1);
        try {
          const [run, loadedTrace] = await Promise.all([api.getDesignAgentRun(activeRun.id), api.getDesignAgentTrace(activeRun.id)]);
          replaceRun(run);
          setTrace(loadedTrace);
        } catch {
          message += " Could not reload the current budget and trace. Refresh before retrying.";
        }
      }
      setError(message);
    } finally {
      setAction(null);
    }
  }

  async function retryCritique() {
    const selected = critiqueRetry;
    if (!selected || !activeRun || selected.runId !== activeRun.id || selected.artifactId !== artifactId
      || selected.executionId !== failedCritique?.id || getActiveProjectId() !== activeRun.game_project_id) {
      setCritiqueRetry(null); setError("The review context changed. Refresh before retrying."); return;
    }
    const projectId = activeRun.game_project_id;
    setAction("critique"); setError(null); setNotice(null);
    try {
      const run = await api.retryDesignAgentCritique(selected.runId, activeRun.game_project_id,
        { artifact_id: selected.artifactId, failed_execution_id: selected.executionId, hosted_provider_consent: true });
      if (getActiveProjectId() === projectId) {
        replaceRun(run);
        setNotice(run.status === "review_queued" ? "Critique retry queued. The saved draft is unchanged." : "Critique recovered. Review the saved draft before approval.");
      }
    } catch (retryError) {
      if (getActiveProjectId() === projectId) setError(retryError instanceof Error ? retryError.message : "Critique retry failed. The saved draft is unchanged.");
    } finally {
      setCritiqueRetry(null);
      if (getActiveProjectId() === projectId) {
        try {
          const [run, loadedTrace] = await Promise.all([api.getDesignAgentRun(selected.runId), api.getDesignAgentTrace(selected.runId)]);
          if (getActiveProjectId() === projectId) { replaceRun(run); setTrace(loadedTrace); }
        } catch {
          if (getActiveProjectId() === projectId) setError((current) => `${current ?? "Review state could not be refreshed."} Refresh before retrying.`);
        }
      }
      setAction(null);
    }
  }

  async function exportArtifact(kind: "brief" | "runtime") {
    if (!activeRun) return;
    if (kind === "runtime" && activeRun.defer_runtime) return;
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
      setNotice(kind === "brief" ? "Technical brief downloaded." : "Runtime preview downloaded; this is not a materialized runtime bundle.");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Could not export this artifact.");
    } finally {
      setAction(null);
    }
  }

  if (initialLoading) return <LoadingView />;
  if (loadError) return (
    <div className="page-shell">
      <p className="page-kicker">Governed workflow</p>
      <h1 className="display-title mt-4 text-3xl">Design-agent workspace unavailable</h1>
      <div role="alert" className="mt-6">
        <p className="text-sm leading-6 text-[var(--text-secondary)]">{loadError}</p>
        <button className="btn-secondary mt-4" onClick={() => setRetry((value) => value + 1)}>Retry design agent</button>
      </div>
    </div>
  );

  return (
    <div className="page-shell">
      <header className="workbench-header flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
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
          disabled={action !== null}
          onClick={() => { if (!setupOpen) setAllowUnspecifiedMemory(false); setSetupOpen((open) => !open); }}
          aria-expanded={setupOpen}
        >
          {setupOpen ? "Close setup" : "New run"}
        </button>
      </header>

      <div className="mt-6 space-y-3" aria-live="polite">
        {error && (
          <div id="design-run-error" role="alert" tabIndex={-1} className="flex items-start justify-between gap-4 rounded-lg border border-rose-500/25 bg-rose-500/8 px-4 py-3 text-sm text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
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
        <section className="status-strip mt-8 overflow-hidden rounded-lg">
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
                  onChange={(event) => {
                    setSelectedDocumentId(event.target.value);
                    replaceLocation(event.target.value);
                  }}
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
              <div className="space-y-4 md:col-span-2">
                <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-[var(--foreground)]">
                  <input type="checkbox" checked={deferRuntime} onChange={(event) => setDeferRuntime(event.target.checked)}
                    disabled={action !== null} aria-describedby="defer-runtime-help"
                    className="h-5 w-5 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]" />
                  Design only — defer runtime integration
                </label>
                <p id="defer-runtime-help" className="text-xs leading-5 text-[var(--text-secondary)]">
                  Review design without inventing engine bindings. Runtime preview stays empty; runtime export and materialization stay blocked. Fixed for this run.
                </p>
                <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-[var(--foreground)]">
                  <input type="checkbox" checked={allowUnspecifiedMemory} onChange={(event) => setAllowUnspecifiedMemory(event.target.checked)}
                    disabled={action !== null} aria-describedby="memory-scope-help"
                    className="h-5 w-5 shrink-0 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]" />
                  Allow NPC memory to remain unspecified for this run
                </label>
                <p id="memory-scope-help" className="text-xs leading-5 text-[var(--text-secondary)]">
                  Empty, uncited memory with a warning is not assessed—not certified complete. Source-backed omissions and other design checks still block approval. Fixed for this run.
                </p>
                <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-[var(--foreground)]">
                  <input
                    type="checkbox"
                    checked={freshDialogue}
                    onChange={(event) => setFreshDialogue(event.target.checked)}
                    disabled={action !== null}
                    className="h-5 w-5 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]"
                    aria-describedby="fresh-dialogue-help"
                  />
                  Generate fresh dialogue
                </label>
                <p id="fresh-dialogue-help" className="text-xs leading-5 text-[var(--text-secondary)]">
                  Copied source lines will block approval when this is selected. Voice and usefulness still need review.
                </p>
                <label className="block">
                  <span className="text-xs font-semibold text-[var(--foreground)]">Fixed repeat/reset policy (optional)</span>
                  <textarea
                    value={dialoguePolicy}
                    onChange={(event) => setDialoguePolicy(event.target.value)}
                    disabled={action !== null}
                    rows={2}
                    maxLength={240}
                    aria-describedby="dialogue-policy-help"
                    placeholder="Describe when warnings repeat and exactly what resets them."
                    className="mt-2 w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-3 text-sm leading-6 text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                  />
                </label>
                <p id="dialogue-policy-help" className="text-xs leading-5 text-[var(--text-secondary)]">
                  Applied verbatim to every warning mapping through revisions. Leave blank for a reviewable AI proposal; start a new run to change a fixed policy.
                </p>
              </div>
              <div className="md:col-span-2 flex flex-col gap-3 border-t border-[var(--border)] pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-[var(--text-secondary)]">
                  Up to two review revisions. Evidence is reused unless a future workflow explicitly requests more.
                </p>
                <button
                  type="button"
                  onClick={requestStartRun}
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

      {(startConsentOpen || critiqueRetry) && (
        <ModalDialog labelledBy="start-agent-review-title" dismissible={action !== "start" && action !== "critique"} onClose={() => { setStartConsentOpen(false); setCritiqueRetry(null); }}>
          <section className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <p className="page-kicker">{offlineConsent ? "Offline review" : "Governed AI review"}</p>
            <h2 id="start-agent-review-title" className="mt-3 text-2xl font-semibold text-[var(--foreground)]">{critiqueRetry ? "Retry this draft's critique?" : "Start a cited review?"}</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              {offlineConsent ? "This run is offline. The mock provider processes source excerpts locally and sends nothing to a hosted provider. It uses deterministic extraction, not newly generated content." : critiqueRetry ? "The saved draft and its frozen source excerpts will be sent to the configured hosted provider for critique only. Planning, retrieval and generation will not repeat. The draft stays unchanged; nothing is approved." : "The selected source revision may be sent to the configured hosted provider to create a cited draft and independent critique. No provider request is made until you confirm."}
            </p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => { setStartConsentOpen(false); setCritiqueRetry(null); }} disabled={action === "start" || action === "critique"} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                Cancel
              </button>
              <button type="button" onClick={critiqueRetry ? retryCritique : startRun} disabled={action === "start" || action === "critique"} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                {critiqueRetry ? action === "critique" ? "Retrying critique" : "Retry saved draft review" : action === "start" ? "Starting review" : offlineConsent ? "Start offline review" : "Start governed review"}
              </button>
            </div>
          </section>
        </ModalDialog>
      )}

      {!activeRun ? (
        <section className="mt-10 flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--card)] px-6 text-center">
          <p className="page-kicker">No runs yet</p>
          <h2 className="mt-3 text-xl font-bold">Your first governed draft starts here.</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
            Choose an indexed GDD, set the design objective, and let the workflow pause when a review decision is needed.
          </p>
          {!setupOpen && (
            <button type="button" className="btn-primary mt-6" onClick={() => { setAllowUnspecifiedMemory(false); setSetupOpen(true); }}>
              Configure first run
            </button>
          )}
        </section>
      ) : (
        <>
          <section className="status-strip mt-8 overflow-hidden rounded-lg">
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
                {activeRun.defer_runtime && (
                  <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                    Design-only review · Runtime integration deferred. Design approval does not enable runtime export or materialization.
                  </p>
                )}
                {activeRun.allow_unspecified_memory && <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">Memory scope is fixed for this run. Only empty, uncited NPC memory with a warning may remain unspecified; other checks still apply.</p>}
                <h2 className="mt-4 text-xl font-semibold leading-7">Design review</h2>
                <p aria-hidden="true" className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--text-secondary)] [overflow-wrap:anywhere]">
                  {activeRun.objective}
                </p>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">
                  Started {formatDate(activeRun.created_at)} · {activeRun.provider_name} · Evidence revision {activeRun.retrieval_revision}
                </p>
                <details key={activeRun.id} className="mt-1">
                  <summary className="min-h-11 w-fit cursor-pointer rounded-md py-2 text-sm font-medium leading-7 text-[var(--text-secondary)] hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
                    Full objective
                  </summary>
                  <p className="max-w-prose whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)] [overflow-wrap:anywhere]">
                    {activeRun.objective}
                  </p>
                </details>
                {activeRun.degraded && (
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                    This run contains degraded or mock-fallback output. It is not proof of hosted-model quality. Explicitly acknowledge this before approval; all design checks still apply.
                  </p>
                )}
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 lg:flex lg:justify-end">
                <label className="sr-only" htmlFor="run-history">Run history</label>
                <select
                  id="run-history"
                  disabled={action !== null}
                  value={activeRun.id}
                  onChange={(event) => {
                    const selected = runs.find((run) => run.id === event.target.value);
                    if (selected) {
                      setTrace(null);
                      setEvaluation(null);
                      setActiveRun(selected);
                      setCritiqueRetry(null);
                      setProposalChoices(null);
                      const documentId = selected.document_ids[0] || selectedDocumentId;
                      if (documentId) {
                        setSelectedDocumentId(documentId);
                        replaceLocation(documentId, selected.id);
                      }
                      setActiveSection("summary");
                      setRejectOpen(false);
                    }
                  }}
                  className="min-h-11 min-w-0 max-w-64 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
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
            <section className="status-strip min-w-0 overflow-hidden rounded-lg">
              <div className="border-b border-[var(--border)] px-5 pt-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="page-kicker">Artifact · version {activeRun.current_artifact?.version ?? "—"}</p>
                    <h2 className="mt-2 text-xl font-bold">{activeSectionMeta.label}</h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{activeSectionMeta.description}</p>
                  </div>
                  {activeSectionData && (
                    <div className="flex items-center gap-2 pb-1 text-xs text-[var(--text-secondary)]">
                      {activeSection === "npc_memory_design" && preApprovalScorecard?.unspecified_sections?.includes("npc_memory_design")
                        ? <span>Unspecified—not assessed</span>
                        : <><span>{activeSectionData.confidence} confidence</span><span aria-hidden="true">·</span><span>{activeSectionData.citations.length} citations</span></>}
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
                          ? "bg-[var(--accent-highlight)] text-[#191a23]"
                          : "text-[var(--text-secondary)] hover:bg-[var(--card-muted)] hover:text-[var(--foreground)]"
                      }`}
                    >
                      {section.label}
                    </button>
                  ))}
                </div>
              </div>
              {artifactId && <FrozenDesignEvidence key={`${activeRun.id}:${artifactId}`} runId={activeRun.id} artifactId={artifactId} references={activeSectionData?.citations ?? []} />}
              <div className="p-5 sm:p-7">
                {!activeSectionData ? (
                  <div className="py-16 text-center text-sm text-[var(--text-secondary)]">
                    {activeRun.status === "failed" && !activeRun.current_artifact
                      ? "No draft was generated. Inspect the failed step in the workflow trace."
                      : "This artifact does not contain the selected section."}
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

            <aside className="status-strip overflow-hidden rounded-lg">
              <ApprovalGate scorecard={preApprovalScorecard} needsRevision={needsRevision} status={activeRun.status} revisionBudgetExhausted={revisionBudgetExhausted} proposalsSelected={confirmationReady} />
              {preApprovalScorecard && <PreApprovalScorecard scorecard={preApprovalScorecard} current={Boolean(systemChecks)} findings={systemChecks?.findings} />}
              {reviewable && pendingProposals.length > 0 && (
                <fieldset className="border-b border-[var(--border)] p-5" disabled={action !== null} aria-describedby="proposal-choice-help">
                  <legend className="px-1 text-sm font-semibold">Proposals to review</legend>
                  <p id="proposal-choice-help" className="text-xs leading-5 text-[var(--text-secondary)]">Selections are unsaved until you submit approval. They do not verify GDD facts or runtime behaviour.</p>
                  <div className="mt-4 space-y-4">
                    {pendingProposals.map((proposal) => (
                      <label key={proposalKey(proposal)} className="flex min-h-11 cursor-pointer items-start gap-3 text-sm leading-6">
                        <input type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
                          aria-label={`Accept proposal for ${proposal.record}: ${proposal.assumption}`}
                          disabled={!proposal.section || !proposal.record_id || !artifactId}
                          checked={selectedKeys.includes(proposalKey(proposal))}
                          onChange={(event) => {
                            if (!artifactId) return;
                            const key = proposalKey(proposal);
                            const keys = event.target.checked ? [...selectedKeys, key] : selectedKeys.filter((item) => item !== key);
                            setProposalChoices({ artifactId, keys });
                          }} />
                        <span className="min-w-0 break-words"><span className="block text-xs font-semibold text-[var(--text-secondary)]">{proposal.record}</span><span className="block">{proposal.assumption}</span></span>
                      </label>
                    ))}
                  </div>
                  <p className="mt-4 text-xs leading-5 text-[var(--text-secondary)]" aria-live="polite">{selectedProposals.length} of {pendingProposals.length} selected for draft version {activeRun.current_artifact?.version}.</p>
                  {pendingProposals.some((proposal) => !proposal.section || !proposal.record_id) && (
                    <p className="mt-2 text-xs leading-5 text-[var(--warning-text)]">This historical scorecard has no proposal IDs. A new review is required before confirmation.</p>
                  )}
                </fieldset>
              )}
              <div className="border-b border-[var(--border)] p-5">
                <p className="page-kicker">{activeRun.critique && !critiqueIsCurrent ? completed ? "Review history" : "Previous or unlinked critique" : "Independent critique"}</p>
                <h2 className="mt-2 text-lg font-bold">
                  {!activeRun.critique
                    ? activeRun.status === "failed" ? "Critique unavailable" : "Critique not ready"
                    : !critiqueIsCurrent
                    ? completed ? "Previous draft critique" : "Critique not linked to current draft"
                    : completed
                    ? "Critique reviewed"
                    : activeRun.critique?.content.verdict === "needs_revision"
                      ? "Changes recommended"
                      : "Ready for your judgment"}
                </h2>
                {activeRun.critique && !critiqueIsCurrent && <p className="mt-2 text-sm leading-6 text-[var(--warning-text)]">
                  {completed
                    ? "The approved snapshot is locked. This critique belongs to an earlier draft; its findings and recorded judgments remain visible for audit. No further approval is required."
                    : <>Draft version {activeRun.current_artifact?.version ?? "—"} needs its own independent review before approval. The critique below is not linked to this version; its findings are retained for reference only.</>}
                </p>}
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  {activeRun.critique?.content.summary || "No critique was recorded for this artifact."}
                </p>
                {failedCritique && artifactId && <div className="mt-4">
                  <p className="text-sm leading-6 text-[var(--text-secondary)]">Your draft is saved. Retry its critique without generating it again. Approval remains blocked.</p>
                  <button type="button" className="btn-primary mt-3 disabled:cursor-not-allowed disabled:opacity-50" disabled={action !== null}
                    onClick={() => setCritiqueRetry({ runId: activeRun.id, artifactId, executionId: failedCritique.id })}>Retry critique</button>
                </div>}
              </div>

              {activeRun.current_artifact && activeRun.critique ? <DesignFindingReviews
                key={findingContext} runId={activeRun.id} artifact={activeRun.current_artifact} critique={activeRun.critique}
                reviewable={reviewable} disabled={action !== null} onPolicy={onFindingPolicy} onBusy={onFindingBusy}
              /> : <p className="p-5 text-sm text-[var(--text-secondary)]">No critique findings were recorded.</p>}

              <div className="border-t border-[var(--border)] bg-[var(--card-muted)] p-5">
                {(reviewable || activeRun.status === "revision_limit_reached") && (
                  <div className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">
                    <p>Saved revisions: {activeRun.revision_count}/{activeRun.max_revisions}</p>
                    <p>Consecutive failed corrections: {failedRevisions}/{failedRevisionLimit}. A failed correction does not consume a saved revision slot.</p>
                    {failedRevisionLimitReached && <p id="failed-revision-help" className="mt-2">Failed revision limit reached. No more corrections will be sent. Start a new run with fresh provider consent; this draft stays unchanged.</p>}
                    {activeRun.last_error && failedRevisions > 0 && <p className="mt-2">Last correction error: {activeRun.last_error}</p>}
                    {revisionBudgetExhausted && <p id="revision-budget-help" className="mt-2">Revision budget exhausted. Start a new run with a clearer objective and fresh provider consent. This draft stays unchanged.</p>}
                  </div>
                )}
                {reviewable && (!rejectOpen || revisionBlocked) && (
                  <div className="grid gap-2">
                    {activeRun.degraded && (
                      <div className="mb-2 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-4">
                        <p id="degraded-review-warning" className="text-sm font-semibold">Degraded output requires your acknowledgement</p>
                        <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">One or more stages used fallback or degraded output. Approving does not certify hosted generation quality.</p>
                        <label className="mt-3 flex cursor-pointer items-start gap-3 text-sm leading-6">
                          <input type="checkbox" className="mt-1 size-4 shrink-0 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2"
                            checked={degradedAcknowledged} disabled={action !== null}
                            aria-describedby="degraded-review-warning"
                            onChange={(event) => setDegradedAcknowledgement(event.target.checked ? `${activeRun.id}:${artifactId}` : null)} />
                          <span>I understand this draft contains degraded/mock-fallback output and explicitly accept that risk for design approval.</span>
                        </label>
                      </div>
                    )}
                    <button
                      type="button"
                      className={action !== null || approvalBlocked
                        ? "inline-flex min-h-11 w-full cursor-not-allowed items-center justify-center border border-[var(--border)] bg-[var(--card-muted)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
                        : "btn-primary w-full"}
                      onClick={() => submitReview("approve")}
                      disabled={action !== null || approvalBlocked}
                      title={approvalBlocked ? "Resolve the listed review blockers before approval." : undefined}
                    >
                      {action === "approve" ? "Finalizing…" : approvalBlocked ? "Approval blocked" : "Approve run"}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary w-full"
                      onClick={() => { setRevisionSections([activeSection]); setRejectOpen(true); }}
                      disabled={action !== null || findingBusy || revisionBlocked}
                      aria-describedby={failedRevisionLimitReached ? "failed-revision-help" : revisionBudgetExhausted ? "revision-budget-help" : undefined}
                      title={failedRevisionLimitReached ? "Consecutive failed correction limit reached." : revisionBudgetExhausted ? "This run has no revisions remaining." : undefined}
                    >
                      Request revision
                    </button>
                  </div>
                )}
                {reviewable && rejectOpen && !revisionBlocked && (
                  <div>
                    <fieldset
                      disabled={action !== null}
                      aria-describedby="revision-scope-help"
                    >
                      <legend className="text-xs font-bold text-[var(--foreground)]">Sections to revise</legend>
                      <div className="mt-2 grid grid-cols-2 gap-x-2">
                        {sections.map((section) => (
                          <label key={section.key} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md px-2 text-sm text-[var(--foreground)] hover:bg-[var(--surface)] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--accent)]">
                            <input
                              type="checkbox"
                              className="h-4 w-4 shrink-0 accent-[var(--accent)]"
                              checked={revisionSections.includes(section.key)}
                              onChange={(event) => {
                                const checked = event.target.checked;
                                setRevisionSections((selected) => checked ? [...selected, section.key] : selected.filter((key) => key !== section.key));
                              }}
                            />
                            <span>{section.label}</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                    <p className="mt-2 text-xs font-semibold text-[var(--foreground)]" aria-live="polite">
                      {revisionSections.length === 0 ? "Select at least one section." : `${revisionSections.length} ${revisionSections.length === 1 ? "section" : "sections"} selected.`}
                    </p>
                    <p id="revision-scope-help" className="mb-4 mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                      Only selected sections may change. Other sections stay unchanged, even if mentioned below.
                    </p>
                    <label htmlFor="rejection-reason" className="text-xs font-bold text-[var(--foreground)]">
                      What must change?
                    </label>
                    <textarea
                      id="rejection-reason"
                      value={rejectionReason}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      rows={5}
                      maxLength={4000}
                      disabled={action !== null}
                      autoFocus
                      placeholder="Be specific enough to verify the revision."
                      className="mt-2 w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-3 text-sm leading-6 text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
                    />
                    <div className="mt-3 grid gap-2">
                      <button
                        type="button"
                        className="btn-primary w-full"
                        onClick={() => submitReview("reject")}
                        disabled={action !== null || revisionBlocked || revisionSections.length === 0 || !rejectionReason.trim()}
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
                    {activeRun.defer_runtime && <p className="text-xs leading-5 text-[var(--text-secondary)]">Runtime deferred. Download the reviewed design brief; client integration remains blocked.</p>}
                    <button type="button" className="btn-primary w-full" onClick={() => exportArtifact("brief")} disabled={action !== null}>
                      {action === "brief" ? "Preparing…" : "Download technical brief"}
                    </button>
                    <button type="button" className="btn-secondary w-full" onClick={() => exportArtifact("runtime")} disabled={action !== null || activeRun.defer_runtime === true}>
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
                  <p className="page-kicker">Quality rubric · {evaluation.rubric_version}</p>
                  <h2 className="mt-2 text-lg font-bold">Quality scorecard</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Human judgments are stored beside system-verified persistence checks.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    evaluation.passed
                      ? "bg-emerald-500/10 text-[var(--success-text)]"
                      : "bg-rose-500/10 text-[var(--danger-text)]"
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

          <details key={activeRun.id} open={activeRun.status === "failed"} className="mt-6 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent)]">
              <span>
                <span className="text-sm font-bold">Workflow trace</span>
                <span className="ml-3 text-xs text-[var(--text-secondary)]">
                  {trace?.items.length ?? 0} events · {trace ? traceTokenLabel(trace.items) : "Token usage unknown"}
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
                        {item.error && <p className="mt-2 text-xs leading-5 text-[var(--danger-text)]">{item.error}</p>}
                      </div>
                      <span className="text-xs text-[var(--text-secondary)]">{formatDuration(item.latency_ms)}</span>
                      <span className="text-xs text-[var(--text-secondary)]">{traceTokenLabel([item])}</span>
                      <span className={`text-xs font-semibold ${item.status === "failed" ? "text-[var(--danger-text)]" : item.status === "waiting" ? "text-[var(--warning-text)]" : "text-[var(--foreground)]"}`}>
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
