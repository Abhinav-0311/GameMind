"use client";

import { useEffect, useState } from "react";
import { api, ApiRequestError, requestFailureMessage, type DesignAgentEvidence } from "@/lib/api";

// The parent keys this component by run and artifact, keeping reads version-bound.
export default function FrozenDesignEvidence({ runId, artifactId, references }: {
  runId: string;
  artifactId: string;
  references: string[];
}) {
  const [open, setOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ evidence?: DesignAgentEvidence; error?: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    let current = true;
    api.getDesignAgentEvidence(runId, artifactId).then((evidence) => {
      if (evidence.artifact_id !== artifactId) throw new Error("Evidence artifact mismatch");
      if (current) setResult({ evidence });
    }).catch((error) => {
      if (current) setResult({ error: error instanceof ApiRequestError && error.status === 404
        ? "Frozen evidence is unavailable for this draft. No current document text has been substituted."
        : requestFailureMessage(error, "Frozen evidence") });
    });
    return () => { current = false; };
  }, [open, attempt, runId, artifactId]);

  const ids = [...new Set(references)];
  const evidence = result?.evidence;
  return (
    <details className="border-b border-[var(--border)] px-5 sm:px-7" onToggle={(event) => {
      // Keep the first read cached while collapsed; retry is always explicit.
      if (event.currentTarget.open) setOpen(true);
    }}>
      <summary className="min-h-11 w-fit cursor-pointer rounded-md py-2 text-sm font-medium leading-7 text-[var(--text-secondary)] hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
        Source evidence
      </summary>
      <div className="space-y-4 pb-5 text-sm leading-6">
        <p className="text-xs leading-5 text-[var(--text-secondary)]">
          Frozen excerpts for this draft, not the latest document. Citations identify sources; they do not prove every claim is supported.
        </p>
        {!result && <p role="status" className="text-[var(--text-secondary)]">Loading frozen evidence…</p>}
        {result?.error && <div role="alert">
          <p className="text-[var(--warning-text)]">{result.error}</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => { setResult(null); setAttempt((value) => value + 1); }}>Retry evidence</button>
        </div>}
        {evidence && <>
          <p className="text-xs text-[var(--text-secondary)]">Evidence revision {evidence.revision}</p>
          {ids.length === 0 && <p className="text-[var(--text-secondary)]">No evidence references were recorded for this section.</p>}
          {ids.map((id) => {
            const item = evidence.items.find((entry) => entry.chunk_id === id);
            return item ? <div key={id} className="space-y-2">
              <p className="font-semibold text-[var(--foreground)]">{item.title}</p>
              <p className="text-xs text-[var(--text-secondary)]"><span className="break-all">Reference {item.chunk_id}</span>{item.chunk_index !== null ? <span className="inline-block"> · Chunk index {item.chunk_index}</span> : null}</p>
              <blockquote className="whitespace-pre-wrap border-l-2 border-[var(--border-strong)] pl-4 text-[var(--foreground)] [overflow-wrap:anywhere]">{item.content}</blockquote>
            </div> : <p key={id} className="break-all text-[var(--warning-text)]">Unavailable in this frozen snapshot: {id}</p>;
          })}
        </>}
      </div>
    </details>
  );
}
