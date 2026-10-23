"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api, ApiRequestError, getActiveProjectId, requestFailureMessage,
  type DesignAgentArtifact, type DesignAgentCritique, type DesignAgentEvidence,
  type DesignFindingReview, type DesignAgentCritiqueFinding } from "@/lib/api";

const sectionLabels: Record<string, string> = { npc_archetypes: "NPCs", quest_hooks: "Quests" };
const label = (value: string) => (sectionLabels[value]
  || value.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase()));
const pointerKey = (value: string) => value.replace(/~/g, "~0").replace(/\//g, "~1");
const control = "mt-2 min-h-11 w-full min-w-0 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm leading-6 text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] disabled:opacity-60";

function fields(value: unknown, path: string, title: string): { path: string; title: string; value: unknown }[] {
  if (Array.isArray(value)) return value.flatMap((item, index) => fields(item, `${path}/${index}`,
    `${title} / ${item?.name || item?.title || index + 1}`));
  if (value && typeof value === "object") return Object.entries(value).flatMap(([key, item]) =>
    key === "source_chunk_ids" ? [] : fields(item, `${path}/${pointerKey(key)}`, ["npcs", "quests"].includes(key) ? title : `${title} / ${label(key)}`));
  return value !== null && value !== undefined && value !== "" && path.length <= 500 ? [{ path, title, value }] : [];
}

function findingFields(content: DesignAgentArtifact["content"], finding: DesignAgentCritiqueFinding) {
  if (finding.reference != null) {
    const path = finding.reference.artifact_path;
    if (typeof path !== "string" || !path.startsWith("/") || path.length > 500 || /~(?![01])/.test(path)) return [];
    let value: unknown = content;
    for (const part of path.slice(1).split("/")) {
      const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
      if (!value || typeof value !== "object" || !Object.hasOwn(value, key)
          || (Array.isArray(value) && !/^(0|[1-9][0-9]*)$/.test(key))) return [];
      value = (value as Record<string, unknown>)[key];
    }
    return [{ path, title: path, value }];
  }
  // Model findings may name a section or a dotted/bracket field beneath its
  // content. Derive presentation only: never rewrite the finding or evaluate it.
  const root = /^([a-z][a-z0-9_]*)(?:\.content(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[(?:0|[1-9][0-9]*)\])*)?$/.exec(finding.section)?.[1];
  if (!root || !Object.hasOwn(content, root)) return [];
  return fields(content[root].content, `/${pointerKey(root)}/content`, label(root));
}

function failure(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 409) return "The draft or review changed. Reload finding reviews before trying again; nothing was approved.";
    if (error.status === 503) return "Finding reviews are unavailable until the prepared database migration is applied. This action recorded no review or approval.";
    if (error.status === 422) return error.message;
  }
  return requestFailureMessage(error, "Finding reviews");
}

export default function DesignFindingReviews({ runId, artifact, critique, reviewable, disabled, onPolicy, onBusy }: {
  runId: string;
  artifact: DesignAgentArtifact;
  critique: DesignAgentCritique;
  reviewable: boolean;
  disabled: boolean;
  onPolicy: (review: DesignFindingReview | null) => void;
  onBusy: (busy: boolean) => void;
}) {
  const targetId = critique.artifact_id || artifact.id;
  const [projectId] = useState(getActiveProjectId);
  const [catalog, setCatalog] = useState<DesignFindingReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState<number | null>(null);
  const [evidence, setEvidence] = useState<DesignAgentEvidence | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [evidenceAttempt, setEvidenceAttempt] = useState(0);
  const [path, setPath] = useState("");
  const [chunkId, setChunkId] = useState("");
  const [quote, setQuote] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const live = useRef(true);
  const fieldInput = useRef<HTMLSelectElement | HTMLTextAreaElement>(null);
  const noticeElement = useRef<HTMLParagraphElement>(null);
  const formId = useId();
  const findings = useMemo(() => critique.content.findings ?? [], [critique.content.findings]);
  const options = useMemo(() => open === null || !findings[open] ? [] : findingFields(artifact.content, findings[open]), [artifact.content, findings, open]);
  const selected = options.find((item) => item.path === path);
  const excerpt = evidence?.items.find((item) => item.chunk_id === chunkId);
  const mayWrite = reviewable && !artifact.immutable && targetId === artifact.id && catalog?.can_record === true;
  const valid = Boolean(mayWrite && selected && excerpt && quote.trim().length >= 12 && quote.trim().length <= 2000
    && excerpt.content.includes(quote.trim()) && reason.trim().length >= 30 && reason.trim().length <= 4000);

  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => {
    if (open !== null) {
      if (options.length) fieldInput.current?.focus();
      else document.getElementById(`${formId}-cancel`)?.focus();
    }
  }, [open, options.length, formId]);
  useEffect(() => {
    if (!critique.id) return;
    let current = true;
    api.getDesignFindingReviews(runId, targetId, projectId).then((review) => {
      if (review.artifact_id !== targetId || review.critique_id !== critique.id || review.findings.length !== findings.length
          || review.findings.some((item, index) => ["severity", "section", "issue", "recommendation"].some((key) =>
            item.finding[key as keyof typeof item.finding] !== findings[index][key as keyof typeof item.finding]))) {
        throw new ApiRequestError("Finding review version mismatch", 409);
      }
      if (current) { setCatalog(review); onPolicy(review); }
    }).catch((cause) => { if (current) { setError(failure(cause)); onPolicy(null); } });
    return () => { current = false; };
  }, [runId, targetId, projectId, critique.id, findings, attempt, onPolicy]);

  useEffect(() => {
    if (open === null || evidence) return;
    let current = true;
    api.getDesignAgentEvidence(runId, targetId).then((result) => {
      if (result.artifact_id !== targetId || result.snapshot_id !== catalog?.evidence_snapshot_id) throw new ApiRequestError("Evidence version mismatch", 409);
      if (current) { setEvidence(result); setChunkId(result.items[0]?.chunk_id || ""); }
    }).catch((cause) => { if (current) setEvidenceError(cause instanceof ApiRequestError && cause.status === 409
      ? "Frozen evidence does not match this draft. Reload finding reviews before recording."
      : requestFailureMessage(cause, "Frozen evidence")); });
    return () => { current = false; };
  }, [runId, targetId, open, evidence, evidenceAttempt, catalog?.evidence_snapshot_id]);

  function reload() {
    setCatalog(null); onPolicy(null); setError(null); setOpen(null); setEvidence(null); setEvidenceError(null);
    setAttempt((value) => value + 1);
  }

  function cancel(index: number) {
    setOpen(null);
    requestAnimationFrame(() => document.getElementById(`${formId}-review-${index}`)?.focus());
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const item = open === null ? undefined : catalog?.findings[open];
    if (!catalog || !item?.can_resolve || !valid || saving || disabled) return;
    setSaving(true); onBusy(true); setError(null); setNotice(null);
    try {
      await api.recordDesignFindingReview(runId, targetId, projectId, {
        critique_id: catalog.critique_id, artifact_sha256: catalog.artifact_sha256,
        critique_sha256: catalog.critique_sha256, evidence_sha256: catalog.evidence_sha256,
        finding_id: item.finding_id, artifact_path: path, evidence_chunk_id: chunkId,
        evidence_quote: quote.trim(), reason: reason.trim(),
      });
      if (live.current) {
        reload(); setNotice("Human review recorded. Nothing was approved or generated.");
        requestAnimationFrame(() => noticeElement.current?.focus());
      }
    } catch (cause) {
      if (live.current) { onPolicy(null); setCatalog(null); setError(failure(cause)); }
    } finally {
      if (live.current) { setSaving(false); onBusy(false); }
    }
  }

  return <section aria-label="Finding reviews" className="divide-y divide-[var(--border)]">
      <div className="space-y-3 px-5 py-4 text-xs leading-5 text-[var(--text-secondary)]">
        <p>AI feedback is advisory, not verified correctness. Review the draft against frozen evidence; confirmed defects need correction. Human judgments stay separate from the unchanged AI critique and cannot bypass system checks or approve this draft.</p>
        {!catalog && !error && critique.id && <p role="status">Loading finding reviews…</p>}
        {notice && <p ref={noticeElement} tabIndex={-1} role="status" className="rounded-md focus-visible:outline-2 focus-visible:outline-[var(--accent)]">{notice}</p>}
        {error && <div role="alert"><p>{error}</p><button type="button" className="btn-secondary mt-3" disabled={saving} onClick={reload}>Reload finding reviews</button></div>}
        {catalog && !catalog.can_record && <p>Read-only. Recording requires a signed-in workspace owner or editor and the current review checkpoint.</p>}
        {!critique.id && <p>Finding identities are unavailable for this historical review.</p>}
      </div>
      {findings.length === 0 && <p className="p-5 text-sm text-[var(--text-secondary)]">No critique findings were recorded.</p>}
      {findings.map((finding, index) => {
        const policy = catalog?.findings[index];
        const record = catalog?.resolutions.find((entry) => entry.finding_id === policy?.finding_id);
        return <article key={index} className="space-y-3 p-5 text-sm leading-6 [overflow-wrap:anywhere]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="font-semibold">{label(finding.section)}</h3>
            <span className="text-xs text-[var(--text-secondary)]">{label(finding.severity)} severity</span>
          </div>
          <p>{finding.issue}</p>
          <p className="text-xs leading-5 text-[var(--text-secondary)]">{finding.recommendation}</p>
          {policy?.resolution_applies && <p className="text-xs font-semibold text-[var(--foreground)]">Human-reviewed, not AI-verified</p>}
          {policy && <p className="text-xs leading-5 text-[var(--text-secondary)]">{policy.status_message}</p>}
          {record && <details className="text-xs text-[var(--text-secondary)]">
            <summary className="min-h-11 w-fit cursor-pointer rounded-md py-3 font-medium focus-visible:outline-2 focus-visible:outline-[var(--accent)]">Recorded human judgment</summary>
            <dl className="space-y-2 pb-2">
              <div><dt className="font-semibold">Judgment</dt><dd>Not a defect — the reviewer’s assertion, not AI verification.</dd></div>
              <div><dt className="font-semibold">Reviewer</dt><dd>{record.reviewer_label} · {new Date(record.created_at).toLocaleString()}</dd></div>
              <div><dt className="font-semibold">Reason</dt><dd className="whitespace-pre-wrap">{record.reason}</dd></div>
              <div><dt className="font-semibold">Draft field</dt><dd>{record.artifact_path}<pre className="mt-1 whitespace-pre-wrap font-sans">{JSON.stringify(record.artifact_value, null, 2)}</pre></dd></div>
              <div><dt className="font-semibold">Frozen quote</dt><dd><blockquote className="whitespace-pre-wrap">{record.evidence_quote}</blockquote></dd></div>
            </dl>
          </details>}
          {policy?.can_resolve && mayWrite && open !== index && <button id={`${formId}-review-${index}`} type="button" className="btn-secondary" disabled={disabled || saving}
            onClick={() => { setOpen(index); setPath(finding.reference != null ? findingFields(artifact.content, finding)[0]?.path || "" : ""); setReason(""); setQuote(""); setNotice(null); }}>Review finding</button>}
          {open === index && mayWrite && policy?.can_resolve && <form aria-label={`Review finding ${index + 1}`} className="space-y-4 pt-2" onSubmit={save}
            onKeyDown={(event) => { if (event.key === "Escape" && !saving) { event.preventDefault(); cancel(index); } }}>
            <div><label htmlFor={`${formId}-field`} className="text-xs font-semibold">Draft field</label>
              {finding.reference != null ? <>
                <textarea ref={(node) => { fieldInput.current = node; }} id={`${formId}-field`} className={`${control} resize-none`} value={path} rows={2} readOnly
                  disabled={saving || disabled || !options.length} aria-describedby={`${formId}-field-help`} />
                {options.length > 0 && <p id={`${formId}-field-help`} className="mt-1 text-xs text-[var(--text-secondary)]">This finding fixes the draft field. Review its value against the frozen evidence below.</p>}
              </> : <select ref={(node) => { fieldInput.current = node; }} id={`${formId}-field`} className={control} value={path} required disabled={saving || disabled || !options.length}
                aria-describedby={!options.length ? `${formId}-field-help` : undefined} onChange={(event) => setPath(event.target.value)}>
                <option value="">Choose the exact field</option>{options.map((item) => <option key={item.path} value={item.path}>{item.title}</option>)}
              </select>}
              {!options.length && <p id={`${formId}-field-help`} role="status" className="mt-2 text-xs text-[var(--text-secondary)]">No reviewable draft fields match this finding. Recording is blocked; request a corrected critique or draft.</p>}
              {selected && <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-[var(--card-muted)] p-3 font-sans text-xs">{typeof selected.value === "object" ? JSON.stringify(selected.value, null, 2) : String(selected.value)}</pre>}
            </div>
            {!evidence && !evidenceError && <p role="status" className="text-xs">Loading frozen evidence…</p>}
            {evidenceError && <div role="alert" className="text-xs"><p>{evidenceError}</p><button type="button" className="btn-secondary mt-2" onClick={() => { setEvidenceError(null); setEvidenceAttempt((value) => value + 1); }}>Retry frozen evidence</button></div>}
            {evidence && <div><label htmlFor={`${formId}-source`} className="text-xs font-semibold">Frozen source excerpt</label>
              <select id={`${formId}-source`} className={control} value={chunkId} disabled={saving || disabled}
                onChange={(event) => { setChunkId(event.target.value); setQuote(""); }}>
                {evidence.items.map((item, itemIndex) => <option key={item.chunk_id} value={item.chunk_id}>{item.title} · Excerpt {itemIndex + 1}</option>)}
              </select>
              {excerpt ? <blockquote className="mt-3 max-h-52 overflow-y-auto whitespace-pre-wrap border-l-2 border-[var(--border-strong)] pl-3 text-xs">{excerpt.content}</blockquote>
                : <p className="mt-2 text-xs">No frozen excerpts are available. Recording is blocked.</p>}
            </div>}
            <div><label htmlFor={`${formId}-quote`} className="text-xs font-semibold">Exact supporting quote</label>
              <textarea id={`${formId}-quote`} className={`${control} resize-y`} value={quote} rows={3} minLength={12} maxLength={2000} required disabled={saving || disabled}
                aria-describedby={`${formId}-quote-help`} onChange={(event) => setQuote(event.target.value)} />
              <p id={`${formId}-quote-help`} className="mt-1 text-xs text-[var(--text-secondary)]">Copy at least 12 characters exactly from the selected frozen excerpt.</p>
            </div>
            <div><label htmlFor={`${formId}-reason`} className="text-xs font-semibold">Why is this not a defect?</label>
              <textarea id={`${formId}-reason`} className={`${control} resize-y`} value={reason} rows={4} minLength={30} maxLength={4000} required disabled={saving || disabled}
                aria-describedby={`${formId}-reason-help`} onChange={(event) => setReason(event.target.value)} />
              <p id={`${formId}-reason-help`} className="mt-1 text-xs text-[var(--text-secondary)]">Explain the field-to-source comparison in at least 30 characters. This judgment cannot be overwritten.</p>
            </div>
            <div className="flex flex-wrap gap-2"><button type="submit" className="btn-primary" disabled={!valid || saving || disabled}>{saving ? "Recording…" : "Record human review"}</button>
              <button id={`${formId}-cancel`} type="button" className="btn-secondary" disabled={saving} onClick={() => cancel(index)}>Cancel</button></div>
          </form>}
        </article>;
      })}
  </section>;
}
