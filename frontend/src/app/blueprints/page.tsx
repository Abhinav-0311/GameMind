"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  BlueprintExportResponse,
  BlueprintResponse,
  BlueprintRuntimeBundleResponse,
  BlueprintSectionResponse,
  DocumentResponse,
  MaterializationReportResponse,
} from "@/lib/api";

interface ReviewSection {
  id: string;
  title: string;
  description: string;
  section: BlueprintSectionResponse;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function statusLabel(blueprint: BlueprintResponse | null) {
  if (!blueprint) return "No blueprint";
  if (blueprint.materialization_manifest) return "Runtime ready";
  if (blueprint.status === "approved") return "Approved";
  return "Draft";
}

function confidenceClass(confidence: string) {
  if (confidence === "High") return "border-emerald-500/20 bg-emerald-500/10 text-[var(--foreground)]";
  if (confidence === "Medium") return "border-amber-500/20 bg-amber-500/10 text-[var(--foreground)]";
  return "border-[var(--border-strong)] bg-[var(--card-muted)] text-[var(--text-secondary)]";
}

function readableValue(value: unknown): string {
  if (Array.isArray(value)) {
    if (value.length === 0) return "None detected";
    return value
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const record = item as Record<string, unknown>;
          return String(record.title || record.name || record.objective || record.description || JSON.stringify(record));
        }
        return String(item);
      })
      .join(", ");
  }

  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => `${key.replaceAll("_", " ")}: ${readableValue(entry)}`)
      .join(" | ");
  }

  return value === undefined || value === null || value === "" ? "Not detected" : String(value);
}

function sectionPreview(section: BlueprintSectionResponse) {
  return Object.entries(section.content).slice(0, 4);
}

function reportCount(section?: { created: string[]; updated: string[]; skipped: string[] }) {
  if (!section) return 0;
  return section.created.length + section.updated.length + section.skipped.length;
}

function skippedCount(report: MaterializationReportResponse | null) {
  if (!report) return 0;
  return report.npcs.skipped.length + report.quests.skipped.length + report.memories.skipped.length + report.flags.skipped.length;
}

function reportSectionRows(report: MaterializationReportResponse) {
  return [
    ["NPCs", report.npcs, "Characters available to dialogue and Unity runtime."],
    ["Quests", report.quests, "Playable objectives, rewards, and quest board data."],
    ["Memories", report.memories, "Facts available to NPC memory and continuity systems."],
    ["World flags", report.flags, "Runtime switches for gates, level state, and conditions."],
  ] as const;
}

const sectionGuidance: Record<string, { use: string; runtime: string }> = {
  summary: {
    use: "Use this as the one-paragraph pitch for the game. If it is unclear, the uploaded GDD needs a sharper premise.",
    runtime: "Defines the player role, world premise, and high-level context shown to NPC and quest systems.",
  },
  narrative: {
    use: "Use this to check whether the conflict, factions, and story stakes are strong enough to support quests.",
    runtime: "Feeds dialogue framing, faction references, quest motivations, and world-state decisions.",
  },
  art: {
    use: "Use this as the visual direction brief before creating concept art, UI moodboards, or level dressing.",
    runtime: "Helps Unity-facing exports describe mood, palette, environment language, and presentation tone.",
  },
  npcs: {
    use: "Use this to decide which characters are worth implementing first, and what role each one serves.",
    runtime: "Can materialize into NPC profiles with names, personalities, dialogue styles, and animation hints.",
  },
  memory: {
    use: "Use this to decide what NPCs should remember between interactions. Keep only facts that affect future behavior.",
    runtime: "Seeds narrative memory records used by dialogue, hints, and quest continuity.",
  },
  levels: {
    use: "Use this to turn lore into playable spaces, gates, objectives, and progression beats.",
    runtime: "Informs level tags, world flags, encounter placement, and objective availability.",
  },
  quests: {
    use: "Use this to choose the first playable missions. Prefer quests that prove the core fantasy quickly.",
    runtime: "Can materialize into quest records, objectives, rewards, and hintable progression paths.",
  },
  unity: {
    use: "Use this to inspect the runtime shape before connecting Unity. This is the bridge from plan to playable scene.",
    runtime: "Summarizes NPCs, quests, levels, art style, and versioning for Unity-facing endpoints.",
  },
};

function SectionBrief({ section }: { section: ReviewSection }) {
  const guidance = sectionGuidance[section.id];
  const previewEntries = sectionPreview(section.section);
  const hasWarnings = section.section.warnings.length > 0;

  return (
    <article className="space-y-6 p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <p className="mono-label text-[var(--text-tertiary)]">Section brief</p>
          <h3 className="text-2xl font-semibold tracking-normal text-[var(--foreground)]">{section.title}</h3>
          <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{section.description}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <span className={`rounded-full border px-3 py-1 text-xs ${confidenceClass(section.section.confidence)}`}>
            {section.section.confidence} confidence
          </span>
          <span className="rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] px-3 py-1 text-xs text-[var(--text-secondary)]">
            {section.section.citations.length} citations
          </span>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card-muted)]">
          <div className="border-b border-[var(--border)] px-5 py-4">
            <p className="mono-label text-[var(--text-tertiary)]">What GameMind found</p>
          </div>

          {previewEntries.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm font-semibold text-[var(--foreground)]">No usable section data yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Add more detail to the source document, then regenerate the blueprint.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)] bg-[var(--card)]">
              {previewEntries.map(([key, value]) => (
                <div key={key} className="p-5">
                  <p className="mono-label text-[var(--text-tertiary)]">{key.replaceAll("_", " ")}</p>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--foreground)]">{readableValue(value)}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
            <p className="mono-label text-[var(--text-tertiary)]">How to use this</p>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              {guidance?.use ?? "Review this section as a design decision before shipping it into runtime data."}
            </p>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
            <p className="mono-label text-[var(--text-tertiary)]">Runtime impact</p>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              {guidance?.runtime ?? "This section contributes to the runtime bundle used by the Unity-facing flow."}
            </p>
          </section>

          {hasWarnings ? (
            <section className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-5">
              <p className="text-sm font-semibold text-amber-800">Needs more source detail</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-800/90">
                {section.section.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : (
            <section className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5">
              <p className="text-sm font-semibold text-[var(--foreground)]">No blocking gaps detected</p>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                The source document has enough detail for this section at MVP level.
              </p>
            </section>
          )}
        </aside>
      </div>

      <details className="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--accent)] outline-none transition hover:text-[var(--accent-hover)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]/20">
          Full structured section
        </summary>
        <pre className="max-h-80 overflow-auto border-t border-[var(--border)] p-4 text-xs leading-5 text-[var(--text-secondary)]">
          {JSON.stringify(section.section.content, null, 2)}
        </pre>
      </details>
    </article>
  );
}

function ReportStat({ label, value, warn = false }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-2">
      <div className={`text-sm font-semibold ${warn ? "text-amber-800" : "text-[var(--foreground)]"}`}>{value}</div>
      <div className="mt-1 text-[10px] font-semibold uppercase tracking-normal text-[var(--text-tertiary)]">{label}</div>
    </div>
  );
}

export default function BlueprintsDashboard() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [blueprints, setBlueprints] = useState<BlueprintResponse[]>([]);
  const [activeBlueprint, setActiveBlueprint] = useState<BlueprintResponse | null>(null);
  const [activeSectionId, setActiveSectionId] = useState("summary");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isMaterializing, setIsMaterializing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [exportData, setExportData] = useState<BlueprintExportResponse | null>(null);
  const [runtimeBundle, setRuntimeBundle] = useState<BlueprintRuntimeBundleResponse | null>(null);
  const [materializeReport, setMaterializeReport] = useState<MaterializationReportResponse | null>(null);

  const loadInitialData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [docs, existingBlueprints] = await Promise.all([
        api.getDocuments(),
        api.getBlueprints(),
      ]);

      setDocuments(docs);
      setBlueprints(existingBlueprints);

      if (docs.length > 0) {
        setSelectedDocId((current) => current || docs[0].id);
      }

      if (existingBlueprints.length > 0) {
        setActiveBlueprint((current) => current || existingBlueprints[0]);
      }
    } catch (err) {
      console.error(err);
      setError("Could not load Blueprints. Check that the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    Promise.resolve().then(loadInitialData);
  }, []);

  const reviewSections: ReviewSection[] = useMemo(() => {
    if (!activeBlueprint) return [];

    return [
      {
        id: "summary",
        title: "Game summary",
        description: "Premise, genre, world setup, and core player role.",
        section: activeBlueprint.summary,
      },
      {
        id: "narrative",
        title: "Narrative direction",
        description: "Conflict, factions, story themes, and lore background.",
        section: activeBlueprint.narrative_direction,
      },
      {
        id: "art",
        title: "Art style",
        description: "Visual identity, palette, and presentation language.",
        section: activeBlueprint.art_style_direction,
      },
      {
        id: "npcs",
        title: "NPC cast",
        description: "Characters, roles, personalities, and dialogue setup.",
        section: activeBlueprint.npc_archetypes,
      },
      {
        id: "memory",
        title: "Memory design",
        description: "Facts and events NPCs should remember at runtime.",
        section: activeBlueprint.npc_memory_design,
      },
      {
        id: "levels",
        title: "Level design",
        description: "Spaces, gates, activities, and progression ideas.",
        section: activeBlueprint.level_design_suggestions,
      },
      {
        id: "quests",
        title: "Quest hooks",
        description: "Objectives, rewards, and playable mission seeds.",
        section: activeBlueprint.quest_hooks,
      },
      {
        id: "unity",
        title: "Unity preview",
        description: "Runtime-facing shape prepared for the Unity client.",
        section: activeBlueprint.unity_runtime_preview,
      },
    ];
  }, [activeBlueprint]);

  const activeSection = reviewSections.find((section) => section.id === activeSectionId) || reviewSections[0];
  const selectedDocument = documents.find((doc) => doc.id === selectedDocId);
  const blueprintIsApproved = activeBlueprint?.status === "approved";
  const blueprintIsMaterialized = Boolean(activeBlueprint?.materialization_manifest);
  const payload = runtimeBundle || exportData;
  const skippedRuntimeItems = skippedCount(materializeReport);

  const handleGenerate = async () => {
    if (!selectedDocId) return;

    setIsGenerating(true);
    setError(null);
    setSuccess(null);
    setMaterializeReport(null);
    setExportData(null);
    setRuntimeBundle(null);

    try {
      const newBlueprint = await api.generateBlueprint(selectedDocId);
      const existingBlueprints = await api.getBlueprints();
      setBlueprints(existingBlueprints);
      setActiveBlueprint(newBlueprint);
      setActiveSectionId("summary");
      setSuccess("Blueprint generated. Review the sections before approval.");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Blueprint generation failed.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!activeBlueprint) return;

    setIsApproving(true);
    setError(null);
    setSuccess(null);

    try {
      const updated = await api.approveBlueprint(activeBlueprint.id);
      setActiveBlueprint(updated);
      setBlueprints((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSuccess("Blueprint approved. It can now be materialized into runtime data.");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Could not approve blueprint.");
    } finally {
      setIsApproving(false);
    }
  };

  const handleMaterialize = async () => {
    if (!activeBlueprint) return;

    setIsMaterializing(true);
    setError(null);
    setSuccess(null);
    setMaterializeReport(null);

    try {
      const report = await api.materializeBlueprint(activeBlueprint.id);
      const existingBlueprints = await api.getBlueprints();
      const updated = existingBlueprints.find((item) => item.id === activeBlueprint.id) || activeBlueprint;
      setMaterializeReport(report);
      setBlueprints(existingBlueprints);
      setActiveBlueprint(updated);
      setSuccess("Runtime data materialized. Unity can now fetch the runtime bundle.");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Materialization failed.");
    } finally {
      setIsMaterializing(false);
    }
  };

  const handleExport = async () => {
    if (!activeBlueprint) return;

    setError(null);
    setSuccess(null);

    try {
      const exported = await api.exportBlueprint(activeBlueprint.id);
      setExportData(exported);
      setRuntimeBundle(null);
    } catch (err) {
      console.error(err);
      setError("Could not create the Unity export.");
    }
  };

  const handleRuntimeBundle = async () => {
    if (!activeBlueprint) return;

    setError(null);
    setSuccess(null);

    try {
      const bundle = await api.getBlueprintRuntimeBundle(activeBlueprint.id);
      setRuntimeBundle(bundle);
      setExportData(null);
    } catch (err) {
      console.error(err);
      setError("Could not fetch runtime bundle.");
    }
  };

  const handleCopyPayload = async () => {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setSuccess("Payload copied to clipboard.");
  };

  return (
    <div className="mx-auto w-full max-w-[96rem] min-w-0 space-y-8 pb-16">
      <section className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <div className="page-kicker">
            Blueprints
          </div>
          <div className="space-y-3">
            <h1 className="display-title text-[1.9rem] leading-tight sm:text-[2.35rem]">
              Blueprint workspace
            </h1>
            <p className="max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
              Select one source, generate one blueprint, review the sections, then ship approved runtime data.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {!blueprintIsMaterialized && (
            <Link
              href="/knowledge"
              className="btn-secondary"
            >
              Upload source
            </Link>
          )}
          {activeBlueprint && !blueprintIsApproved && (
            <button
              type="button"
              onClick={handleApprove}
              disabled={isApproving}
              className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isApproving ? "Approving" : "Approve blueprint"}
            </button>
          )}
          {activeBlueprint && blueprintIsApproved && !blueprintIsMaterialized && (
            <button
              type="button"
              onClick={handleMaterialize}
              disabled={isMaterializing}
              className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isMaterializing ? "Materializing" : "Materialize runtime"}
            </button>
          )}
        </div>
      </section>

      {(error || success) && (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            error
              ? "border-rose-500/25 bg-rose-500/10 text-rose-700"
              : "border-emerald-500/25 bg-emerald-500/10 text-emerald-800"
          }`}
        >
          {error || success}
        </div>
      )}

      <section className="min-w-0 space-y-7">
        <aside className="grid min-w-0 gap-6 xl:grid-cols-[420px_1fr]">
          <section className="panel min-w-0 overflow-hidden rounded-2xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="mono-label text-[var(--text-tertiary)]">1 / Source</p>
                <h2 className="mt-2 text-xl font-semibold tracking-normal text-[var(--foreground)]">Generate blueprint</h2>
              </div>
              <span className="rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent)]">
                $0 local
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              Use one GDD or lore file as the source of truth.
            </p>

            <div className="mt-5 space-y-4">
              {documents.length === 0 ? (
                <div className="rounded-md border border-[var(--border-strong)] bg-[var(--card)] p-4">
                  <p className="text-sm font-semibold text-[var(--foreground)]">No documents yet</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    Upload a GDD before generating a blueprint.
                  </p>
                  <Link
                    href="/knowledge"
                    className="mt-4 inline-flex min-h-10 items-center rounded-md bg-[var(--foreground)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--foreground)]"
                  >
                    Upload document
                  </Link>
                </div>
              ) : (
                <>
                  <label className="block text-xs font-semibold text-[var(--foreground)]" htmlFor="source-document">
                    Source document
                  </label>
                  <select
                    id="source-document"
                    value={selectedDocId}
                    onChange={(event) => setSelectedDocId(event.target.value)}
                    className="min-h-11 w-full min-w-0 rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/15"
                  >
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.title}
                      </option>
                    ))}
                  </select>

                  <div className="rounded-xl border border-[var(--border)] bg-[var(--card-muted)] p-4">
                    <div className="break-words text-sm font-medium text-[var(--foreground)]">
                      {selectedDocument?.title || "Selected document"}
                    </div>
                    <div className="mt-2 text-sm text-[var(--text-secondary)]">
                      {selectedDocument?.chunks_count || 0} searchable chunks
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={isGenerating || !selectedDocId}
                    className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isGenerating ? "Generating blueprint" : "Generate blueprint"}
                  </button>
                </>
              )}
            </div>
          </section>

          <section className="panel min-w-0 overflow-hidden rounded-2xl">
            <div className="border-b border-[var(--border)] p-5">
              <p className="mono-label text-[var(--text-tertiary)]">2 / Select</p>
              <h2 className="mt-2 text-xl font-semibold tracking-normal text-[var(--foreground)]">Blueprints</h2>
            </div>

            {isLoading ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-16 animate-pulse rounded-md bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : blueprints.length === 0 ? (
              <div className="p-5 text-sm leading-6 text-[var(--text-secondary)]">
                No generated blueprints yet.
              </div>
            ) : (
              <div className="grid max-h-[20rem] gap-2 overflow-y-auto p-2 sm:grid-cols-2 xl:grid-cols-3">
                {blueprints.map((blueprint) => {
                  const selected = activeBlueprint?.id === blueprint.id;
                  return (
                    <button
                      key={blueprint.id}
                      type="button"
                      onClick={() => {
                        setActiveBlueprint(blueprint);
                        setActiveSectionId("summary");
                        setExportData(null);
                        setRuntimeBundle(null);
                        setMaterializeReport(null);
                      }}
                      className={`block w-full rounded-xl px-3 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20 ${
                        selected ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--card-muted)]"
                      }`}
                    >
                      <div className="truncate text-sm font-medium text-[var(--foreground)]">{blueprint.title}</div>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <span className="text-xs text-[var(--text-secondary)]">{formatDate(blueprint.created_at)}</span>
                        <span className={`rounded-full border px-2 py-0.5 text-xs ${confidenceClass(blueprint.summary.confidence)}`}>
                          {statusLabel(blueprint)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </aside>

        <main className="min-w-0 space-y-6">
          {!activeBlueprint ? (
            <section className="panel rounded-xl px-6 py-16 text-center">
              <h2 className="font-display text-3xl font-semibold text-[var(--foreground)]">Generate your first blueprint</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Pick a source document and GameMind will extract a structured game plan ready for review.
              </p>
            </section>
          ) : (
            <>
              <section className="panel overflow-hidden rounded-2xl">
                <div className="border-b border-[var(--border)] px-6 py-5">
                  <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0 space-y-3">
                      <p className="mono-label text-[var(--text-tertiary)]">3 / Review</p>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate text-2xl font-semibold tracking-normal text-[var(--foreground)] sm:text-3xl">
                          {activeBlueprint.title}
                        </h2>
                        <span className="rounded-full border border-[var(--border-strong)] bg-[var(--card-muted)] px-3 py-1 text-xs font-medium text-[var(--foreground)]">
                          {statusLabel(activeBlueprint)}
                        </span>
                      </div>
                      <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                        Review each section. Approval is the boundary between draft generation and runtime data.
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={handleExport}
                        className="btn-secondary"
                      >
                        Export
                      </button>
                      {blueprintIsMaterialized && (
                        <button
                          type="button"
                          onClick={handleRuntimeBundle}
                          className="btn-secondary"
                        >
                          Runtime bundle
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div>
                  <nav className="border-b border-[var(--border)] px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {reviewSections.map((section) => {
                        const selected = activeSection?.id === section.id;
                        return (
                          <button
                            key={section.id}
                            type="button"
                            onClick={() => setActiveSectionId(section.id)}
                            className={`shrink-0 rounded-full px-4 py-2 text-left text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20 ${
                              selected ? "bg-[var(--accent-soft)] text-[var(--foreground)]" : "text-[var(--text-secondary)] hover:bg-[var(--card-muted)] hover:text-[var(--foreground)]"
                            }`}
                          >
                            {section.title}
                          </button>
                        );
                      })}
                    </div>
                  </nav>

                  {activeSection && (
                    <SectionBrief section={activeSection} />
                  )}
                </div>
              </section>

              {materializeReport && (
                <section className="panel overflow-hidden rounded-2xl">
                  <div className="flex flex-col gap-4 border-b border-[var(--border)] p-6 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="mono-label text-[var(--text-tertiary)]">Runtime result</p>
                      <h2 className="mt-2 font-display text-3xl font-semibold text-[var(--foreground)]">Materialization complete</h2>
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                        GameMind created or updated safe runtime records and skipped anything that should not enter the
                        playable scene automatically.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-800">
                        {materializeReport.status}
                      </span>
                      {skippedRuntimeItems > 0 && (
                        <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-800">
                          {skippedRuntimeItems} skipped
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-4">
                    {reportSectionRows(materializeReport).map(([label, report, description]) => (
                      <div key={label} className="panel-muted rounded-xl p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-[var(--foreground)]">{label}</div>
                            <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{description}</div>
                          </div>
                          <div className="text-2xl font-semibold text-[var(--foreground)]">
                            {reportCount(report)}
                          </div>
                        </div>
                        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                          <ReportStat label="Created" value={report.created.length} />
                          <ReportStat label="Updated" value={report.updated.length} />
                          <ReportStat label="Skipped" value={report.skipped.length} warn={report.skipped.length > 0} />
                        </div>
                      </div>
                    ))}
                  </div>

                  {(materializeReport.warnings.length > 0 || skippedRuntimeItems > 0) && (
                    <div className="border-t border-[var(--border)] p-5">
                      <div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <h3 className="text-base font-semibold text-[var(--foreground)]">Review before Unity</h3>
                            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                              Skipped items were blocked from runtime data. This usually means a generated fragment,
                              duplicate manual record, or missing valid NPC quest giver needs human review.
                            </p>
                          </div>
                          <Link href="/npcs" className="btn-secondary shrink-0">
                            Review NPCs
                          </Link>
                        </div>
                        {materializeReport.warnings.length > 0 && (
                          <ul className="mt-5 space-y-2 text-sm leading-6 text-amber-900">
                            {materializeReport.warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}

                  {skippedRuntimeItems === 0 && (
                    <div className="border-t border-[var(--border)] p-5">
                      <div className="flex flex-col gap-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-[var(--foreground)]">Runtime data is clean</h3>
                          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                            Open the simulator next and test dialogue, quest acceptance, and progressive hints.
                          </p>
                        </div>
                        <Link href="/vertical-slice" className="btn-primary shrink-0">
                          Open Runtime Test
                        </Link>
                      </div>
                    </div>
                  )}
                </section>
              )}

              {payload && (
                <section className="panel overflow-hidden rounded-xl">
                  <div className="flex flex-col gap-4 border-b border-[var(--border)] p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h2 className="font-display text-2xl font-semibold text-[var(--foreground)]">
                        {runtimeBundle ? "Runtime bundle" : "Unity export"}
                      </h2>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">Use this only when inspecting the Unity contract.</p>
                    </div>
                    <button
                      type="button"
                      onClick={handleCopyPayload}
                      className="min-h-10 rounded-md bg-[var(--foreground)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--foreground)]"
                    >
                      Copy data
                    </button>
                  </div>
                  <pre className="max-h-96 overflow-auto p-5 text-xs leading-5 text-[var(--text-secondary)]">
                    {JSON.stringify(payload, null, 2)}
                  </pre>
                </section>
              )}
            </>
          )}
        </main>
      </section>
    </div>
  );
}
