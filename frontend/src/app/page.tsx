"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api, DocumentResponse } from "@/lib/api";

export default function WorkspaceOverview() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Mock Recent Query Log (Phase 1 UI - Neutral scoring)
  const mockQueries = [
    { query: "Who is King Arven?", citations: 3, similarity: "98.2%", confidence: "High", time: "5 mins ago" },
    { query: "What caused the Ember Siege?", citations: 2, similarity: "95.4%", confidence: "High", time: "12 mins ago" },
    { query: "What faction controls Frostpeak ruins?", citations: 5, similarity: "88.1%", confidence: "Medium", time: "1 hour ago" },
  ];

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const docs = await api.getDocuments();
        setDocuments(docs);
      } catch (err) {
        console.error("Failed to fetch documents for dashboard stats:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchStats();
  }, []);

  // Helper to estimate token counts based on standard characters mapping
  const estimateTokens = (count: number) => {
    return `${((count * 220) / 1000).toFixed(1)}k`;
  };

  // Helper to map world name based on lore document titles
  const getWorldName = (title: string): string => {
    const t = title.toLowerCase();
    if (t.includes("siege") || t.includes("arven") || t.includes("kingdom")) return "Frostpeak";
    if (t.includes("ashen") || t.includes("court")) return "Ashen Court";
    if (t.includes("vulcana") || t.includes("faction")) return "Vulcana";
    return "Universal";
  };

  // Helper to estimate total chunks count
  const getTotalChunks = () => {
    return documents.reduce((sum, doc) => sum + (doc.chunks_count || 0), 0);
  };

  const systemMetrics = [
    { label: "Documents Indexed", value: isLoading ? "..." : String(documents.length), type: "mono" },
    { label: "Chunks Stored", value: isLoading ? "..." : String(getTotalChunks()), type: "mono" },
    { label: "Vector Dimension", value: "768 (Cosine)", type: "mono" },
    { label: "Database Status", value: "Connected", type: "status", color: "text-emerald-400" },
    { label: "Gemini Service", value: "Active", type: "status", color: "text-emerald-400" },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 max-w-7xl mx-auto pb-12 animate-fade-in">
      
      {/* Left Column: Data Tables (3 cols wide) */}
      <div className="lg:col-span-3 space-y-10">
        
        {/* Workspace Title Header */}
        <div className="space-y-1.5 border-b border-[#262626] pb-4">
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
            Workspace Overview
          </h2>
          <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
            Manage narrative source files and query index registers. All game assets are cataloged, vectorized, and compiled for runtime dialogue lookups.
          </p>
        </div>

        {/* Section 1: Ingested Game Lore Files */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#fafafa]">World Lore Catalog</span>
            <Link href="/knowledge" className="text-xs text-[#a1a1aa] hover:text-[#fafafa] hover:underline font-mono text-[11px] transition">
              MANAGE KNOWLEDGE BASE &rarr;
            </Link>
          </div>

          {/* Vercel-Style Table */}
          <div className="border border-[#262626] rounded bg-[#111111]/10 overflow-hidden">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider select-none">
                  <th className="py-2.5 px-4 font-bold">Document Name</th>
                  <th className="py-2.5 px-4 font-bold text-center">Chunks</th>
                  <th className="py-2.5 px-4 font-bold text-center">Tokens</th>
                  <th className="py-2.5 px-4 font-bold">World</th>
                  <th className="py-2.5 px-4">Last Indexed</th>
                  <th className="py-2.5 px-4 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]/80 font-sans">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500 font-mono text-xs">
                      LOADING FILES CATALOG...
                    </td>
                  </tr>
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500 font-mono text-xs">
                      NO DOCUMENTS INGESTED YET
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-[#111111]/30 transition duration-150">
                      <td className="py-2.5 px-4 font-semibold text-[#fafafa] font-mono text-[12px]">{doc.title}</td>
                      <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center">{doc.chunks_count}</td>
                      <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center">{estimateTokens(doc.chunks_count)}</td>
                      <td className="py-2.5 px-4 text-[#fafafa]">{getWorldName(doc.title)}</td>
                      <td className="py-2.5 px-4 text-[#a1a1aa]">{new Date(doc.created_at).toLocaleDateString()}</td>
                      <td className="py-2.5 px-4 text-right flex items-center justify-end gap-1.5 text-[#a1a1aa]">
                        <span className="text-emerald-400 text-[9px]">●</span>
                        <span className="font-mono text-[10px] uppercase tracking-wide">Synced</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 2: Recent Queries */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#fafafa]">Recent Retrieval Sandbox Queries</span>
            <Link href="/query" className="text-xs text-[#a1a1aa] hover:text-[#fafafa] hover:underline font-mono text-[11px] transition">
              OPEN QUERY STUDIO &rarr;
            </Link>
          </div>

          {/* Vercel-Style Table */}
          <div className="border border-[#262626] rounded bg-[#111111]/10 overflow-hidden">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider select-none">
                  <th className="py-2.5 px-4 font-bold">Query Expression</th>
                  <th className="py-2.5 px-4 font-bold text-center">Citations</th>
                  <th className="py-2.5 px-4 font-bold text-center">Similarity</th>
                  <th className="py-2.5 px-4 font-bold">Confidence</th>
                  <th className="py-2.5 px-4 text-right">Executed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]/80 font-sans">
                {mockQueries.map((item, idx) => (
                  <tr key={idx} className="hover:bg-[#111111]/30 transition duration-150">
                    <td className="py-2.5 px-4 font-semibold text-[#fafafa] truncate max-w-xs">{item.query}</td>
                    <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center">{item.citations} cited</td>
                    <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center font-bold">{item.similarity}</td>
                    <td className="py-2.5 px-4">
                      <span className="px-1.5 py-0.5 rounded border border-[#262626] bg-[#111111] font-mono text-[9px] text-[#a1a1aa] uppercase tracking-wider">
                        {item.confidence}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-right text-[#a1a1aa]">{item.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Right Column: System Overview Panel (1 col wide) */}
      <div className="space-y-6">
        <div className="rounded border border-[#262626] bg-[#111111] p-5 h-[calc(100vh-140px)] flex flex-col justify-between">
          <div className="space-y-4">
            <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-3 block">
              System Overview
            </span>
            
            <div className="space-y-3 font-mono text-[11px]">
              {systemMetrics.map((item) => (
                <div key={item.label} className="flex flex-col gap-1 border-b border-[#262626]/50 pb-2.5">
                  <span className="text-slate-500 uppercase tracking-wide text-[9px]">{item.label}</span>
                  {item.type === "status" ? (
                    <div className="flex items-center gap-1.5 font-sans text-xs">
                      <span className="text-emerald-500 text-[10px]">●</span>
                      <span className="text-[#fafafa] font-mono text-[11px] uppercase tracking-wide">{item.value}</span>
                    </div>
                  ) : (
                    <span className="text-[#fafafa] font-bold text-[12px]">{item.value}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          {/* Quick Help Tip */}
          <div className="p-3 bg-[#0a0a0a] rounded border border-[#262626]/60 text-[10px] text-slate-500 leading-relaxed font-sans select-none">
            Use the keyboard shortcut <kbd className="bg-[#171717] px-1 rounded text-[#fafafa] font-mono border border-[#262626]">Ctrl + K</kbd> anywhere to access the workspace index search command utility.
          </div>
        </div>
      </div>
    </div>
  );
}
