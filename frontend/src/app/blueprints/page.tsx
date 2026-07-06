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
  if (confidence === "High") return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  if (confidence === "Medium") return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  return "border-[#313943] bg-[#15191f] text-[#aab4c0]";
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
  return Object.entries(section.content).slice(0, 5);
}

function reportCount(section?: { created: string[]; updated: string[]; skipped: string[] }) {
  if (!section) return 0;
  return section.created.length + section.updated.length + section.skipped.length;
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
      setError("Could not load Blueprint Studio. Check that the backend is running.");
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

  const workflowSteps = [
    {
      label: "Source",
      value: selectedDocument ? selectedDocument.title : "Choose a document",
      complete: documents.length > 0,
    },
    {
      label: "Blueprint",
      value: activeBlueprint ? activeBlueprint.title : "Generate plan",
      complete: Boolean(activeBlueprint),
    },
    {
      label: "Approval",
      value: activeBlueprint ? statusLabel(activeBlueprint) : "Review first",
      complete: Boolean(activeBlueprint && (blueprintIsApproved || blueprintIsMaterialized)),
    },
    {
      label: "Runtime",
      value: blueprintIsMaterialized ? "Unity ready" : "Not materialized",
      complete: blueprintIsMaterialized,
    },
  ];

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
      setError("Could not create Unity export payload.");
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
    <div className="page-shell space-y-10">
      <section className="space-y-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <div className="page-kicker">
              Blueprint Studio
            </div>
            <div className="space-y-3">
              <h1 className="display-title text-[2.65rem] leading-tight sm:text-6xl">
                Turn a GDD into runtime-ready game systems.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[#9aa5b4]">
                Generate a structured plan for narrative, art direction, NPCs, memory, quests, level ideas, and Unity
                runtime data. Review it, approve it, then materialize it.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link
              href="/knowledge"
              className="inline-flex min-h-10 items-center rounded-md border border-[#2f3742] px-4 text-sm font-semibold text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
            >
              Upload source
            </Link>
            {activeBlueprint && !blueprintIsApproved && (
              <button
                type="button"
                onClick={handleApprove}
                disabled={isApproving}
                className="inline-flex min-h-10 items-center rounded-md bg-[#f5f7fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:bg-[#252b34] disabled:text-[#66717f]"
              >
                {isApproving ? "Approving" : "Approve blueprint"}
              </button>
            )}
            {activeBlueprint && blueprintIsApproved && (
              <button
                type="button"
                onClick={handleMaterialize}
                disabled={isMaterializing}
                className="inline-flex min-h-10 items-center rounded-md bg-[#f5f7fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:bg-[#252b34] disabled:text-[#66717f]"
              >
                {isMaterializing ? "Materializing" : "Materialize runtime"}
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          {workflowSteps.map((step, index) => (
            <div key={step.label} className="panel-muted rounded-xl p-4">
              <div className="flex items-center justify-between">
                <span className="mono-label text-[#7f8b9a]">
                  {index + 1}. {step.label}
                </span>
                <span
                  className={`h-2 w-2 rounded-full ${step.complete ? "bg-emerald-300" : "bg-[#3a424d]"}`}
                  aria-hidden="true"
                />
              </div>
              <div className="mt-3 truncate text-sm font-semibold text-[#f5f7fa]">{step.value}</div>
            </div>
          ))}
        </div>

        {(error || success) && (
          <div
            className={`rounded-md border px-4 py-3 text-sm ${
              error
                ? "border-rose-500/25 bg-rose-500/10 text-rose-200"
                : "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
            }`}
          >
            {error || success}
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-5">
          <section className="panel rounded-xl p-5">
            <h2 className="font-display text-2xl font-semibold text-[#f5f7fa]">Create from source</h2>
            <p className="mt-2 text-sm leading-6 text-[#9aa5b4]">
              Choose the GDD or lore document that best represents this game idea.
            </p>

            <div className="mt-5 space-y-4">
              {documents.length === 0 ? (
                <div className="rounded-md border border-[#2f3742] bg-[#090b0e] p-4">
                  <p className="text-sm font-semibold text-[#f5f7fa]">No documents yet</p>
                  <p className="mt-2 text-sm leading-6 text-[#9aa5b4]">
                    Upload a GDD before generating a blueprint.
                  </p>
                  <Link
                    href="/knowledge"
                    className="mt-4 inline-flex min-h-10 items-center rounded-md bg-[#f5f7fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa]"
                  >
                    Upload document
                  </Link>
                </div>
              ) : (
                <>
                  <label className="block text-xs font-semibold text-[#dbe2ea]" htmlFor="source-document">
                    Source document
                  </label>
                  <select
                    id="source-document"
                    value={selectedDocId}
                    onChange={(event) => setSelectedDocId(event.target.value)}
                    className="min-h-11 w-full rounded-md border border-[#252b34] bg-[#090b0e] px-3 text-sm text-[#f5f7fa] outline-none transition hover:border-[#38414d] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/15"
                  >
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.title}
                      </option>
                    ))}
                  </select>

                  <div className="rounded-md border border-[#242a32] bg-[#090b0e] p-4">
                    <div className="text-sm font-medium text-[#f5f7fa]">
                      {selectedDocument?.title || "Selected document"}
                    </div>
                    <div className="mt-2 text-sm text-[#9aa5b4]">
                      {selectedDocument?.chunks_count || 0} searchable chunks
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={isGenerating || !selectedDocId}
                    className="min-h-11 w-full rounded-md bg-[#f5f7fa] text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:bg-[#252b34] disabled:text-[#66717f]"
                  >
                    {isGenerating ? "Generating blueprint" : "Generate blueprint"}
                  </button>
                </>
              )}
            </div>
          </section>

          <section className="panel overflow-hidden rounded-xl">
            <div className="border-b border-[#242a32] p-5">
              <h2 className="font-display text-2xl font-semibold text-[#f5f7fa]">Recent blueprints</h2>
              <p className="mt-1 text-sm text-[#9aa5b4]">Select a plan to review or ship.</p>
            </div>

            {isLoading ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-16 animate-pulse rounded-md bg-[#15191f]" />
                ))}
              </div>
            ) : blueprints.length === 0 ? (
              <div className="p-5 text-sm leading-6 text-[#9aa5b4]">
                No generated blueprints yet.
              </div>
            ) : (
              <div className="max-h-[28rem] divide-y divide-[#20262e] overflow-y-auto">
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
                      className={`block w-full px-5 py-4 text-left transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20 ${
                        selected ? "bg-[#15191f]" : "hover:bg-[#121820]"
                      }`}
                    >
                      <div className="truncate text-sm font-semibold text-[#f5f7fa]">{blueprint.title}</div>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <span className="text-xs text-[#7f8b9a]">{formatDate(blueprint.created_at)}</span>
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

        <main className="space-y-6">
          {!activeBlueprint ? (
            <section className="panel rounded-xl px-6 py-16 text-center">
              <h2 className="font-display text-3xl font-semibold text-[#f5f7fa]">Generate your first blueprint</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#9aa5b4]">
                Pick a source document and GameMind will extract a structured game plan ready for review.
              </p>
            </section>
          ) : (
            <>
              <section className="panel overflow-hidden rounded-xl">
                <div className="border-b border-[#242a32] px-6 py-5">
                  <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate font-display text-3xl font-semibold text-[#f5f7fa]">
                          {activeBlueprint.title}
                        </h2>
                        <span className="rounded-full border border-[#2f3742] bg-[#15191f] px-3 py-1 text-xs font-medium text-[#dbe2ea]">
                          {statusLabel(activeBlueprint)}
                        </span>
                      </div>
                      <p className="max-w-2xl text-sm leading-6 text-[#9aa5b4]">
                        Review each section. Approval is the boundary between draft generation and runtime data.
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={handleExport}
                        className="min-h-10 rounded-md border border-[#2f3742] px-4 text-sm font-semibold text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
                      >
                        Export JSON
                      </button>
                      {blueprintIsMaterialized && (
                        <button
                          type="button"
                          onClick={handleRuntimeBundle}
                          className="min-h-10 rounded-md border border-[#2f3742] px-4 text-sm font-semibold text-[#dbe2ea] transition hover:border-[#8bdff0]/50 hover:text-[#f5f7fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20"
                        >
                          Runtime bundle
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid lg:grid-cols-[260px_1fr]">
                  <nav className="border-b border-[#242a32] p-4 lg:border-b-0 lg:border-r">
                    <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-1">
                      {reviewSections.map((section) => {
                        const selected = activeSection?.id === section.id;
                        return (
                          <button
                            key={section.id}
                            type="button"
                            onClick={() => setActiveSectionId(section.id)}
                            className={`rounded-md px-3 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0]/20 ${
                              selected ? "bg-[#1c222a] text-[#f5f7fa]" : "text-[#9aa5b4] hover:bg-[#15191f] hover:text-[#f5f7fa]"
                            }`}
                          >
                            <div className="text-sm font-semibold">{section.title}</div>
                            <div className="mt-1 line-clamp-2 text-xs leading-5 text-[#7f8b9a]">
                              {section.description}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </nav>

                  {activeSection && (
                    <article className="space-y-6 p-6">
                      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-2">
                          <h3 className="font-display text-3xl font-semibold text-[#f5f7fa]">{activeSection.title}</h3>
                          <p className="max-w-2xl text-sm leading-6 text-[#9aa5b4]">{activeSection.description}</p>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <span className={`rounded-full border px-3 py-1 text-xs ${confidenceClass(activeSection.section.confidence)}`}>
                            {activeSection.section.confidence} confidence
                          </span>
                          <span className="rounded-full border border-[#2f3742] bg-[#15191f] px-3 py-1 text-xs text-[#aab4c0]">
                            {activeSection.section.citations.length} citations
                          </span>
                        </div>
                      </div>

                      {activeSection.section.warnings.length > 0 && (
                        <div className="rounded-md border border-amber-500/25 bg-amber-500/10 px-4 py-3">
                          <div className="text-sm font-semibold text-amber-200">Source detail needed</div>
                          <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-100/90">
                            {activeSection.section.warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="grid gap-3">
                        {sectionPreview(activeSection.section).map(([key, value]) => (
                          <div key={key} className="panel-muted rounded-xl p-5">
                            <div className="mono-label text-[#7f8b9a]">
                              {key.replaceAll("_", " ")}
                            </div>
                            <p className="mt-3 text-base leading-8 text-[#f5f7fa]">{readableValue(value)}</p>
                          </div>
                        ))}
                      </div>

                      <details className="rounded-md border border-[#242a32] bg-[#090b0e]">
                        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[#8bdff0] outline-none transition hover:text-[#b7eef7] focus-visible:ring-2 focus-visible:ring-[#8bdff0]/20">
                          Structured payload
                        </summary>
                        <pre className="max-h-80 overflow-auto border-t border-[#242a32] p-4 text-xs leading-5 text-[#aab4c0]">
                          {JSON.stringify(activeSection.section.content, null, 2)}
                        </pre>
                      </details>
                    </article>
                  )}
                </div>
              </section>

              {materializeReport && (
                <section className="panel rounded-xl p-6">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h2 className="font-display text-3xl font-semibold text-[#f5f7fa]">Materialization complete</h2>
                      <p className="mt-2 text-sm leading-6 text-[#9aa5b4]">
                        Runtime records created, updated, or safely skipped from this blueprint.
                      </p>
                    </div>
                    <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
                      {materializeReport.status}
                    </span>
                  </div>

                  <div className="mt-6 grid gap-3 sm:grid-cols-4">
                    {[
                      ["NPCs", materializeReport.npcs],
                      ["Quests", materializeReport.quests],
                      ["Memories", materializeReport.memories],
                      ["World flags", materializeReport.flags],
                    ].map(([label, report]) => (
                      <div key={label as string} className="panel-muted rounded-xl p-4">
                        <div className="text-sm font-semibold text-[#f5f7fa]">{label as string}</div>
                        <div className="mt-2 text-2xl font-semibold text-[#f5f7fa]">
                          {reportCount(report as MaterializationReportResponse["npcs"])}
                        </div>
                        <div className="mt-1 text-xs text-[#7f8b9a]">runtime operations</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {payload && (
                <section className="panel overflow-hidden rounded-xl">
                  <div className="flex flex-col gap-4 border-b border-[#242a32] p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h2 className="font-display text-2xl font-semibold text-[#f5f7fa]">
                        {runtimeBundle ? "Runtime bundle" : "Export payload"}
                      </h2>
                      <p className="mt-1 text-sm text-[#9aa5b4]">Use this only when inspecting the Unity contract.</p>
                    </div>
                    <button
                      type="button"
                      onClick={handleCopyPayload}
                      className="min-h-10 rounded-md bg-[#f5f7fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f5f7fa]"
                    >
                      Copy payload
                    </button>
                  </div>
                  <pre className="max-h-96 overflow-auto p-5 text-xs leading-5 text-[#aab4c0]">
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
