import type { DraftQualityEvaluation } from "@/lib/api";

export default function DraftQualityAdvisories({ evaluation }: { evaluation?: DraftQualityEvaluation | null }) {
  if (!evaluation) return null;
  return (
    <section className="border-b border-[var(--border)] p-5" aria-label="Advisories (non-blocking)">
      <h2 className="text-sm font-semibold">Advisories (non-blocking)</h2>
      <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">Exact local checks only. These do not affect approval and never change the draft.</p>
      {evaluation.advisories.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">No exact matches found; this is not a quality guarantee.</p>
      ) : (
        <ul className="mt-4 space-y-5">
          {evaluation.advisories.map((advisory) => (
            <li key={advisory.id}>
              <p className="text-xs font-medium text-[var(--text-secondary)]">{advisory.severity} · {advisory.check.replaceAll("_", " ")}</p>
              <p className="mt-1 text-sm leading-6">{advisory.message}</p>
              {advisory.paths.map((path) => <code key={path} className="mt-1 block break-all text-xs leading-5 text-[var(--text-secondary)]">{path}</code>)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
