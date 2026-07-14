"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  BlueprintExportResponse,
  BlueprintComparisonResponse,
  BlueprintProvenanceResponse,
  BlueprintReadinessResponse,
  BlueprintResponse,
  DecisionCoverageResponse,
  GddReviewResponse,
  BlueprintRuntimeBundleResponse,
  BlueprintSectionResponse,
  DocumentResponse,
  MaterializationReportResponse,
} from "@/lib/api";
import { asSourceKind, sourceKindMeta } from "@/lib/sourceKinds";

interface ReviewSection {
  id: string;
  title: string;
  description: string;
  section: BlueprintSectionResponse;
}

interface StepItem {
  label: string;
  detail: string;
  complete: boolean;
  active: boolean;
}

interface ReadinessState {
  blueprintId: string;
  value: BlueprintReadinessResponse;
}

interface DecisionCoverageState {
  documentId: string;
  value: DecisionCoverageResponse;
}

interface ProvenanceState {
  blueprintId: string;
  value: BlueprintProvenanceResponse;
}

const sectionGuidance: Record<string, { use: string; runtime: string }> = {
  summary: {
    use: "Use this as the game pitch. If it feels vague, improve the source document before approving.",
    runtime: "Feeds the basic player role, premise, and world context.",
  },
  narrative: {
    use: "Check whether the conflict, factions, and stakes are strong enough to support quests.",
    runtime: "Frames dialogue, faction references, and quest motivations.",
  },
  art: {
    use: "Use this as a mood direction before concept art, UI styling, or level dressing.",
    runtime: "Describes palette, tone, environment language, and presentation cues.",
  },
  npcs: {
    use: "Decide which characters are worth implementing first and what role each one serves.",
    runtime: "Can become NPC profiles with personality, dialogue style, and animation hints.",
  },
  memory: {
    use: "Keep only facts that should influence future NPC behavior.",
    runtime: "Seeds continuity records used by dialogue, hints, and quests.",
  },
  levels: {
    use: "Turn lore into spaces, gates, objectives, and progression beats.",
    runtime: "Informs level tags, world flags, and objective availability.",
  },
  systems: {
    use: "Check the player loop, progression, and hard constraints before building features around them.",
    runtime: "Provides reviewed mechanics context for engine adapters and future design tools.",
  },
  quests: {
    use: "Choose the first playable missions. Prefer quests that prove the core fantasy quickly.",
    runtime: "Can become quest records, objectives, rewards, and progressive hint paths.",
  },
  unity: {
    use: "Inspect the runtime shape before connecting any game engine.",
    runtime: "Summarizes NPCs, quests, level ideas, art direction, and versioning for API clients.",
  },
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function statusLabel(blueprint: BlueprintResponse | null) {
  if (!blueprint) return "No blueprint";
  if (blueprint.materialization_manifest) return "Runtime ready";
  if (blueprint.status === "approved") return "Approved";
  return "Draft";
}

function readinessLabel(readiness: BlueprintReadinessResponse | null) {
  if (!readiness) return "Checking runtime";
  if (readiness.status === "runtime_ready") return "Runtime ready";
  if (readiness.status === "runtime_review") return "Runtime review";
  return "Planning only";
}

function confidenceTone(confidence: string) {
  if (confidence === "High") return "border-emerald-500/25 bg-emerald-500/10 text-[var(--foreground)]";
  if (confidence === "Medium") return "border-amber-500/25 bg-amber-500/10 text-[var(--foreground)]";
  return "border-[var(--border)] bg-[var(--card-muted)] text-[var(--text-secondary)]";
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

function previewEntries(section: BlueprintSectionResponse) {
  return Object.entries(section.content).slice(0, 5);
}

function reportCount(section?: { created: string[]; updated: string[]; skipped: string[] }) {
  if (!section) return 0;
  return section.created.length + section.updated.length + section.skipped.length;
}

function skippedCount(report: MaterializationReportResponse | null) {
  if (!report) return 0;
  return report.npcs.skipped.length + report.quests.skipped.length + report.memories.skipped.length + report.flags.skipped.length;
}

function sectionRows(report: MaterializationReportResponse) {
  return [
    ["NPCs", report.npcs],
    ["Quests", report.quests],
    ["Memories", report.memories],
    ["Flags", report.flags],
  ] as const;
}

export default function BlueprintsDashboard() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [supportingDocIds, setSupportingDocIds] = useState<string[]>([]);
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
  const [readinessState, setReadinessState] = useState<ReadinessState | null>(null);
  const [materializationReviewOpen, setMaterializationReviewOpen] = useState(false);
  const [compareTargetId, setCompareTargetId] = useState("");
  const [comparison, setComparison] = useState<BlueprintComparisonResponse | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [isExportingBrief, setIsExportingBrief] = useState(false);
  const [sourceReview, setSourceReview] = useState<GddReviewResponse | null>(null);
  const [isReviewingSource, setIsReviewingSource] = useState(false);
  const [decisionCoverageState, setDecisionCoverageState] = useState<DecisionCoverageState | null>(null);
  const [provenanceState, setProvenanceState] = useState<ProvenanceState | null>(null);

  const loadInitialData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [docs, existingBlueprints] = await Promise.all([api.getDocuments(), api.getBlueprints()]);
      setDocuments(docs);
      setBlueprints(existingBlueprints);

      if (docs.length > 0) {
        setSelectedDocId((current) => current || docs[0].id);
      }

      if (existingBlueprints.length > 0) {
        setActiveBlueprint((current) => current || existingBlueprints[0]);
      }
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        console.warn("Blueprint workspace unavailable:", err);
      }
      setError("Could not load blueprints. Start Docker and refresh this page.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    Promise.resolve().then(loadInitialData);
  }, []);

  useEffect(() => {
    const blueprintId = activeBlueprint?.id;
    if (!blueprintId) return;

    let active = true;
    api
      .getBlueprintReadiness(blueprintId)
      .then((result) => {
        if (active) setReadinessState({ blueprintId, value: result });
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, [activeBlueprint?.id]);

  useEffect(() => {
    const documentId = activeBlueprint?.document_id;
    if (!documentId) return;
    let active = true;
    api.getDecisionCoverage(documentId)
      .then((result) => {
        if (active) setDecisionCoverageState({ documentId, value: result });
      })
      .catch(() => {
        if (active) setDecisionCoverageState(null);
      });
    return () => {
      active = false;
    };
  }, [activeBlueprint?.document_id]);

  useEffect(() => {
    const blueprintId = activeBlueprint?.id;
    if (!blueprintId) return;
    let active = true;
    api.getBlueprintProvenance(blueprintId)
      .then((result) => {
        if (active) setProvenanceState({ blueprintId, value: result });
      })
      .catch(() => {
        if (active) setProvenanceState(null);
      });
    return () => {
      active = false;
    };
  }, [activeBlueprint?.id]);

  const reviewSections: ReviewSection[] = useMemo(() => {
    if (!activeBlueprint) return [];

    return [
      {
        id: "summary",
        title: "Game summary",
        description: "Premise, genre, world setup, and player role.",
        section: activeBlueprint.summary,
      },
      {
        id: "narrative",
        title: "Narrative",
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
        title: "NPCs",
        description: "Characters, roles, personalities, and dialogue setup.",
        section: activeBlueprint.npc_archetypes,
      },
      {
        id: "memory",
        title: "Memory",
        description: "Facts and events NPCs should remember.",
        section: activeBlueprint.npc_memory_design,
      },
      {
        id: "levels",
        title: "Levels",
        description: "Spaces, gates, activities, and progression ideas.",
        section: activeBlueprint.level_design_suggestions,
      },
      ...(activeBlueprint.gameplay_systems ? [{
        id: "systems",
        title: "Gameplay systems",
        description: "Gameplay loop, progression, economy, controls, accessibility, and technical constraints.",
        section: activeBlueprint.gameplay_systems,
      }] : []),
      {
        id: "quests",
        title: "Quests",
        description: "Objectives, rewards, and playable mission seeds.",
        section: activeBlueprint.quest_hooks,
      },
      {
        id: "unity",
        title: "Runtime",
        description: "Engine-facing shape prepared for API clients.",
        section: activeBlueprint.unity_runtime_preview,
      },
    ];
  }, [activeBlueprint]);

  const activeSection = reviewSections.find((section) => section.id === activeSectionId) || reviewSections[0];
  const selectedDocument = documents.find((doc) => doc.id === selectedDocId);
  const supportingDocuments = documents.filter((doc) => doc.id !== selectedDocId);
  const blueprintIsApproved = activeBlueprint?.status === "approved";
  const blueprintIsMaterialized = Boolean(activeBlueprint?.materialization_manifest);
  const readiness = readinessState && readinessState.blueprintId === activeBlueprint?.id ? readinessState.value : null;
  const decisionCoverage = decisionCoverageState && decisionCoverageState.documentId === activeBlueprint?.document_id
    ? decisionCoverageState.value
    : null;
  const provenance = provenanceState && provenanceState.blueprintId === activeBlueprint?.id ? provenanceState.value : null;
  const payload = runtimeBundle || exportData;
  const skippedRuntimeItems = skippedCount(materializeReport);

  const steps: StepItem[] = [
    {
      label: "Source",
      detail: selectedDocument?.title || "Choose a document",
      complete: Boolean(selectedDocId),
      active: !activeBlueprint,
    },
    {
      label: "Generate",
      detail: activeBlueprint ? "Blueprint exists" : "Create draft",
      complete: Boolean(activeBlueprint),
      active: Boolean(selectedDocId && !activeBlueprint),
    },
    {
      label: "Review",
      detail: activeBlueprint ? statusLabel(activeBlueprint) : "Waiting",
      complete: Boolean(activeBlueprint && activeBlueprint.status !== "draft"),
      active: Boolean(activeBlueprint && activeBlueprint.status === "draft"),
    },
    {
      label: "Runtime",
      detail: blueprintIsMaterialized ? "Ready" : "Not materialized",
      complete: blueprintIsMaterialized,
      active: Boolean(activeBlueprint && blueprintIsApproved && !blueprintIsMaterialized),
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
      const newBlueprint = await api.generateBlueprint(selectedDocId, supportingDocIds);
      const existingBlueprints = await api.getBlueprints();
      setBlueprints(existingBlueprints);
      setActiveBlueprint(newBlueprint);
      setActiveSectionId("summary");
      setCompareTargetId("");
      setComparison(null);
      setSuccess("Blueprint generated. Review the sections before approval.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Blueprint generation failed.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleReviewSource = async () => {
    if (!selectedDocId) return;

    setIsReviewingSource(true);
    setError(null);
    setSuccess(null);
    try {
      setSourceReview(await api.reviewDocument(selectedDocId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not review this source document.");
    } finally {
      setIsReviewingSource(false);
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
      setSuccess("Blueprint approved. It can now become runtime data.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve blueprint.");
    } finally {
      setIsApproving(false);
    }
  };

  const handleMaterialize = async (confirmIncomplete: boolean = false) => {
    if (!activeBlueprint) return;
    if (!confirmIncomplete && readiness && !readiness.can_materialize) {
      setMaterializationReviewOpen(true);
      return;
    }

    setIsMaterializing(true);
    setError(null);
    setSuccess(null);
    setMaterializeReport(null);

    try {
      const report = await api.materializeBlueprint(activeBlueprint.id, confirmIncomplete);
      const existingBlueprints = await api.getBlueprints();
      const updated = existingBlueprints.find((item) => item.id === activeBlueprint.id) || activeBlueprint;
      setMaterializeReport(report);
      setBlueprints(existingBlueprints);
      setActiveBlueprint(updated);
      setMaterializationReviewOpen(false);
      setSuccess("Runtime data materialized. The simulator or a game client can fetch it.");
    } catch (err) {
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
      setSuccess("Blueprint export generated.");
    } catch {
      setError("Could not create the export.");
    }
  };

  const handleExportBrief = async () => {
    if (!activeBlueprint) return;
    setIsExportingBrief(true);
    setError(null);
    setSuccess(null);
    try {
      const brief = await api.getBlueprintBrief(activeBlueprint.id);
      const url = URL.createObjectURL(new Blob([brief.markdown], { type: "text/markdown;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = brief.filename;
      link.click();
      URL.revokeObjectURL(url);
      setSuccess("Project brief exported as Markdown.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not export the project brief.");
    } finally {
      setIsExportingBrief(false);
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
      setSuccess("Runtime bundle loaded.");
    } catch {
      setError("Could not fetch runtime bundle.");
    }
  };

  const handleCopyPayload = async () => {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setSuccess("Payload copied to clipboard.");
  };

  const handleCompare = async () => {
    if (!activeBlueprint || !compareTargetId) return;
    setIsComparing(true);
    setError(null);
    try {
      setComparison(await api.compareBlueprints(compareTargetId, activeBlueprint.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not compare blueprints.");
    } finally {
      setIsComparing(false);
    }
  };

  const comparableBlueprints = blueprints.filter((blueprint) => blueprint.id !== activeBlueprint?.id);

  return (
    <main className="page-shell">
      <section className="flex flex-col gap-6 py-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="page-kicker">Blueprint studio</p>
          <h1 className="display-title mt-4 text-[2.15rem] leading-tight sm:text-[3rem]">
            Convert one game document into a usable build plan.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Generate a grounded blueprint, review each section, approve it, then materialize only the data your runtime
            should consume.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link href="/knowledge" className="btn-secondary">
            Add source
          </Link>
          {activeBlueprint && activeBlueprint.status === "draft" && (
            <button type="button" onClick={handleApprove} disabled={isApproving} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
              {isApproving ? "Approving" : "Approve"}
            </button>
          )}
          {activeBlueprint && blueprintIsApproved && !blueprintIsMaterialized && (
            <button type="button" onClick={() => handleMaterialize()} disabled={isMaterializing || !readiness} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
              {isMaterializing ? "Materializing" : !readiness ? "Checking runtime" : readiness.can_materialize ? "Materialize" : "Review runtime"}
            </button>
          )}
        </div>
      </section>

      <section className="mt-6 grid gap-3 md:grid-cols-4" aria-label="Blueprint progress">
        {steps.map((step, index) => (
          <div
            key={step.label}
            className={`rounded-2xl border p-4 ${
              step.active
                ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                : step.complete
                  ? "border-emerald-500/20 bg-emerald-500/10"
                  : "border-[var(--border)] bg-[var(--card)]"
            }`}
          >
            <p className="page-kicker">{String(index + 1).padStart(2, "0")}</p>
            <h2 className="mt-3 text-base font-semibold text-[var(--foreground)]">{step.label}</h2>
            <p className="mt-1 truncate text-sm text-[var(--text-secondary)]">{step.detail}</p>
          </div>
        ))}
      </section>

      {(error || success) && (
        <section
          className={`mt-6 rounded-2xl border px-4 py-3 text-sm ${
            error
              ? "border-amber-500/30 bg-amber-500/10 text-[var(--foreground)]"
              : "border-emerald-500/25 bg-emerald-500/10 text-[var(--foreground)]"
          }`}
          role={error ? "alert" : "status"}
        >
          {error || success}
        </section>
      )}

      <section className="mt-8 grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <section className="panel rounded-3xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="page-kicker">Source</p>
                <h2 className="mt-3 text-xl font-semibold text-[var(--foreground)]">Choose source truth</h2>
              </div>
              <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">$0 local</span>
            </div>

            <div className="mt-5">
              {documents.length === 0 ? (
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--card-muted)] p-4">
                  <p className="text-sm font-semibold text-[var(--foreground)]">No documents yet</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">Upload a GDD before generating a blueprint.</p>
                  <Link href="/knowledge" className="btn-primary mt-4 w-full">
                    Upload source
                  </Link>
                </div>
              ) : (
                <div className="space-y-4">
                  <label className="block text-sm font-semibold text-[var(--foreground)]" htmlFor="source-document">
                    Source document
                  </label>
                  <select
                    id="source-document"
                    value={selectedDocId}
                    onChange={(event) => {
                      setSelectedDocId(event.target.value);
                      setSupportingDocIds((current) => current.filter((id) => id !== event.target.value));
                      setSourceReview(null);
                    }}
                    className="min-h-11 w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
                  >
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.title} · revision {doc.revision_number}
                      </option>
                    ))}
                  </select>

                  <div className="rounded-2xl border border-[var(--border)] bg-[var(--card-muted)] p-4">
                    <p className="break-words text-sm font-semibold text-[var(--foreground)]">{selectedDocument?.title || "Selected document"}</p>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">{selectedDocument?.chunks_count || 0} searchable chunks</p>
                    {selectedDocument && (
                      <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
                        {sourceKindMeta[asSourceKind(selectedDocument.source_kind)].label} · improves {sourceKindMeta[asSourceKind(selectedDocument.source_kind)].impact.join(", ")}
                      </p>
                    )}
                  </div>

                  {supportingDocuments.length > 0 && (
                    <details className="border-y border-[var(--border)] py-4">
                      <summary className="cursor-pointer text-sm font-semibold text-[var(--foreground)] marker:text-[var(--accent)]">
                        Supporting sources {supportingDocIds.length > 0 ? `(${supportingDocIds.length})` : ""}
                      </summary>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">Add only documents that should contribute evidence to this blueprint.</p>
                      <div className="mt-4 space-y-3">
                        {supportingDocuments.map((document) => {
                          const checked = supportingDocIds.includes(document.id);
                          const kind = sourceKindMeta[asSourceKind(document.source_kind)];
                          return (
                            <label key={document.id} className="flex cursor-pointer items-start gap-3 text-sm text-[var(--foreground)]">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => setSupportingDocIds((current) => checked ? current.filter((id) => id !== document.id) : [...current, document.id])}
                                className="mt-1 h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent)] focus:ring-[var(--accent)]"
                              />
                              <span className="min-w-0">
                                <span className="block truncate font-medium">{document.title}</span>
                                <span className="mt-1 block text-xs text-[var(--text-secondary)]">{kind.label} · {kind.impact.join(", ")}</span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </details>
                  )}

                  <button type="button" onClick={handleGenerate} disabled={isGenerating || !selectedDocId} className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-50">
                    {isGenerating ? "Generating" : supportingDocIds.length > 0 ? `Generate from ${supportingDocIds.length + 1} sources` : "Generate blueprint"}
                  </button>
                  <button type="button" onClick={handleReviewSource} disabled={isReviewingSource || !selectedDocId} className="btn-secondary w-full disabled:cursor-not-allowed disabled:opacity-50">
                    {isReviewingSource ? "Reviewing source" : "Review source"}
                  </button>
                </div>
              )}
            </div>
          </section>

          {sourceReview && (
            <section className="border-y border-[var(--border)] py-5" aria-live="polite">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="page-kicker">Design review</p>
                  <h2 className="mt-2 text-lg font-semibold text-[var(--foreground)]">Source decision coverage</h2>
                </div>
                <span className="text-sm font-semibold text-[var(--text-secondary)]">
                  {sourceReview.summary.needs_decision} open
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                {sourceReview.summary.conflicts > 0
                  ? `${sourceReview.summary.conflicts} scope conflict needs a decision before generation.`
                  : "Only missing decisions and explicit conflicts are shown. Covered areas remain quiet."}
              </p>
              <ul className="mt-4 space-y-3">
                {sourceReview.findings.filter((finding) => finding.severity !== "covered").map((finding) => (
                  <li key={finding.title} className={`border-l-2 pl-3 ${finding.severity === "conflict" ? "border-amber-500" : "border-[var(--accent)]"}`}>
                    <p className="text-sm font-semibold text-[var(--foreground)]">{finding.title}</p>
                    <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{finding.guidance || finding.message}</p>
                  </li>
                ))}
              </ul>
              {sourceReview.summary.needs_decision === 0 && sourceReview.summary.conflicts === 0 && (
                <p className="mt-4 text-sm font-medium text-[var(--foreground)]">The source covers the first-pass decisions GameMind checks.</p>
              )}
              {(sourceReview.summary.needs_decision > 0 || sourceReview.summary.conflicts > 0) && (
                <Link href="/decisions" className="btn-secondary mt-5">Open decision workspace</Link>
              )}
            </section>
          )}

          <section className="panel overflow-hidden rounded-3xl">
            <div className="border-b border-[var(--border)] p-5">
              <p className="page-kicker">Saved</p>
              <h2 className="mt-3 text-xl font-semibold text-[var(--foreground)]">Blueprints</h2>
            </div>

            {isLoading ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-16 animate-pulse rounded-2xl bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : blueprints.length === 0 ? (
              <div className="p-5 text-sm leading-6 text-[var(--text-secondary)]">No generated blueprints yet.</div>
            ) : (
              <div className="max-h-[24rem] overflow-y-auto p-2">
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
                        setCompareTargetId("");
                        setComparison(null);
                      }}
                      className={`mb-2 block w-full rounded-2xl px-4 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
                        selected ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--card-muted)]"
                      }`}
                    >
                      <p className="truncate text-sm font-semibold text-[var(--foreground)]">{blueprint.title}</p>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <span className="text-xs text-[var(--text-secondary)]">{formatDate(blueprint.created_at)}</span>
                        <span className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
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

        <section className="min-w-0">
          {!activeBlueprint ? (
            <div className="panel rounded-3xl px-6 py-20 text-center">
              <p className="page-kicker">Empty state</p>
              <h2 className="display-title mx-auto mt-4 max-w-lg text-3xl leading-tight">Generate your first blueprint from a source document.</h2>
              <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                A blueprint is a structured game plan: summary, narrative, art direction, NPCs, memory, levels, quests, and runtime shape.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <section className="panel overflow-hidden rounded-3xl">
                <div className="border-b border-[var(--border)] p-6">
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <p className="page-kicker">Review</p>
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <h2 className="max-w-3xl truncate text-2xl font-semibold tracking-normal text-[var(--foreground)] sm:text-3xl">
                          {activeBlueprint.title}
                        </h2>
                        <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold text-[var(--foreground)]">
                          {statusLabel(activeBlueprint)}
                        </span>
                        {activeBlueprint.source_document_ids.length > 1 && (
                          <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]">
                            {activeBlueprint.source_document_ids.length} sources
                          </span>
                        )}
                        {!blueprintIsMaterialized && (
                          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                            readiness?.status === "runtime_ready"
                              ? "border-emerald-500/25 bg-emerald-500/10 text-[var(--foreground)]"
                              : readiness?.status === "planning_only"
                                ? "border-amber-500/25 bg-amber-500/10 text-[var(--foreground)]"
                                : "border-[var(--border)] bg-[var(--card-muted)] text-[var(--text-secondary)]"
                          }`}>
                            {readinessLabel(readiness)}
                          </span>
                        )}
                        {decisionCoverage && decisionCoverage.items.length > 0 && (
                          <Link href="/decisions" className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)]">
                            Decisions: {decisionCoverage.summary.source_backed} backed · {decisionCoverage.summary.needs_source_evidence + decisionCoverage.summary.decision_open} open
                          </Link>
                        )}
                      </div>
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                        Review section by section. Approval is the point where draft design becomes runtime intent.
                      </p>
                      {comparableBlueprints.length > 0 && (
                        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
                          <label className="min-w-0 flex-1 text-sm font-semibold text-[var(--foreground)]" htmlFor="compare-blueprint">
                            Compare with earlier blueprint
                            <select
                              id="compare-blueprint"
                              value={compareTargetId}
                              onChange={(event) => {
                                setCompareTargetId(event.target.value);
                                setComparison(null);
                              }}
                              className="mt-2 h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm font-normal text-[var(--foreground)] outline-none focus:ring-2 focus:ring-[var(--accent)]"
                            >
                              <option value="">Choose a snapshot</option>
                              {comparableBlueprints.map((blueprint) => (
                                <option key={blueprint.id} value={blueprint.id}>
                                  {blueprint.title} · {formatDate(blueprint.created_at)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <button type="button" onClick={handleCompare} disabled={!compareTargetId || isComparing} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                            {isComparing ? "Comparing" : "Compare changes"}
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button type="button" onClick={handleExportBrief} disabled={isExportingBrief} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                        {isExportingBrief ? "Exporting brief" : "Export brief"}
                      </button>
                      <button type="button" onClick={handleExport} className="btn-secondary">
                        Export JSON
                      </button>
                      {blueprintIsMaterialized && (
                        <button type="button" onClick={handleRuntimeBundle} className="btn-secondary">
                          Runtime bundle
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid min-h-[34rem] lg:grid-cols-[220px_minmax(0,1fr)]">
                  <nav className="border-b border-[var(--border)] bg-[var(--card-muted)] p-3 lg:border-b-0 lg:border-r" aria-label="Blueprint sections">
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                      {reviewSections.map((section) => {
                        const selected = activeSection?.id === section.id;
                        return (
                          <button
                            key={section.id}
                            type="button"
                            onClick={() => setActiveSectionId(section.id)}
                            className={`min-h-12 rounded-xl px-3 text-left text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
                              selected ? "bg-[var(--surface)] text-[var(--foreground)] shadow-sm" : "text-[var(--text-secondary)] hover:bg-[var(--surface)] hover:text-[var(--foreground)]"
                            }`}
                          >
                            {section.title}
                          </button>
                        );
                      })}
                    </div>
                  </nav>

                  {activeSection && <SectionBrief section={activeSection} citations={provenance?.sections.find((item) => item.section === activeSection.id)?.citations || []} />}
                </div>
              </section>

              {comparison && (
                <section className="border border-[var(--border)] bg-[var(--card-muted)] px-5 py-4">
                  <p className="page-kicker">Revision comparison</p>
                  {comparison.changed_sections.length === 0 ? (
                    <p className="mt-3 text-sm text-[var(--text-secondary)]">No extracted blueprint sections changed between these snapshots.</p>
                  ) : (
                    <ul className="mt-3 flex flex-wrap gap-2" aria-label="Changed blueprint sections">
                      {comparison.changed_sections.map((section) => (
                        <li key={section.section} className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground)]">
                          {section.section} · warnings {section.before_warnings} to {section.after_warnings}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )}

              {materializeReport && (
                <section className="panel rounded-3xl p-6">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="page-kicker">Runtime result</p>
                      <h2 className="mt-3 text-2xl font-semibold text-[var(--foreground)]">Materialization complete</h2>
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                        GameMind created or updated runtime records and skipped anything unsafe or duplicate.
                      </p>
                    </div>
                    <Link href="/vertical-slice" className="btn-primary shrink-0">
                      Open Runtime Test
                    </Link>
                  </div>

                  <div className="mt-5 grid gap-3 sm:grid-cols-4">
                    {sectionRows(materializeReport).map(([label, report]) => (
                      <div key={label} className="rounded-2xl border border-[var(--border)] bg-[var(--card-muted)] p-4">
                        <p className="page-kicker">{label}</p>
                        <p className="mt-3 text-2xl font-semibold text-[var(--foreground)]">{reportCount(report)}</p>
                        <p className="mt-2 text-xs text-[var(--text-secondary)]">
                          {report.created.length} created, {report.updated.length} updated, {report.skipped.length} skipped
                        </p>
                      </div>
                    ))}
                  </div>

                  {(materializeReport.warnings.length > 0 || skippedRuntimeItems > 0) && (
                    <div className="mt-5 rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4">
                      <p className="text-sm font-semibold text-[var(--foreground)]">Review skipped items</p>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Skipped records usually mean duplicates or missing source detail. Review them before using this in a real scene.
                      </p>
                    </div>
                  )}
                </section>
              )}

              {payload && (
                <section className="panel overflow-hidden rounded-3xl">
                  <div className="flex flex-col gap-4 border-b border-[var(--border)] p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="page-kicker">{runtimeBundle ? "Runtime bundle" : "Export"}</p>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--foreground)]">Structured payload</h2>
                    </div>
                    <button type="button" onClick={handleCopyPayload} className="btn-secondary">
                      Copy data
                    </button>
                  </div>
                  <pre className="max-h-96 overflow-auto p-5 text-xs leading-5 text-[var(--text-secondary)]">
                    {JSON.stringify(payload, null, 2)}
                  </pre>
                </section>
              )}
            </div>
          )}
        </section>
      </section>

      {materializationReviewOpen && readiness && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm" role="presentation">
          <button
            type="button"
            aria-label="Close runtime review"
            onClick={() => !isMaterializing && setMaterializationReviewOpen(false)}
            className="absolute inset-0"
          />
          <section role="dialog" aria-modal="true" aria-labelledby="runtime-review-title" className="relative w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
            <p className="page-kicker">Runtime review</p>
            <h2 id="runtime-review-title" className="mt-3 text-2xl font-semibold text-[var(--foreground)]">
              This blueprint is incomplete for runtime.
            </h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              GameMind found useful planning material, but the source does not yet support every runtime record.
            </p>
            <ul className="mt-5 space-y-2 text-sm text-[var(--foreground)]">
              {readiness.missing_required.map((item) => <li key={item}>Missing: {item}</li>)}
              {readiness.advisories.map((item) => <li key={item} className="text-[var(--text-secondary)]">Review: {item}</li>)}
            </ul>
            <p className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">
              Improve the source and regenerate for a complete bundle, or continue knowing that the runtime output may be partial.
            </p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => setMaterializationReviewOpen(false)} disabled={isMaterializing} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50">
                Return to review
              </button>
              <button type="button" onClick={() => handleMaterialize(true)} disabled={isMaterializing} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                {isMaterializing ? "Materializing" : "Materialize anyway"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function SectionBrief({
  section,
  citations,
}: {
  section: ReviewSection;
  citations: BlueprintProvenanceResponse["sections"][number]["citations"];
}) {
  const guidance = sectionGuidance[section.id];
  const entries = previewEntries(section.section);
  const hasWarnings = section.section.warnings.length > 0;

  return (
    <article className="min-w-0 p-5 sm:p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="page-kicker">Section brief</p>
          <h3 className="mt-3 text-2xl font-semibold tracking-normal text-[var(--foreground)]">{section.title}</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{section.description}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${confidenceTone(section.section.confidence)}`}>
            {section.section.confidence} confidence
          </span>
          <span className="rounded-full border border-[var(--border)] bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            {section.section.citations.length} citations
          </span>
        </div>
      </div>

      <div className="mt-6 grid gap-5">
        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="border-b border-[var(--border)] px-5 py-4">
            <p className="page-kicker">What GameMind found</p>
          </div>

          {entries.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm font-semibold text-[var(--foreground)]">No usable section data yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                Add more detail to the source document, then regenerate.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {entries.map(([key, value]) => (
                <div key={key} className="p-5">
                  <p className="page-kicker">{key.replaceAll("_", " ")}</p>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--foreground)]">{readableValue(value)}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="grid gap-4 lg:grid-cols-3">
          <InfoPanel title="How to use this" body={guidance?.use ?? "Review this as a design decision before runtime use."} />
          <InfoPanel title="Runtime impact" body={guidance?.runtime ?? "This section contributes to runtime data and exports."} />
          <section
            className={`rounded-2xl border p-5 ${
              hasWarnings ? "border-amber-500/25 bg-amber-500/10" : "border-emerald-500/20 bg-emerald-500/10"
            }`}
          >
            <p className="text-sm font-semibold text-[var(--foreground)]">{hasWarnings ? "Needs source detail" : "No blocking gaps"}</p>
            {hasWarnings ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
                {section.section.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">This section has enough detail for the MVP workflow.</p>
            )}
          </section>
        </aside>
      </div>

      <details className="mt-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--accent)] outline-none transition hover:text-[var(--accent-hover)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
          Structured data
        </summary>
        <pre className="max-h-80 overflow-auto border-t border-[var(--border)] p-4 text-xs leading-5 text-[var(--text-secondary)]">
          {JSON.stringify(section.section.content, null, 2)}
        </pre>
      </details>

      {citations.length > 0 && (
        <details className="mt-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--accent)] outline-none transition hover:text-[var(--accent-hover)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
            Evidence sources ({citations.length})
          </summary>
          <ul className="divide-y divide-[var(--border)] border-t border-[var(--border)]">
            {citations.map((citation) => (
              <li key={citation.chunk_id} className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                <Link
                  href={`/knowledge?document=${citation.document_id}&chunk=${citation.chunk_id}`}
                  className="font-medium text-[var(--foreground)] underline-offset-4 transition hover:text-[var(--accent)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                >
                  {citation.document_title}
                </Link>
                <span className="text-[var(--text-secondary)]">Revision {citation.revision_number} · Chunk {citation.chunk_index + 1}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function InfoPanel({ title, body }: { title: string; body: string }) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
      <p className="page-kicker">{title}</p>
      <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{body}</p>
    </section>
  );
}
