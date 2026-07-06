"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, BlueprintResponse, DocumentResponse, HealthResponse } from "@/lib/api";

type FlowState = "complete" | "current" | "waiting";

interface FlowStep {
  label: string;
  description: string;
  href: string;
  action: string;
  state: FlowState;
}

interface NextAction {
  label: string;
  description: string;
  href: string;
  action: string;
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

  const latestDocuments = useMemo(
    () =>
      [...documents]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 4),
    [documents]
  );

  const hasDocuments = documents.length > 0;
  const hasBlueprints = blueprints.length > 0;
  const runtimeReadyCount = blueprints.filter((blueprint) => blueprint.materialization_manifest).length;
  const hasRuntimeData = runtimeReadyCount > 0;
  const isHealthy = health?.status === "healthy";
  const isLocalMode = health?.ai_mode === "local_demo";

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

  const flowSteps: FlowStep[] = [
    {
      label: "Upload source",
      description: "Bring in the GDD or lore document that defines the world.",
      href: "/knowledge",
      action: hasDocuments ? "Review sources" : "Upload",
      state: hasDocuments ? "complete" : "current",
    },
    {
      label: "Generate blueprint",
      description: "Extract a structured game plan from the uploaded source.",
      href: "/blueprints",
      action: hasBlueprints ? "Review blueprint" : "Generate",
      state: hasBlueprints ? "complete" : hasDocuments ? "current" : "waiting",
    },
    {
      label: "Materialize runtime",
      description: "Create NPCs, quests, memories, and flags from the approved plan.",
      href: "/blueprints",
      action: hasRuntimeData ? "Runtime ready" : "Materialize",
      state: hasRuntimeData ? "complete" : hasBlueprints ? "current" : "waiting",
    },
    {
      label: "Play test",
      description: "Validate the flow in the web simulator and Unity scene.",
      href: "/vertical-slice",
      action: "Open simulator",
      state: hasRuntimeData ? "current" : "waiting",
    },
  ];

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

  return (
    <main className="page-shell">
      <section className="grid gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-14">
        <div className="max-w-3xl">
          <p className="page-kicker">
            GameMind workspace
          </p>
          <h1 className="display-title mt-5 text-[2.65rem] leading-[1.02] sm:text-6xl sm:leading-[0.98]">
            Build a playable AI narrative slice from one GDD.
          </h1>
          <p className="mt-6 max-w-2xl text-[1.05rem] leading-8 text-[#a5afbd]">
            Upload a design document, generate a grounded blueprint, materialize runtime records, then test the
            result in the dashboard and Unity without paid model calls.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href={nextAction.href}
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#f7f8fa] px-5 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#090b0e]"
            >
              {nextAction.action}
            </Link>
            <Link
              href="/query"
              className="inline-flex min-h-11 items-center justify-center rounded-md border border-[#27303a] px-5 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#3b4654] hover:bg-[#12161b] focus:outline-none focus:ring-2 focus:ring-[#3b4654] focus:ring-offset-2 focus:ring-offset-[#090b0e]"
            >
              Search lore
            </Link>
          </div>
        </div>

        <aside className="panel self-start rounded-xl p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="mono-label text-[#7c8794]">Next action</p>
              <h2 className="mt-3 font-display text-2xl font-semibold text-[#f7f8fa]">{nextAction.label}</h2>
            </div>
            <span
              className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
                isHealthy ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"
              }`}
            >
              {isLoading ? "Checking" : isHealthy ? "Ready" : "Review"}
            </span>
          </div>
          <p className="mt-4 text-sm leading-6 text-[#a5afbd]">{nextAction.description}</p>
          <Link
            href={nextAction.href}
            className="mt-6 inline-flex min-h-10 w-full items-center justify-center rounded-md bg-[#8bdff0] px-4 text-sm font-semibold text-[#061014] transition hover:bg-[#a6edfa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] focus:ring-offset-2 focus:ring-offset-[#101419]"
          >
            Continue
          </Link>
        </aside>
      </section>

      {error && (
        <section className="mb-8 rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </section>
      )}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {readiness.map((item) => (
          <div key={item.label} className="panel-muted rounded-xl p-4">
            <p className="mono-label text-[#7c8794]">{item.label}</p>
            <div className="mt-3 flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  isLoading ? "bg-[#7c8794]" : item.good ? "bg-emerald-300" : "bg-amber-300"
                }`}
              />
              <p className="text-sm font-semibold capitalize text-[#f7f8fa]">
                {isLoading ? "checking" : item.value}
              </p>
            </div>
          </div>
        ))}
      </section>

      <section className="panel mt-8 overflow-hidden rounded-xl">
        <div className="border-b border-[#222a33] px-5 py-5">
          <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">MVP build flow</h2>
          <p className="mt-1 text-sm leading-6 text-[#a5afbd]">
            This is the shortest path from document upload to a demonstrable Unity integration.
          </p>
        </div>

        <div className="grid gap-0 md:grid-cols-4">
          {flowSteps.map((step, index) => (
            <div key={step.label} className="border-b border-[#222a33] p-5 md:border-b-0 md:border-r last:border-r-0">
              <div className="flex items-center justify-between gap-3">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                    step.state === "complete"
                      ? "bg-emerald-500/12 text-emerald-300"
                      : step.state === "current"
                        ? "bg-[#8bdff0] text-[#061014]"
                        : "bg-[#171d24] text-[#7c8794]"
                  }`}
                >
                  {index + 1}
                </span>
                <span
                  className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    step.state === "complete"
                      ? "text-emerald-300"
                      : step.state === "current"
                        ? "text-[#8bdff0]"
                        : "text-[#6f7a87]"
                  }`}
                >
                  {step.state}
                </span>
              </div>
              <h3 className="mt-5 font-display text-xl font-semibold text-[#f7f8fa]">{step.label}</h3>
              <p className="mt-2 min-h-16 text-sm leading-6 text-[#a5afbd]">{step.description}</p>
              <Link
                href={step.href}
                className={`mt-5 inline-flex min-h-9 items-center rounded-md px-3 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#3b4654] focus:ring-offset-2 focus:ring-offset-[#101419] ${
                  step.state === "waiting"
                    ? "border border-[#222a33] text-[#6f7a87]"
                    : "border border-[#303a46] text-[#f7f8fa] hover:border-[#4a5563] hover:bg-[#151b22]"
                }`}
              >
                {step.action}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="panel overflow-hidden rounded-xl">
          <div className="flex items-center justify-between border-b border-[#222a33] px-5 py-4">
            <div>
              <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Source library</h2>
              <p className="mt-1 text-xs text-[#7c8794]">Recent documents available to retrieval and blueprinting.</p>
            </div>
            <Link
              href="/knowledge"
              className="rounded-md px-3 py-2 text-xs font-semibold text-[#a5afbd] transition hover:bg-[#151b22] hover:text-[#f7f8fa] focus:outline-none focus:ring-2 focus:ring-[#3b4654]"
            >
              Manage
            </Link>
          </div>

          {isLoading ? (
            <div className="grid gap-3 p-5 sm:grid-cols-2">
              {[1, 2, 3, 4].map((item) => (
                <div key={item} className="h-24 animate-pulse rounded-md bg-[#151b22]" />
              ))}
            </div>
          ) : latestDocuments.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <h3 className="text-sm font-semibold text-[#f7f8fa]">No source documents yet</h3>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#a5afbd]">
                Upload a GDD or the Frostpeak sample file to start generating grounded outputs.
              </p>
              <Link
                href="/knowledge"
                className="mt-5 inline-flex min-h-10 items-center justify-center rounded-md bg-[#f7f8fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#101419]"
              >
                Upload source
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-[#222a33]">
              {latestDocuments.map((doc) => (
                <div key={doc.id} className="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-[#f7f8fa]">{doc.title}</h3>
                    <p className="mt-1 text-xs text-[#7c8794]">
                      {doc.chunks_count} chunks indexed on {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className="w-fit rounded-full bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-300">
                    Synced
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="panel rounded-xl p-5">
          <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Workspace facts</h2>
          <div className="mt-5 divide-y divide-[#222a33]">
            <FactRow label="Documents" value={isLoading ? "--" : String(documents.length)} />
            <FactRow label="Chunks" value={isLoading ? "--" : String(totalChunks)} />
            <FactRow label="Blueprints" value={isLoading ? "--" : String(blueprints.length)} />
            <FactRow label="Runtime ready" value={isLoading ? "--" : String(runtimeReadyCount)} />
            <FactRow label="LLM cost" value="$0" />
          </div>
          <p className="mt-5 rounded-md border border-[#222a33] bg-[#0b0f13] p-3 text-xs leading-5 text-[#a5afbd]">
            Local mode uses Chroma embeddings and deterministic generation. It is intentionally free, predictable, and
            suitable for demos.
          </p>
        </aside>
      </section>
    </main>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[#a5afbd]">{label}</span>
      <span className="text-sm font-semibold text-[#f7f8fa]">{value}</span>
    </div>
  );
}
