"use client";

import React, { useEffect, useState } from "react";
import { api, DocumentResponse, BlueprintResponse, BlueprintExportResponse } from "@/lib/api";

export default function BlueprintsDashboard() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [blueprints, setBlueprints] = useState<BlueprintResponse[]>([]);
  const [activeBlueprint, setActiveBlueprint] = useState<BlueprintResponse | null>(null);
  const [activeTab, setActiveTab] = useState<string>("summary");
  const [isGenerating, setIsGenerating] = useState(false);
  const [exportData, setExportData] = useState<BlueprintExportResponse | null>(null);
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const docs = await api.getDocuments();
        setDocuments(docs);
        if (docs.length > 0) {
          setSelectedDocId(docs[0].id);
        }

        const bps = await api.getBlueprints();
        setBlueprints(bps);
        if (bps.length > 0) {
          setActiveBlueprint(bps[0]);
        }
      } catch (err) {
        console.error("Failed to load initial data:", err);
      }
    };
    loadInitialData();
  }, []);

  const handleGenerate = async () => {
    if (!selectedDocId) return;
    setIsGenerating(true);
    try {
      const newBp = await api.generateBlueprint(selectedDocId);
      setBlueprints((prev) => [newBp, ...prev]);
      setActiveBlueprint(newBp);
      // Reload blueprints list
      const bps = await api.getBlueprints();
      setBlueprints(bps);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!activeBlueprint) return;
    try {
      const updated = await api.approveBlueprint(activeBlueprint.id);
      setActiveBlueprint(updated);
      setBlueprints((prev) => prev.map((bp) => (bp.id === updated.id ? updated : bp)));
    } catch {
      alert("Failed to approve blueprint");
    }
  };

  const handleExport = async () => {
    if (!activeBlueprint) return;
    try {
      const exp = await api.exportBlueprint(activeBlueprint.id);
      setExportData(exp);
      setShowExportModal(true);
    } catch {
      alert("Failed to export blueprint");
    }
  };

  const tabs = [
    { id: "summary", label: "Game Summary" },
    { id: "narrative", label: "Narrative Direction" },
    { id: "art", label: "Art Style Direction" },
    { id: "npcs", label: "NPC Archetypes" },
    { id: "memory", label: "NPC Memory Design" },
    { id: "levels", label: "Level Suggestions" },
    { id: "quests", label: "Quest Hooks" },
    { id: "unity", label: "Unity Runtime Preview" }
  ];

  const getSectionData = (tabId: string) => {
    if (!activeBlueprint) return null;
    switch (tabId) {
      case "summary": return activeBlueprint.summary;
      case "narrative": return activeBlueprint.narrative_direction;
      case "art": return activeBlueprint.art_style_direction;
      case "npcs": return activeBlueprint.npc_archetypes;
      case "memory": return activeBlueprint.npc_memory_design;
      case "levels": return activeBlueprint.level_design_suggestions;
      case "quests": return activeBlueprint.quest_hooks;
      case "unity": return activeBlueprint.unity_runtime_preview;
      default: return null;
    }
  };

  const activeSection = getSectionData(activeTab);

  return (
    <div className="max-w-7xl mx-auto pb-12 space-y-8 animate-fade-in">
      
      {/* Title Header */}
      <div className="space-y-1.5 border-b border-[#262626] pb-4">
        <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
          Game Blueprint Studio
        </h2>
        <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
          Select a Game Design Document to analyze. Generate standard blueprint models, review source citations, track template warnings, and export runtime payloads for Unity.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        {/* Left Control Panel: Select and Generate */}
        <div className="lg:col-span-1 space-y-6">
          <div className="rounded border border-[#262626] bg-[#111111] p-5 space-y-5">
            <span className="text-xs font-semibold text-[#fafafa] block border-b border-[#262626] pb-3">
              GDD Document Index
            </span>
            
            <div className="space-y-3">
              <label className="text-[10px] uppercase font-mono text-slate-500 tracking-wider">Select Source GDD</label>
              {documents.length === 0 ? (
                <p className="text-xs text-[#a1a1aa] italic">No GDD documents uploaded yet.</p>
              ) : (
                <select
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  className="w-full bg-[#0a0a0a] border border-[#262626] rounded px-3 py-2 text-xs text-[#fafafa] focus:outline-none focus:border-amber-500 transition font-mono"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <button
              onClick={handleGenerate}
              disabled={isGenerating || documents.length === 0}
              className="w-full bg-amber-500 hover:bg-amber-600 disabled:bg-[#262626] disabled:text-slate-500 text-black font-semibold rounded py-2 text-xs transition duration-200 uppercase tracking-wider font-mono shadow"
            >
              {isGenerating ? "Analyzing GDD..." : "Generate Blueprint"}
            </button>
          </div>

          {/* List of existing blueprints */}
          <div className="rounded border border-[#262626] bg-[#111111] p-5 space-y-3">
            <span className="text-xs font-semibold text-[#fafafa] block border-b border-[#262626] pb-3">
              Blueprints List
            </span>
            {blueprints.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No blueprints generated yet.</p>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {blueprints.map((bp) => (
                  <button
                    key={bp.id}
                    onClick={() => {
                      setActiveBlueprint(bp);
                      setExportData(null);
                    }}
                    className={`w-full text-left p-2.5 rounded border text-xs transition font-mono ${
                      activeBlueprint?.id === bp.id
                        ? "border-amber-500/50 bg-amber-500/5 text-[#fafafa]"
                        : "border-[#262626] hover:bg-[#1c1c1c]/50 text-slate-400"
                    }`}
                  >
                    <div className="font-semibold truncate">{bp.title}</div>
                    <div className="flex justify-between items-center mt-1.5 text-[10px] text-slate-500">
                      <span>Status: {bp.status.toUpperCase()}</span>
                      <span>{new Date(bp.created_at).toLocaleDateString()}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Blueprint Panel: Review, Approve, Export */}
        <div className="lg:col-span-3 space-y-6">
          {activeBlueprint ? (
            <div className="rounded border border-[#262626] bg-[#111111] p-6 space-y-6">
              
              {/* Header: Title, Status, Action Buttons */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#262626] pb-4">
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-[#fafafa] font-mono">{activeBlueprint.title}</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500 font-mono">ID: {activeBlueprint.id}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wide border ${
                      activeBlueprint.status === "approved"
                        ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
                        : "border-amber-500/30 bg-amber-500/5 text-amber-400"
                    }`}>
                      {activeBlueprint.status}
                    </span>
                  </div>
                </div>

                <div className="flex gap-2">
                  {activeBlueprint.status !== "approved" && (
                    <button
                      onClick={handleApprove}
                      className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold px-4 py-1.5 rounded text-xs transition font-mono uppercase tracking-wider"
                    >
                      Approve Blueprint
                    </button>
                  )}
                  <button
                    onClick={handleExport}
                    className="bg-[#fafafa] hover:bg-slate-200 text-black font-semibold px-4 py-1.5 rounded text-xs transition font-mono uppercase tracking-wider shadow"
                  >
                    Export to Unity JSON
                  </button>
                </div>
              </div>

              {/* Module Tab Selector */}
              <div className="flex border-b border-[#262626] overflow-x-auto pb-px">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`whitespace-nowrap px-4 py-2 border-b-2 text-xs font-semibold transition ${
                      activeTab === tab.id
                        ? "border-amber-500 text-amber-500"
                        : "border-transparent text-slate-400 hover:text-[#fafafa]"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content Display */}
              {activeSection && (
                <div className="space-y-6">
                  
                  {/* Warning notices if any */}
                  {activeSection.warnings && activeSection.warnings.length > 0 && (
                    <div className="p-4 bg-amber-500/5 border border-amber-500/20 rounded text-xs text-amber-300 space-y-1">
                      <div className="font-bold flex items-center gap-1.5">
                        <span>⚠️ Template Fallback Notice</span>
                      </div>
                      <ul className="list-disc pl-4 space-y-1 mt-1 font-mono text-[11px]">
                        {activeSection.warnings.map((w: string, idx: number) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Section Metadata Panel (Citations & Confidence) */}
                  <div className="grid grid-cols-2 gap-4 p-4 rounded border border-[#262626] bg-[#0c0c0c]/80 font-mono text-xs">
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider mb-1">Confidence Rating</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${
                        activeSection.confidence === "High"
                          ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
                          : activeSection.confidence === "Medium"
                          ? "border-amber-500/30 bg-amber-500/5 text-amber-400"
                          : "border-rose-500/30 bg-rose-500/5 text-rose-400"
                      }`}>
                        {activeSection.confidence}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider mb-1">Source Citations</span>
                      <span className="text-[#fafafa] font-semibold">
                        {activeSection.citations && activeSection.citations.length > 0
                          ? `${activeSection.citations.length} chunks mapped`
                          : "None (Generated by Rule fallback)"}
                      </span>
                    </div>
                  </div>

                  {/* Core Structured Payload */}
                  <div className="space-y-4">
                    <span className="text-[10px] uppercase font-mono text-slate-500 tracking-wider block">Generated Configuration Payload</span>
                    <pre className="p-4 rounded border border-[#262626] bg-[#090909] text-xs text-amber-500/90 font-mono overflow-auto max-h-[300px] leading-relaxed select-text">
                      {JSON.stringify(activeSection.content, null, 2)}
                    </pre>
                  </div>

                  {/* Citations List if present */}
                  {activeSection.citations && activeSection.citations.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] uppercase font-mono text-slate-500 tracking-wider block">Source Chunk ID Registers</span>
                      <div className="flex flex-wrap gap-1.5">
                        {activeSection.citations.map((c: string, idx: number) => (
                          <span key={idx} className="bg-[#1c1c1c] text-slate-400 border border-[#262626] rounded px-2 py-0.5 font-mono text-[9px]">
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                </div>
              )}

            </div>
          ) : (
            <div className="rounded border border-[#262626] bg-[#111111] p-12 text-center text-slate-500 italic text-xs font-mono">
              Select or generate a blueprint to start.
            </div>
          )}
        </div>

      </div>

      {/* Export Modal Display */}
      {showExportModal && exportData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl bg-[#111111] border border-[#262626] rounded-lg shadow-2xl p-6 space-y-4 animate-scale-in">
            <div className="flex justify-between items-center border-b border-[#262626] pb-3">
              <span className="text-xs font-bold text-[#fafafa] font-mono">Unity Runtime Config Export Payload</span>
              <button
                onClick={() => setShowExportModal(false)}
                className="text-slate-500 hover:text-[#fafafa] text-xs font-mono"
              >
                CLOSE
              </button>
            </div>
            
            <p className="text-[11px] text-slate-400 font-medium">
              Copy this flat JSON configuration schema to seed your Unity dialogue profiles, quest databases, and level variables.
            </p>

            <pre className="p-4 rounded border border-[#262626] bg-[#070707] text-xs text-emerald-400/90 font-mono overflow-auto max-h-[350px] leading-relaxed select-all">
              {JSON.stringify(exportData, null, 2)}
            </pre>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(exportData, null, 2));
                  alert("Copied to clipboard!");
                }}
                className="bg-amber-500 hover:bg-amber-600 text-black font-semibold px-4 py-2 rounded text-xs transition font-mono uppercase tracking-wider"
              >
                Copy to Clipboard
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
