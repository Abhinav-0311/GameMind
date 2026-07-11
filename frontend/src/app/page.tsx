"use client";

import React, { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { api, BlueprintResponse, DocumentResponse, HealthResponse } from "@/lib/api";

interface NextAction {
  label: string;
  description: string;
  href: string;
  action: string;
}

interface WalkthroughStep {
  eyebrow: string;
  title: string;
  body: string;
  href: string;
  action: string;
  complete: boolean;
  current: boolean;
}

export default function WorkspaceOverview() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [blueprints, setBlueprints] = useState<BlueprintResponse[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchWorkspace = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [docs, healthData, blueprintData] = await Promise.all([
          api.getDocuments(),
          api.getHealth(),
          api.getBlueprints(),
        ]);

        if (!cancelled) {
          setDocuments(docs);
          setHealth(healthData);
          setBlueprints(blueprintData);
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to load workspace overview:", err);
          setError("The workspace could not load. Start Docker and refresh this page.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchWorkspace();

    return () => {
      cancelled = true;
    };
  }, []);

  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + (doc.chunks_count || 0), 0),
    [documents]
  );

  const hasDocuments = documents.length > 0;
  const hasBlueprints = blueprints.length > 0;
  const runtimeReadyCount = blueprints.filter((blueprint) => blueprint.materialization_manifest).length;
  const hasRuntimeData = runtimeReadyCount > 0;
  const isLocalMode = health?.ai_mode === "local_demo";
  const currentStepIndex = !hasDocuments ? 0 : !hasBlueprints ? 1 : !hasRuntimeData ? 2 : 3;

  const nextAction: NextAction = useMemo(() => {
    if (!hasDocuments) {
      return {
        label: "Start with the source document",
        description: "Upload a GDD, lore file, quest sheet, or character brief. Everything else depends on this.",
        href: "/knowledge",
        action: "Upload document",
      };
    }

    if (!hasBlueprints) {
      return {
        label: "Generate the first game blueprint",
        description: "Convert the selected document into narrative, NPC, quest, level, memory, and runtime guidance.",
        href: "/blueprints",
        action: "Generate blueprint",
      };
    }

    if (!hasRuntimeData) {
      return {
        label: "Approve and materialize runtime data",
        description: "Write the approved blueprint into NPC, quest, memory, and world-state records for Unity.",
        href: "/blueprints",
        action: "Materialize blueprint",
      };
    }

    return {
      label: "Test the playable vertical slice",
      description: "Open the simulator or Unity scene and verify dialogue, quests, memory, and hints together.",
      href: "/vertical-slice",
      action: "Test runtime",
    };
  }, [hasBlueprints, hasDocuments, hasRuntimeData]);

  const readiness = [
    {
      label: "Backend",
      value: health?.status ?? "checking",
      good: health?.status === "healthy",
    },
    {
      label: "Database",
      value: health?.database ?? "checking",
      good: health?.database === "healthy",
    },
    {
      label: "Vector index",
      value: health?.chromadb ?? "checking",
      good: health?.chromadb === "healthy",
    },
    {
      label: "AI mode",
      value: isLocalMode ? "local demo" : health?.ai_mode ?? "checking",
      good: isLocalMode,
    },
  ];

  const walkthrough: WalkthroughStep[] = [
    {
      eyebrow: "01 / Sources",
      title: "Start with the game document",
      body: "Upload the GDD, lore brief, quest notes, NPC sheet, or the Frostpeak sample. GameMind chunks it into searchable source evidence.",
      href: "/knowledge",
      action: "Open Sources",
      complete: hasDocuments,
      current: currentStepIndex === 0,
    },
    {
      eyebrow: "02 / Blueprint",
      title: "Turn the source into a build plan",
      body: "Generate a structured blueprint for narrative direction, NPCs, memory, quests, level ideas, and Unity runtime data.",
      href: "/blueprints",
      action: "Open Blueprints",
      complete: hasBlueprints,
      current: currentStepIndex === 1,
    },
    {
      eyebrow: "03 / Grounding",
      title: "Inspect what the system knows",
      body: "Ask direct lore questions and check citations before trusting generated outputs. This keeps the assistant honest.",
      href: "/query",
      action: "Search Lore",
      complete: hasRuntimeData,
      current: currentStepIndex === 2,
    },
    {
      eyebrow: "04 / Runtime",
      title: "Playtest the loop",
      body: "Run dialogue, quest generation, quest acceptance, and progressive hints in one guided simulator before opening Unity.",
      href: "/vertical-slice",
      action: "Open Runtime Test",
      complete: hasRuntimeData,
      current: currentStepIndex === 3,
    },
  ];

  return (
    <main className="page-shell">
      <section className="grid items-center gap-8 py-4 lg:grid-cols-[minmax(0,1fr)_420px] lg:py-8">
        <div className="max-w-3xl">
          <p className="page-kicker">Guided AI game builder</p>
          <h1 className="display-title mt-5 max-w-3xl text-[2.15rem] leading-[1.08] sm:text-[3rem] sm:leading-[1.05]">
            Turn a rough GDD into a playable game plan.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            GameMind helps student and indie developers upload source docs, generate a structured blueprint,
            verify lore with citations, and test dialogue or quests before opening Unity.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href={nextAction.href}
              className="btn-primary"
            >
              {nextAction.action}
            </Link>
            <Link
              href="#build-loop"
              className="btn-secondary"
            >
              See full walkthrough
            </Link>
          </div>
        </div>

        <div className="panel overflow-hidden rounded-3xl">
          <div className="border-b border-[var(--border)] p-3">
            <Image
              src="/brand/game-builder-workbench.svg"
              alt="Visual map showing a source GDD becoming a blueprint and runtime game systems"
              width={960}
              height={720}
              priority
              className="h-auto w-full rounded-2xl"
            />
          </div>
          <div className="p-5">
            <p className="page-kicker">Current step</p>
            <h2 className="mt-3 text-xl font-semibold tracking-normal text-[var(--foreground)]">
              {nextAction.label}
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{nextAction.description}</p>
            <Link href={nextAction.href} className="btn-primary mt-5 w-full">
              {nextAction.action}
            </Link>
          </div>
        </div>
      </section>

      {error && (
        <section className="mb-8 rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-800">
          {error}
        </section>
      )}

      <section id="build-loop" className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="panel overflow-hidden rounded-3xl">
          <div className="border-b border-[var(--border)] p-6">
            <p className="page-kicker">Full site walkthrough</p>
            <h2 className="display-title mt-4 text-3xl leading-tight sm:text-[2.2rem]">
              One build loop, four screens.
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
              The dashboard is intentionally sectioned by decision type: source truth, generation, verification, and
              playtesting.
            </p>
          </div>

          <div className="divide-y divide-[var(--border)]">
            {walkthrough.map((step, index) => (
              <Link
                key={step.eyebrow}
                href={step.href}
                className="group grid gap-4 p-5 transition hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[var(--accent)] sm:grid-cols-[7rem_1fr_auto]"
              >
                <div className="flex items-center gap-3 sm:block">
                  <span
                    className={`inline-flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold ${
                      step.complete
                        ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-700"
                        : step.current
                          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                          : "border-[var(--border)] bg-[var(--surface)] text-[var(--text-tertiary)]"
                    }`}
                  >
                    {step.complete ? "✓" : String(index + 1).padStart(2, "0")}
                  </span>
                  <p className="mono-label mt-0 text-[var(--text-tertiary)] sm:mt-3">{step.eyebrow.split(" / ")[1]}</p>
                </div>
                <div>
                  <h3 className="text-lg font-semibold tracking-normal text-[var(--foreground)]">{step.title}</h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{step.body}</p>
                </div>
                <div className="flex items-center">
                  <span className="text-sm font-semibold text-[var(--foreground)] transition group-hover:text-[var(--accent)]">
                    {step.current ? "Continue" : step.action}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>

        <aside className="space-y-5">
          <section className="panel rounded-3xl p-5">
            <h2 className="font-display text-[1.45rem] font-semibold tracking-normal text-[var(--foreground)]">Project snapshot</h2>
            <div className="mt-5 divide-y divide-[var(--border)]">
              <FactRow label="Documents" value={isLoading ? "--" : String(documents.length)} />
              <FactRow label="Chunks" value={isLoading ? "--" : String(totalChunks)} />
              <FactRow label="Blueprints" value={isLoading ? "--" : String(blueprints.length)} />
              <FactRow label="Runtime ready" value={isLoading ? "--" : String(runtimeReadyCount)} />
              <FactRow label="Paid API cost" value="$0" />
            </div>
          </section>

          <section className="panel-muted rounded-3xl p-5" aria-label="Workspace readiness">
            <h2 className="text-sm font-semibold text-[var(--foreground)]">System status</h2>
            <div className="mt-4 space-y-3">
              {readiness.map((item) => (
                <div key={item.label} className="flex items-center justify-between gap-4">
                  <span className="flex items-center gap-2">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        isLoading ? "bg-[var(--text-secondary)]" : item.good ? "bg-emerald-600" : "bg-amber-500"
                      }`}
                    />
                    <span className="text-sm text-[var(--text-secondary)]">{item.label}</span>
                  </span>
                  <span className="text-sm font-semibold capitalize text-[var(--foreground)]">
                    {isLoading ? "checking" : item.value}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--foreground)]">{value}</span>
    </div>
  );
}
