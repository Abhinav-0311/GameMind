"use client";

import React, { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { api, BlueprintReadinessResponse, BlueprintResponse, DocumentResponse, HealthResponse, requestFailureMessage } from "@/lib/api";

interface ProductMode {
  eyebrow: string;
  title: string;
  body: string;
  href: string;
  action: string;
  points: string[];
  recommended?: boolean;
}

interface NextAction {
  label: string;
  description: string;
  href: string;
  action: string;
}

function hasMaterializedRuntimeRecords(blueprint: BlueprintResponse) {
  const manifest = blueprint.materialization_manifest;
  if (!manifest) return false;
  return ["npcs", "quest_ids", "memory_ids", "flag_keys"].some((key) => {
    const value = manifest[key];
    return Array.isArray(value) && value.length > 0;
  });
}

export default function WorkspaceOverview() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [blueprints, setBlueprints] = useState<BlueprintResponse[]>([]);
  const [readinessByBlueprint, setReadinessByBlueprint] = useState<Record<string, BlueprintReadinessResponse>>({});
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState({ documents: false, blueprints: false, readiness: false });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchWorkspace = async () => {
      if (cancelled) return;
      setIsLoading(true);
      setError(null);

      const [docs, healthData, blueprintData] = await Promise.allSettled([
        api.getDocuments(),
        api.getHealth(),
        api.getBlueprints(),
      ]);
      const readinessResults = await Promise.all(
        (blueprintData.status === "fulfilled" ? blueprintData.value : [])
          .filter(hasMaterializedRuntimeRecords)
          .map(async (blueprint) => {
            try {
              return [blueprint.id, await api.getBlueprintReadiness(blueprint.id)] as const;
            } catch {
              return null;
            }
          })
      );
      const nextReadiness = Object.fromEntries(
        readinessResults.filter((result): result is readonly [string, BlueprintReadinessResponse] => result !== null)
      );

      if (!cancelled) {
        setDocuments(docs.status === "fulfilled" ? docs.value : []);
        setHealth(healthData.status === "fulfilled" ? healthData.value : null);
        setBlueprints(blueprintData.status === "fulfilled" ? blueprintData.value : []);
        setReadinessByBlueprint(nextReadiness);
        const readinessAvailable = blueprintData.status === "fulfilled" && readinessResults.every((result) => result !== null);
        setAvailable({ documents: docs.status === "fulfilled", blueprints: blueprintData.status === "fulfilled", readiness: readinessAvailable });
        const failure = [docs, healthData, blueprintData].find((result) => result.status === "rejected");
        setError(failure?.status === "rejected"
          ? requestFailureMessage(failure.reason, "Some workspace data")
          : !readinessAvailable ? "Runtime readiness unavailable. Retry before choosing a runtime action." : null);
        setIsLoading(false);
      }
    };

    void Promise.resolve().then(fetchWorkspace);

    return () => {
      cancelled = true;
    };
  }, [retry]);

  const totalChunks = useMemo(
    () => documents.reduce((sum, doc) => sum + (doc.chunks_count || 0), 0),
    [documents]
  );

  const hasDocuments = documents.length > 0;
  const hasBlueprints = blueprints.length > 0;
  const approvedBlueprints = blueprints.filter((blueprint) => blueprint.status === "approved");
  const runtimeReadyCount = blueprints.filter((blueprint) => readinessByBlueprint[blueprint.id]?.can_serve_runtime).length;
  const hasRuntimeData = runtimeReadyCount > 0;
  const hasBlockedRuntimeRelease = blueprints.some(
    (blueprint) => hasMaterializedRuntimeRecords(blueprint) && readinessByBlueprint[blueprint.id] && !readinessByBlueprint[blueprint.id].can_serve_runtime
  );
  const provider = health?.llm_provider;
  const isLocalMode = provider === "mock";

  const nextAction: NextAction = useMemo(() => {
    if (isLoading || !available.documents || !available.blueprints || !available.readiness) {
      return {
        label: isLoading ? "Checking workspace" : "Workspace status unavailable",
        description: "Load the source library and release status before choosing the next design or runtime step.",
        href: "/workspace",
        action: "Check workspace",
      };
    }
    if (!hasDocuments) {
      return {
        label: "Add your first source document",
        description: "Upload a GDD, lore file, quest sheet, or use the Frostpeak sample. Good output starts with grounded source material.",
        href: "/knowledge",
        action: "Open sources",
      };
    }

    if (!hasBlueprints) {
      return {
        label: "Start a reviewed design run",
        description: "Use your indexed GDD as fixed evidence, then inspect the draft and independent critique before approval.",
        href: "/design-agent",
        action: "Open review",
      };
    }

    if (hasBlockedRuntimeRelease) {
      return {
        label: "Repair the runtime release",
        description: "A materialized blueprint has current quality blockers. Resolve them before using it in a game client.",
        href: "/blueprints",
        action: "Review blockers",
      };
    }

    if (!hasRuntimeData) {
      return {
        label: approvedBlueprints.length > 0 ? "Materialize reviewed runtime data" : "Review a blueprint before runtime",
        description: approvedBlueprints.length > 0
          ? "Materialize only explicit runtime bindings so the simulator or a game client can consume stable records."
          : "Inspect the source evidence and blueprint sections, then approve only the design you are ready to make runtime data.",
        href: "/blueprints",
        action: approvedBlueprints.length > 0 ? "Open materialization" : "Open blueprints",
      };
    }

    return {
      label: "Playtest the runtime loop",
      description: "Verify dialogue, quest acceptance, and progressive hints after the blueprint is materialized.",
      href: "/vertical-slice",
      action: "Open runtime test",
    };
  }, [approvedBlueprints.length, hasBlueprints, hasBlockedRuntimeRelease, hasDocuments, hasRuntimeData, isLoading, available]);

  const productModes: ProductMode[] = [
    {
      eyebrow: "Mode 01",
      title: "Dashboard workspace",
      body: "For students, writers, and indie teams who want to turn rough game documents into a clean, reviewable plan.",
      href: "/blueprints",
      action: "Build a blueprint",
      recommended: true,
      points: ["Upload GDDs and lore", "Search with citations", "Generate structured game sections", "Export JSON or design notes"],
    },
    {
      eyebrow: "Mode 02",
      title: "Runtime integration",
      body: "For developers who want a game client to consume approved NPCs, quests, dialogue, hints, memory, and world state.",
      href: "/vertical-slice",
      action: "Test runtime",
      points: ["Fetch runtime bundles", "Call dialogue and hint APIs", "Map emotions to presentation", "Adapt to Unity, Godot, Unreal, or web"],
    },
  ];

  if (!isLoading && !error && !hasDocuments) {
    return <FirstRunWorkspace />;
  }

  return (
    <main className="page-shell">
      <section className="grid items-start gap-8 py-5 lg:grid-cols-[minmax(0,1fr)_23rem] lg:py-10">
        <div className="max-w-3xl">
          <p className="page-kicker">Local-first AI game builder</p>
          <h1 className="display-title mt-4 max-w-3xl text-[2.35rem] leading-[1.05] sm:text-[3.2rem]">
            Keep every game decision connected to its evidence.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            GameMind helps new game developers convert GDDs, lore, NPC notes, quest ideas, and level concepts into
            grounded blueprints and engine-ready runtime data. Local evidence checks run first; AI review is an explicit, governed choice.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href={nextAction.href} className="btn-primary">
              {nextAction.action}
            </Link>
            <Link href="#product-modes" className="btn-secondary">
              Compare both modes
            </Link>
          </div>
        </div>

        <aside className="status-strip overflow-hidden rounded-2xl" aria-label="Recommended next action">
          <Image
            src="/brand/game-builder-workbench.svg"
            alt="GameMind workflow from source document to blueprint and runtime systems"
            width={960}
            height={720}
            priority
            className="h-auto w-full border-b border-[var(--border)] bg-[var(--card-muted)]"
          />
          <div className="p-5">
            <p className="page-kicker">Next best step</p>
            <h2 className="mt-3 text-xl font-semibold tracking-[-0.03em] text-[var(--foreground)]">{nextAction.label}</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{nextAction.description}</p>
          </div>
        </aside>
      </section>

      {error && (
        <section role="alert" className="mb-8 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-[var(--foreground)]">
          <p>{error}</p>
          <button className="btn-secondary mt-3" disabled={isLoading} onClick={() => setRetry((value) => value + 1)}>Retry workspace</button>
        </section>
      )}

      <section className="grid gap-px overflow-hidden border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-5" aria-label="Workspace status">
        <StatusTile label="Documents" value={isLoading ? "--" : available.documents ? String(documents.length) : "Unavailable"} />
        <StatusTile label="Chunks" value={isLoading ? "--" : available.documents ? String(totalChunks) : "Unavailable"} />
        <StatusTile label="Blueprints" value={isLoading ? "--" : available.blueprints ? String(blueprints.length) : "Unavailable"} />
        <StatusTile label="Runtime ready" value={isLoading ? "--" : available.readiness ? String(runtimeReadyCount) : "Unavailable"} />
        <StatusTile label="AI review" value="opt-in" accent />
      </section>

      <section id="product-modes" className="mt-14">
        <div className="max-w-2xl">
          <p className="page-kicker">Choose the path</p>
          <h2 className="display-title mt-4 text-3xl leading-tight sm:text-[2.35rem]">
            One design desk. Two outcomes.
          </h2>
          <p className="mt-4 text-base leading-7 text-[var(--text-secondary)]">
            You do not need a Unity project to get value. Use the dashboard to organize a game, then connect a runtime
            only when your team is ready.
          </p>
        </div>

        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          {productModes.map((mode) => (
            <article key={mode.title} className="status-strip rounded-2xl p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="page-kicker">{mode.eyebrow}</p>
                  <h3 className="mt-4 text-2xl font-semibold tracking-normal text-[var(--foreground)]">{mode.title}</h3>
                </div>
                {mode.recommended && (
                  <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">
                    Start here
                  </span>
                )}
              </div>

              <p className="mt-4 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">{mode.body}</p>

              <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                {mode.points.map((point) => (
                  <li key={point} className="flex gap-3 text-sm leading-6 text-[var(--foreground)]">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>

              <Link href={mode.href} className="btn-secondary mt-7">
                {mode.action}
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-12 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="status-strip rounded-2xl p-6">
          <p className="page-kicker">Workflow</p>
          <h2 className="display-title mt-4 text-3xl leading-tight">From document to game systems.</h2>
          <div className="mt-7 grid gap-4 md:grid-cols-4">
            <FlowStep index="01" title="Source" body="Add the GDD, lore, characters, quests, or level notes." href="/knowledge" />
            <FlowStep index="02" title="Blueprint" body="Generate structured game sections from one selected source." href="/blueprints" />
            <FlowStep index="03" title="Grounding" body="Ask lore questions and inspect citations before trusting output." href="/query" />
            <FlowStep index="04" title="Runtime" body="Materialize approved data and test dialogue, quests, and hints." href="/vertical-slice" />
          </div>
        </div>

        <aside className="panel-muted rounded-2xl p-6">
          <p className="page-kicker">Readiness</p>
          <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[var(--foreground)]">
            {isLoading ? "Checking workspace" : !error && health?.status === "healthy" ? "Workspace is connected" : "Needs attention"}
          </h2>
          <div className="mt-5 space-y-3">
            <ReadinessRow label="Backend" value={health?.status ?? "unavailable"} good={health?.status === "healthy"} loading={isLoading} />
            <ReadinessRow label="Database" value={health?.database ?? "unavailable"} good={health?.database === "healthy"} loading={isLoading} />
            <ReadinessRow label="Vector index" value={health?.chromadb ?? "unavailable"} good={health?.chromadb === "healthy"} loading={isLoading} />
            <ReadinessRow label="AI mode" value={isLocalMode ? "local demo" : provider ?? "unavailable"} good={Boolean(provider)} loading={isLoading} />
          </div>
        </aside>
      </section>
    </main>
  );
}

function FirstRunWorkspace() {
  const steps = [
    {
      number: "01",
      title: "Add the source of truth",
      body: "Start with one GDD. You can add lore, NPC notes, level briefs, and technical constraints later.",
    },
    {
      number: "02",
      title: "Review what is missing",
      body: "GameMind turns uncertain or conflicting details into decisions instead of quietly inventing an answer.",
    },
    {
      number: "03",
      title: "Review before runtime",
      body: "Generate from indexed evidence, inspect citations and critique, then approve and materialize only explicit runtime data.",
    },
  ];

  return (
    <main className="page-shell">
      <section className="grid min-h-[calc(100dvh-11rem)] items-center gap-10 py-8 lg:grid-cols-[minmax(0,1fr)_23rem] lg:py-12">
        <div className="max-w-3xl">
          <p className="page-kicker">New workspace</p>
          <h1 className="display-title mt-4 max-w-2xl text-[2.45rem] leading-[1.04] sm:text-[3.35rem]">
            Begin with a document you can defend.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-[var(--text-secondary)]">
            Add one design document first. GameMind will keep the source, the design decisions, and the resulting blueprint connected as your game develops.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/knowledge" className="btn-primary">
              Open sources
            </Link>
            <Link href="/blueprints" className="btn-secondary">
              Preview blueprint workflow
            </Link>
          </div>

          <p className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">
            Not ready with your own GDD? Load the Frostpeak sample from Sources to explore the full workflow without changing this workspace plan.
          </p>
        </div>

        <aside className="status-strip rounded-2xl p-6" aria-label="First workspace steps">
          <p className="page-kicker">Your path</p>
          <ol className="mt-6 space-y-6">
            {steps.map((step) => (
              <li key={step.number} className="onboarding-step">
                <span className="onboarding-step__number">{step.number}</span>
                <div>
                  <h2 className="text-base font-semibold text-[var(--foreground)]">{step.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </section>
    </main>
  );
}

function StatusTile({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="metric-tile">
      <p className="page-kicker">{label}</p>
      <p className={`mt-3 text-2xl font-semibold tracking-normal ${accent ? "text-[var(--accent)]" : "text-[var(--foreground)]"}`}>
        {value}
      </p>
    </div>
  );
}

function FlowStep({ index, title, body, href }: { index: string; title: string; body: string; href: string }) {
  return (
    <Link
      href={href}
      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 transition hover:border-[var(--foreground)] hover:bg-[var(--accent-soft)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
    >
      <p className="page-kicker">{index}</p>
      <h3 className="mt-4 text-base font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{body}</p>
    </Link>
  );
}

function ReadinessRow({
  label,
  value,
  good,
  loading,
}: {
  label: string;
  value: string;
  good: boolean;
  loading: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
      <span className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
        <span className={`h-1.5 w-1.5 rounded-full ${loading ? "bg-[var(--text-tertiary)]" : good ? "bg-[var(--green)]" : "bg-[var(--warning)]"}`} />
        {label}
      </span>
      <span className="text-sm font-semibold capitalize text-[var(--foreground)]">{loading ? "checking" : value}</span>
    </div>
  );
}
