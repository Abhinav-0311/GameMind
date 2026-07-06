"use client";

import React, { useEffect, useMemo, useState } from "react";
import { api, MemoryMetrics, NPCCostBreakdown, OverviewMetrics, TelemetryLog } from "@/lib/api";

const PAGE_SIZE = 12;

export default function AnalyticsDashboard() {
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [costs, setCosts] = useState<NPCCostBreakdown[]>([]);
  const [memories, setMemories] = useState<MemoryMetrics | null>(null);
  const [logs, setLogs] = useState<TelemetryLog[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [selectedNpc, setSelectedNpc] = useState("");
  const [selectedAction, setSelectedAction] = useState("");
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCoreMetrics = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [overviewData, costsData, memoryData] = await Promise.all([
          api.getOverviewMetrics(),
          api.getNPCCosts(),
          api.getMemoryMetrics(),
        ]);
        setOverview(overviewData);
        setCosts(costsData);
        setMemories(memoryData);
      } catch (err) {
        console.error("Failed to fetch analytics metrics:", err);
        setError("Observability metrics could not be loaded. Check that the backend is running.");
      } finally {
        setIsLoading(false);
      }
    };

    void Promise.resolve().then(fetchCoreMetrics);
  }, []);

  useEffect(() => {
    const fetchLogsData = async () => {
      setIsLogsLoading(true);

      try {
        const result = await api.getTelemetryLogs({
          npc_slug: selectedNpc.trim() || undefined,
          action_type: selectedAction || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        setLogs(result.logs);
        setTotalLogs(result.total);
      } catch (err) {
        console.error("Failed to fetch telemetry logs:", err);
      } finally {
        setIsLogsLoading(false);
      }
    };

    void Promise.resolve().then(fetchLogsData);
  }, [selectedAction, selectedNpc, offset]);

  const actionCounts = useMemo(
    () => new Map((overview?.breakdown_by_action ?? []).map((item) => [item.action, item.count])),
    [overview]
  );

  const topActions = useMemo(
    () => [...(overview?.breakdown_by_action ?? [])].sort((a, b) => b.count - a.count).slice(0, 5),
    [overview]
  );

  const topNpcCosts = useMemo(
    () => [...costs].sort((a, b) => b.requests_count - a.requests_count).slice(0, 5),
    [costs]
  );

  const totalTokens = (overview?.total_input_tokens ?? 0) + (overview?.total_output_tokens ?? 0);
  const issueCount = (overview?.error_count ?? 0) + (overview?.safety_blocked_count ?? 0) + (memories?.failed_chroma_indexing_count ?? 0);
  const healthLabel = issueCount === 0 ? "Healthy" : `${issueCount} issues`;
  const shownStart = totalLogs === 0 ? 0 : offset + 1;
  const shownEnd = Math.min(offset + PAGE_SIZE, totalLogs);

  const hintMetrics = [
    { label: "Generated", value: actionCounts.get("progressive_hints_generated_total") ?? 0 },
    { label: "Cache hits", value: actionCounts.get("progressive_hint_cache_hits_total") ?? 0 },
    { label: "Cache misses", value: actionCounts.get("progressive_hint_cache_misses_total") ?? 0 },
    { label: "Cooldown blocks", value: actionCounts.get("progressive_hint_cooldown_blocks_total") ?? 0 },
    { label: "Progression blocks", value: actionCounts.get("progressive_hint_progression_blocks_total") ?? 0 },
    { label: "Level 1", value: actionCounts.get("progressive_hint_level_1_total") ?? 0 },
    { label: "Level 2", value: actionCounts.get("progressive_hint_level_2_total") ?? 0 },
    { label: "Level 3", value: actionCounts.get("progressive_hint_level_3_total") ?? 0 },
  ];

  return (
    <main className="page-shell">
      <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-12">
        <div className="max-w-3xl">
          <p className="page-kicker">Observability</p>
          <h1 className="display-title mt-5 text-[2.65rem] leading-tight sm:text-6xl">
            Understand runtime behavior at a glance.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[#a5afbd]">
            Monitor local model usage, dialogue activity, memory persistence, hint flow, and errors without reading raw
            telemetry counters.
          </p>
        </div>

        <aside className="panel self-start rounded-xl p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="mono-label text-[#7c8794]">Runtime health</p>
              <h2 className="mt-3 font-display text-3xl font-semibold text-[#f7f8fa]">{isLoading ? "Checking" : healthLabel}</h2>
            </div>
            <span
              className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
                issueCount === 0 ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"
              }`}
            >
              {issueCount === 0 ? "Clean" : "Review"}
            </span>
          </div>
          <div className="mt-5 divide-y divide-[#222a33]">
            <FactRow label="Requests" value={String(overview?.total_requests ?? 0)} />
            <FactRow label="Errors" value={String(overview?.error_count ?? 0)} />
            <FactRow label="Safety blocks" value={String(overview?.safety_blocked_count ?? 0)} />
            <FactRow label="Model cost" value={formatCurrency(overview?.total_cost_usd ?? 0)} />
          </div>
        </aside>
      </section>

      {error && (
        <div className="mb-6 rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      )}

      {isLoading ? (
        <LoadingState />
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Total requests" value={String(overview?.total_requests ?? 0)} description="Logged runtime actions" />
            <MetricCard label="Cost" value={formatCurrency(overview?.total_cost_usd ?? 0)} description="Local mode should stay at zero" accent />
            <MetricCard label="Latency" value={`${Math.round(overview?.avg_latency_ms ?? 0)}ms`} description="Average response time" />
            <MetricCard label="Tokens" value={totalTokens.toLocaleString()} description={`${(overview?.total_input_tokens ?? 0).toLocaleString()} in, ${(overview?.total_output_tokens ?? 0).toLocaleString()} out`} />
          </section>

          <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="panel overflow-hidden rounded-xl">
              <div className="border-b border-[#222a33] px-5 py-4">
                <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Activity shape</h2>
                <p className="mt-1 text-sm leading-6 text-[#a5afbd]">
                  The most common runtime events. This should match what you are testing in the simulator.
                </p>
              </div>
              <div className="space-y-4 p-5">
                {topActions.length === 0 ? (
                  <EmptyText title="No activity yet" body="Run dialogue, quest, or hint flows to populate this view." />
                ) : (
                  topActions.map((action) => (
                    <ActivityBar
                      key={action.action}
                      label={humanizeAction(action.action)}
                      value={action.count}
                      max={Math.max(...topActions.map((item) => item.count), 1)}
                    />
                  ))
                )}
              </div>
            </div>

            <div className="panel rounded-xl p-5">
              <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Memory store</h2>
              <div className="mt-5 divide-y divide-[#222a33]">
                <FactRow label="Active" value={String(memories?.active_memories ?? 0)} />
                <FactRow label="Archived" value={String(memories?.archived_memories ?? 0)} />
                <FactRow label="Promoted" value={String(memories?.promoted_memories ?? 0)} />
                <FactRow label="Avg importance" value={(memories?.average_importance_score ?? 0).toFixed(2)} />
                <FactRow label="Index failures" value={String(memories?.failed_chroma_indexing_count ?? 0)} />
              </div>
            </div>
          </section>

          <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="panel overflow-hidden rounded-xl">
              <div className="border-b border-[#222a33] px-5 py-4">
                <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Progressive hint engine</h2>
                <p className="mt-1 text-sm leading-6 text-[#a5afbd]">
                  Cache behavior, blocked requests, and level distribution.
                </p>
              </div>
              <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
                {hintMetrics.map((metric) => (
                  <FactTile key={metric.label} label={metric.label} value={String(metric.value)} />
                ))}
              </div>
            </div>

            <div className="panel rounded-xl p-5">
              <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">NPC usage</h2>
              <div className="mt-5 space-y-3">
                {topNpcCosts.length === 0 ? (
                  <EmptyText title="No NPC usage" body="Talk to an NPC in the simulator to populate usage." />
                ) : (
                  topNpcCosts.map((npc) => (
                    <div key={npc.npc_slug} className="rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-semibold text-[#f7f8fa]">{npc.npc_slug}</p>
                        <span className="text-sm font-semibold text-[#8bdff0]">{npc.requests_count}</span>
                      </div>
                      <p className="mt-1 text-xs text-[#7c8794]">{formatCurrency(npc.total_cost_usd)} total cost</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="panel mt-8 overflow-hidden rounded-xl">
            <div className="flex flex-col gap-4 border-b border-[#222a33] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="font-display text-2xl font-semibold text-[#f7f8fa]">Recent trace log</h2>
                <p className="mt-1 text-sm leading-6 text-[#a5afbd]">
                  Latest runtime events, filtered when you need to inspect a specific NPC or action.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <select
                  value={selectedAction}
                  onChange={(event) => {
                    setSelectedAction(event.target.value);
                    setOffset(0);
                  }}
                  className="min-h-10 rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
                >
                  <option value="">All actions</option>
                  {topActions.map((action) => (
                    <option key={action.action} value={action.action}>
                      {humanizeAction(action.action)}
                    </option>
                  ))}
                  <option value="dialogue">Dialogue</option>
                </select>
                <input
                  type="search"
                  value={selectedNpc}
                  onChange={(event) => {
                    setSelectedNpc(event.target.value);
                    setOffset(0);
                  }}
                  placeholder="NPC slug"
                  className="min-h-10 rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
                />
              </div>
            </div>

            <div className="divide-y divide-[#222a33]">
              {isLogsLoading ? (
                <div className="space-y-3 p-5">
                  {[1, 2, 3].map((item) => (
                    <div key={item} className="h-20 animate-pulse rounded-md bg-[#151b22]" />
                  ))}
                </div>
              ) : logs.length === 0 ? (
                <div className="px-5 py-12 text-center">
                  <EmptyText title="No traces found" body="Change filters or run a simulator action." />
                </div>
              ) : (
                logs.map((log) => <TraceRow key={log.id} log={log} />)
              )}
            </div>

            <div className="flex flex-col gap-3 border-t border-[#222a33] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-[#7c8794]">
                Showing {shownStart}-{shownEnd} of {totalLogs}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                  disabled={offset === 0 || isLogsLoading}
                  className="inline-flex min-h-9 items-center rounded-md border border-[#303a46] px-3 text-xs font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setOffset((current) => current + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= totalLogs || isLogsLoading}
                  className="inline-flex min-h-9 items-center rounded-md border border-[#303a46] px-3 text-xs font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function LoadingState() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((item) => (
        <div key={item} className="h-28 animate-pulse rounded-xl border border-[#222a33] bg-[#101419]" />
      ))}
    </div>
  );
}

function MetricCard({
  label,
  value,
  description,
  accent = false,
}: {
  label: string;
  value: string;
  description: string;
  accent?: boolean;
}) {
  return (
    <div className="panel-muted rounded-xl p-4">
      <p className="mono-label text-[#7c8794]">{label}</p>
      <p className={`mt-3 font-display text-4xl font-semibold ${accent ? "text-[#8bdff0]" : "text-[#f7f8fa]"}`}>{value}</p>
      <p className="mt-2 text-xs leading-5 text-[#a5afbd]">{description}</p>
    </div>
  );
}

function ActivityBar({ label, value, max }: { label: string; value: number; max: number }) {
  const width = Math.max(6, Math.round((value / max) * 100));

  return (
    <div>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="truncate font-semibold text-[#f7f8fa]">{label}</span>
        <span className="text-[#a5afbd]">{value}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#1a212a]">
        <div className="h-full rounded-full bg-[#8bdff0]" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function TraceRow({ log }: { log: TelemetryLog }) {
  const hasIssue = Boolean(log.error || log.safety_blocked);

  return (
    <article className="grid gap-3 px-5 py-4 lg:grid-cols-[10rem_minmax(0,1fr)_8rem_7rem] lg:items-center">
      <div>
        <p className="text-xs text-[#7c8794]">{new Date(log.created_at).toLocaleString()}</p>
        <p className="mt-1 text-xs font-semibold text-[#a5afbd]">{log.npc_slug}</p>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#27303a] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8bdff0]">
            {humanizeAction(log.action_type)}
          </span>
          <span
            className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
              hasIssue ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300"
            }`}
          >
            {hasIssue ? "Review" : "Success"}
          </span>
        </div>
        <p className="mt-2 truncate text-sm text-[#a5afbd]">
          {log.model_used} via {log.llm_provider}
        </p>
        {log.error && <p className="mt-2 text-sm leading-6 text-amber-200">{log.error}</p>}
      </div>
      <div className="text-sm text-[#a5afbd]">
        <span className="font-semibold text-[#f7f8fa]">{log.latency_ms}ms</span>
        <span className="block text-xs text-[#7c8794]">latency</span>
      </div>
      <div className="text-sm text-[#a5afbd] lg:text-right">
        <span className="font-semibold text-[#f7f8fa]">{log.input_tokens + log.output_tokens}</span>
        <span className="block text-xs text-[#7c8794]">{formatCurrency(log.estimated_cost_usd)}</span>
      </div>
    </article>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[#a5afbd]">{label}</span>
      <span className="max-w-40 truncate text-right text-sm font-semibold text-[#f7f8fa]">{value}</span>
    </div>
  );
}

function FactTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel-muted rounded-xl p-3">
      <p className="mono-label text-[#7c8794]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[#f7f8fa]">{value}</p>
    </div>
  );
}

function EmptyText({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-[#f7f8fa]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#a5afbd]">{body}</p>
    </div>
  );
}

function formatCurrency(value: number) {
  if (value === 0) return "$0";
  return `$${value.toFixed(6)}`;
}

function humanizeAction(action: string) {
  return action
    .replace(/_total$/u, "")
    .replace(/_/gu, " ")
    .replace(/\b\w/gu, (letter) => letter.toUpperCase());
}
