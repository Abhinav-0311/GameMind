"use client";

import React, { useEffect, useState } from "react";
import { 
  api, 
  OverviewMetrics, 
  NPCCostBreakdown, 
  MemoryMetrics, 
  TelemetryLog 
} from "@/lib/api";

export default function AnalyticsDashboard() {
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [costs, setCosts] = useState<NPCCostBreakdown[]>([]);
  const [memories, setMemories] = useState<MemoryMetrics | null>(null);
  const [logs, setLogs] = useState<TelemetryLog[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  
  // Filter and pagination states
  const [selectedNpc, setSelectedNpc] = useState("");
  const [selectedAction, setSelectedAction] = useState("");
  const [limit] = useState(15);
  const [offset, setOffset] = useState(0);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isLogsLoading, setIsLogsLoading] = useState(false);

  useEffect(() => {
    const fetchCoreMetrics = async () => {
      try {
        const [overviewData, costsData, memoryData] = await Promise.all([
          api.getOverviewMetrics(),
          api.getNPCCosts(),
          api.getMemoryMetrics()
        ]);
        setOverview(overviewData);
        setCosts(costsData);
        setMemories(memoryData);
      } catch (err) {
        console.error("Failed to fetch core analytics metrics:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCoreMetrics();
  }, []);

  useEffect(() => {
    const fetchLogsData = async () => {
      setIsLogsLoading(true);
      try {
        const result = await api.getTelemetryLogs({
          npc_slug: selectedNpc || undefined,
          action_type: selectedAction || undefined,
          limit,
          offset
        });
        setLogs(result.logs);
        setTotalLogs(result.total);
      } catch (err) {
        console.error("Failed to fetch logs:", err);
      } finally {
        setIsLogsLoading(false);
      }
    };
    fetchLogsData();
  }, [selectedNpc, selectedAction, offset, limit]);

  const handlePrevPage = () => {
    if (offset >= limit) {
      setOffset(offset - limit);
    }
  };

  const handleNextPage = () => {
    if (offset + limit < totalLogs) {
      setOffset(offset + limit);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] font-mono text-xs text-slate-500 gap-4">
        <span className="animate-pulse">LOADING OBSERVABILITY METRICS...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12 animate-fade-in font-sans">
      
      {/* Title Header */}
      <div className="space-y-1.5 border-b border-[#262626] pb-4">
        <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
          Observability & Analytics
        </h2>
        <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
          Monitor LLM requests, token usage, real-time cost tracking, and inspect narrative memory persistence metrics.
        </p>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        
        {/* Card 1: Total Calls */}
        <div className="rounded border border-[#262626] bg-[#111111] p-4.5 space-y-2">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">LLM Requests</span>
          <div className="text-xl font-mono font-bold text-[#fafafa]">
            {overview?.total_requests ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            {overview?.breakdown_by_action.map(b => `${b.action}: ${b.count}`).join(" | ") || "No requests logged"}
          </div>
        </div>

        {/* Card 2: Cost */}
        <div className="rounded border border-[#262626] bg-[#111111] p-4.5 space-y-2">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">Cumulative Cost</span>
          <div className="text-xl font-mono font-bold text-[#b9ff66]">
            ${overview?.total_cost_usd.toFixed(6) ?? "0.000000"}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            USD (Numeric Precision)
          </div>
        </div>

        {/* Card 3: Avg Latency */}
        <div className="rounded border border-[#262626] bg-[#111111] p-4.5 space-y-2">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">Avg Latency</span>
          <div className="text-xl font-mono font-bold text-[#fafafa]">
            {overview?.avg_latency_ms ? `${Math.round(overview.avg_latency_ms)}ms` : "0ms"}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            Network & model response duration
          </div>
        </div>

        {/* Card 4: Tokens usage */}
        <div className="rounded border border-[#262626] bg-[#111111] p-4.5 space-y-2">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">Token Volumes</span>
          <div className="text-xl font-mono font-bold text-[#fafafa]">
            {((overview?.total_input_tokens ?? 0) + (overview?.total_output_tokens ?? 0)).toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            In: {(overview?.total_input_tokens ?? 0).toLocaleString()} | Out: {(overview?.total_output_tokens ?? 0).toLocaleString()}
          </div>
        </div>

      </div>

      {/* Row 2: Cost Breakdowns & Memory Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Memory Metrics Panel */}
        <div className="rounded border border-[#262626] bg-[#111111]/45 p-5 space-y-4 lg:col-span-1">
          <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-2 block">
            Memory Store Diagnostics
          </span>
          <div className="space-y-3 font-mono text-[11px]">
            <div className="flex justify-between border-b border-[#262626]/50 pb-2">
              <span className="text-slate-500">ACTIVE MEMORIES</span>
              <span className="text-[#fafafa] font-bold">{memories?.active_memories ?? 0}</span>
            </div>
            <div className="flex justify-between border-b border-[#262626]/50 pb-2">
              <span className="text-slate-500">ARCHIVED (DUPLICATES)</span>
              <span className="text-[#fafafa] font-bold">{memories?.archived_memories ?? 0}</span>
            </div>
            <div className="flex justify-between border-b border-[#262626]/50 pb-2">
              <span className="text-slate-500">PROMOTED (FROM CHATS)</span>
              <span className="text-[#fafafa] font-bold">{memories?.promoted_memories ?? 0}</span>
            </div>
            <div className="flex justify-between border-b border-[#262626]/50 pb-2">
              <span className="text-slate-500">AVG IMPORTANCE SCORE</span>
              <span className="text-[#fafafa] font-bold">{memories?.average_importance_score.toFixed(2) ?? "0.00"}</span>
            </div>
            <div className="flex justify-between pb-1">
              <span className="text-slate-500">FAILED CHROMA INDEXINGS</span>
              <span className={`font-bold ${memories?.failed_chroma_indexing_count ? "text-amber-500" : "text-emerald-400"}`}>
                {memories?.failed_chroma_indexing_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Cost Allocation by NPC Table */}
        <div className="rounded border border-[#262626] bg-[#111111]/45 p-5 space-y-4 lg:col-span-2">
          <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-2 block">
            LLM Cost Allocation by NPC
          </span>
          <div className="overflow-hidden border border-[#262626] rounded bg-[#0a0a0a]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider">
                  <th className="py-2 px-4 font-bold">NPC Slug</th>
                  <th className="py-2 px-4 font-bold text-center">Requests</th>
                  <th className="py-2 px-4 font-bold text-right">Aggregated Cost (USD)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]/60 font-mono text-[11px]">
                {costs.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-4 text-center text-slate-600">
                      NO NPC TELEMETRY LOGGED YET
                    </td>
                  </tr>
                ) : (
                  costs.map((c) => (
                    <tr key={c.npc_slug} className="hover:bg-[#111111]/40">
                      <td className="py-2 px-4 text-[#fafafa] font-semibold">{c.npc_slug}</td>
                      <td className="py-2 px-4 text-center text-[#a1a1aa]">{c.requests_count}</td>
                      <td className="py-2 px-4 text-right text-[#b9ff66]">${c.total_cost_usd.toFixed(6)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Row 3: Progressive Hint Metrics */}
      <div className="rounded border border-[#262626] bg-[#111111]/45 p-5 space-y-4">
        <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-2 block">
          Progressive Hint Engine Telemetry
        </span>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 font-mono text-[11px]">
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Generated</div>
            <div className="text-[#fafafa] font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hints_generated_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Cache Hits</div>
            <div className="text-emerald-400 font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_cache_hits_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Cache Misses</div>
            <div className="text-slate-400 font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_cache_misses_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Cooldown Blocks</div>
            <div className="text-amber-500 font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_cooldown_blocks_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Progression Blocks</div>
            <div className="text-amber-500 font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_progression_blocks_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Level 1</div>
            <div className="text-[#fafafa] font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_level_1_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Level 2</div>
            <div className="text-[#fafafa] font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_level_2_total")?.count ?? 0}
            </div>
          </div>
          <div className="rounded border border-[#262626]/50 bg-[#0a0a0a] p-3 text-center">
            <div className="text-slate-500 text-[9px] uppercase tracking-wide mb-1">Level 3</div>
            <div className="text-[#fafafa] font-bold text-sm">
              {overview?.breakdown_by_action.find(a => a.action === "progressive_hint_level_3_total")?.count ?? 0}
            </div>
          </div>
        </div>
      </div>

      {/* Observability Live Traces list */}
      <div className="space-y-4">
        
        {/* Table Title and Filters Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#262626] pb-3">
          <span className="text-xs font-semibold text-[#fafafa]">Live Telemetry Logs Trace Console</span>
          
          {/* Simple Filters */}
          <div className="flex items-center gap-3">
            <select
              value={selectedAction}
              onChange={(e) => { setSelectedAction(e.target.value); setOffset(0); }}
              className="bg-[#111111] border border-[#262626] rounded text-slate-400 font-mono text-[10px] uppercase tracking-wider py-1 px-2.5 outline-none hover:text-[#fafafa] transition"
            >
              <option value="">All Actions</option>
              <option value="dialogue">Dialogue</option>
              <option value="summarization">Summarization</option>
              <option value="progressive_hints_generated_total">progressive_hints_generated_total</option>
              <option value="progressive_hint_cache_hits_total">progressive_hint_cache_hits_total</option>
              <option value="progressive_hint_cache_misses_total">progressive_hint_cache_misses_total</option>
              <option value="progressive_hint_cooldown_blocks_total">progressive_hint_cooldown_blocks_total</option>
              <option value="progressive_hint_progression_blocks_total">progressive_hint_progression_blocks_total</option>
            </select>
            
            <input
              type="text"
              placeholder="Filter by NPC slug..."
              value={selectedNpc}
              onChange={(e) => { setSelectedNpc(e.target.value); setOffset(0); }}
              className="bg-[#111111] border border-[#262626] rounded text-slate-300 font-mono text-[10px] py-1 px-2.5 w-44 placeholder-slate-600 outline-none focus:border-slate-700 transition"
            />
          </div>
        </div>

        {/* Live Logs Table */}
        <div className="border border-[#262626] rounded bg-[#111111]/10 overflow-hidden">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider">
                <th className="py-2.5 px-4 font-bold">Timestamp</th>
                <th className="py-2.5 px-4 font-bold">Action</th>
                <th className="py-2.5 px-4 font-bold">NPC Slug</th>
                <th className="py-2.5 px-4 font-bold">Model</th>
                <th className="py-2.5 px-4 font-bold text-center">Latency</th>
                <th className="py-2.5 px-4 font-bold text-center">Tokens</th>
                <th className="py-2.5 px-4 font-bold text-right">Cost</th>
                <th className="py-2.5 px-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#262626]/80 font-mono text-[11px]">
              {isLogsLoading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-600 animate-pulse">
                    FETCHING LOG TRACES...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-600">
                    NO LOGS FOUND MATCHING FILTER CRITERIA
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#111111]/30 transition duration-150">
                    <td className="py-2.5 px-4 text-slate-500">{new Date(log.created_at).toLocaleTimeString()}</td>
                    <td className="py-2.5 px-4">
                      <span className={`px-1 rounded border text-[9px] uppercase tracking-wide ${
                        log.action_type === "dialogue" 
                          ? "border-[#262626] bg-[#111111] text-[#fafafa]"
                          : "border-slate-700 bg-slate-800/20 text-[#a1a1aa]"
                      }`}>
                        {log.action_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-300 font-semibold">{log.npc_slug}</td>
                    <td className="py-2.5 px-4 text-slate-400">{log.model_used} ({log.llm_provider})</td>
                    <td className="py-2.5 px-4 text-center text-slate-300">{log.latency_ms}ms</td>
                    <td className="py-2.5 px-4 text-center text-slate-400">{log.input_tokens + log.output_tokens}</td>
                    <td className="py-2.5 px-4 text-right text-[#b9ff66]">${log.estimated_cost_usd.toFixed(6)}</td>
                    <td className="py-2.5 px-4 text-right">
                      {log.error ? (
                        <span className="text-amber-500 font-semibold" title={log.error}>
                          ERROR ({log.error})
                        </span>
                      ) : log.safety_blocked ? (
                        <span className="text-red-400 font-semibold">BLOCKED</span>
                      ) : (
                        <span className="text-emerald-400 font-semibold">SUCCESS</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Simple Pagination controls */}
        <div className="flex items-center justify-between font-mono text-[10px] text-slate-500 select-none pt-2">
          <span>
            SHOWING {offset + 1}-{Math.min(offset + limit, totalLogs)} OF {totalLogs} TRACES
          </span>
          <div className="flex gap-2">
            <button
              onClick={handlePrevPage}
              disabled={offset === 0 || isLogsLoading}
              className={`px-3 py-1 rounded border border-[#262626] bg-[#111111] text-[#fafafa] font-bold ${
                offset === 0 ? "opacity-50 cursor-not-allowed" : "hover:bg-[#171717]"
              }`}
            >
              PREV
            </button>
            <button
              onClick={handleNextPage}
              disabled={offset + limit >= totalLogs || isLogsLoading}
              className={`px-3 py-1 rounded border border-[#262626] bg-[#111111] text-[#fafafa] font-bold ${
                offset + limit >= totalLogs ? "opacity-50 cursor-not-allowed" : "hover:bg-[#171717]"
              }`}
            >
              NEXT
            </button>
          </div>
        </div>

      </div>

    </div>
  );
}
