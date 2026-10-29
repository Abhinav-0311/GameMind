import type { DraftQualityAdvisory, DraftQualityEvaluation } from "@/lib/api";

function comparedValues({ check, values }: DraftQualityAdvisory): [string, unknown][] {
  if (check === "objective_text_copied_as_dialogue") {
    return [["Dialogue", values.dialogue], ...(Array.isArray(values.objectives)
      ? values.objectives.map((objective): [string, unknown] => ["Matching objective", objective.value]) : [])];
  }
  if (check === "quest_label_mismatch") return [["Situation", values.situation], ["Linked quest ID", values.quest_id]];
  return [["Rule text", values.rule]];
}

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
              <code className="mt-1 block text-xs text-[var(--text-secondary)]">#{advisory.id.slice(0, 8)}</code>
              <p className="mt-1 text-sm leading-6">{advisory.message}</p>
              <dl className="mt-3 space-y-3 text-sm leading-6">
                {comparedValues(advisory).map(([label, value], index) => typeof value === "string" && (
                  <div key={`${label}-${index}`}>
                    <dt className="text-xs font-medium text-[var(--text-secondary)]">{label}</dt>
                    <dd className="whitespace-pre-wrap break-words">{value}</dd>
                  </div>
                ))}
              </dl>
              {advisory.paths.map((path) => <code key={path} className="mt-1 block break-all text-xs leading-5 text-[var(--text-secondary)]">{path}</code>)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
