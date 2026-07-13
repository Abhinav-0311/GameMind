"use client";

import React, { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { api, BlueprintResponse, DocumentResponse, HealthResponse } from "@/lib/api";

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
          if (process.env.NODE_ENV === "development") {
            console.warn("Workspace overview is unavailable:", err);
          }
          setError("Start Docker, wait for the backend health check, then refresh this page.");
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

  const nextAction: NextAction = useMemo(() => {
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
        label: "Generate a blueprint",
        description: "Convert one source document into narrative, NPC, quest, memory, level, and runtime sections.",
        href: "/blueprints",
        action: "Open blueprints",
      };
    }

    if (!hasRuntimeData) {
      return {
        label: "Approve runtime data",
        description: "Materialize the approved blueprint so the simulator or a game client can consume stable records.",
        href: "/blueprints",
        action: "Materialize",
      };
    }

    return {
      label: "Playtest the runtime loop",
      description: "Verify dialogue, quest acceptance, and progressive hints after the blueprint is materialized.",
      href: "/vertical-slice",
      action: "Open runtime test",
    };
  }, [hasBlueprints, hasDocuments, hasRuntimeData]);

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

  return (
    <main className="page-shell">
      <section className="grid items-center gap-10 py-5 lg:grid-cols-[minmax(0,1fr)_390px] lg:py-10">
        <div className="max-w-3xl">
          <p className="page-kicker">Local-first AI game builder</p>
          <h1 className="display-title mt-5 max-w-3xl text-[2.35rem] leading-[1.05] sm:text-[3.45rem]">
            Design the game first. Integrate the runtime when it matters.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            GameMind helps new game developers convert GDDs, lore, NPC notes, quest ideas, and level concepts into
            grounded blueprints and engine-ready runtime data without requiring paid model APIs.
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

        <aside className="panel overflow-hidden rounded-3xl" aria-label="Recommended next action">
          <Image
            src="/brand/game-builder-workbench.svg"
            alt="GameMind workflow from source document to blueprint and runtime systems"
            width={960}
            height={720}
            priority
            className="h-auto w-full border-b border-[var(--border)] bg-[var(--card-muted)]"
          />
          <div className="p-6">
            <p className="page-kicker">Next best step</p>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-[var(--foreground)]">{nextAction.label}</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{nextAction.description}</p>
          </div>
        </aside>
      </section>

      {error && (
        <section className="mb-8 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-[var(--foreground)]">
          {error}
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5" aria-label="Workspace status">
        <StatusTile label="Documents" value={isLoading ? "--" : String(documents.length)} />
        <StatusTile label="Chunks" value={isLoading ? "--" : String(totalChunks)} />
        <StatusTile label="Blueprints" value={isLoading ? "--" : String(blueprints.length)} />
        <StatusTile label="Runtime ready" value={isLoading ? "--" : String(runtimeReadyCount)} />
        <StatusTile label="AI cost" value="$0" accent />
      </section>

      <section id="product-modes" className="mt-12">
        <div className="max-w-2xl">
          <p className="page-kicker">Choose the path</p>
          <h2 className="display-title mt-4 text-3xl leading-tight sm:text-[2.35rem]">
            GameMind works in two useful ways.
          </h2>
          <p className="mt-4 text-base leading-7 text-[var(--text-secondary)]">
            You do not need a Unity project to get value. Use the dashboard to organize a game, then connect a runtime
            only when your team is ready.
          </p>
        </div>

        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          {productModes.map((mode) => (
            <article key={mode.title} className="panel rounded-3xl p-6">
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
        <div className="panel rounded-3xl p-6">
          <p className="page-kicker">Workflow</p>
          <h2 className="display-title mt-4 text-3xl leading-tight">From document to game systems.</h2>
          <div className="mt-7 grid gap-4 md:grid-cols-4">
            <FlowStep index="01" title="Source" body="Add the GDD, lore, characters, quests, or level notes." href="/knowledge" />
            <FlowStep index="02" title="Blueprint" body="Generate structured game sections from one selected source." href="/blueprints" />
            <FlowStep index="03" title="Grounding" body="Ask lore questions and inspect citations before trusting output." href="/query" />
            <FlowStep index="04" title="Runtime" body="Materialize approved data and test dialogue, quests, and hints." href="/vertical-slice" />
          </div>
        </div>

        <aside className="panel-muted rounded-3xl p-6">
          <p className="page-kicker">Readiness</p>
          <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[var(--foreground)]">
            {isLoading ? "Checking workspace" : health?.status === "healthy" ? "Workspace is connected" : "Needs attention"}
          </h2>
          <div className="mt-5 space-y-3">
            <ReadinessRow label="Backend" value={health?.status ?? "checking"} good={health?.status === "healthy"} loading={isLoading} />
            <ReadinessRow label="Database" value={health?.database ?? "checking"} good={health?.database === "healthy"} loading={isLoading} />
            <ReadinessRow label="Vector index" value={health?.chromadb ?? "checking"} good={health?.chromadb === "healthy"} loading={isLoading} />
            <ReadinessRow label="AI mode" value={isLocalMode ? "local demo" : health?.ai_mode ?? "checking"} good={Boolean(health?.ai_mode)} loading={isLoading} />
          </div>
        </aside>
      </section>
    </main>
  );
}

function StatusTile({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="panel-muted rounded-2xl p-4">
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
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
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
