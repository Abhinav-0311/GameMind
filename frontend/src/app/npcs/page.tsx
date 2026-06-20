"use client";

import React, { useState, useEffect } from "react";
import { api, NPCProfile, NPCProfileCreate, NPCProfileUpdate, DialogueAssembleResponse, DialogueChatResponse, QueryResult } from "@/lib/api";

export default function NPCStudioPage() {
  const [npcs, setNpcs] = useState<NPCProfile[]>([]);
  const [filteredNpcs, setFilteredNpcs] = useState<NPCProfile[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFaction, setSelectedFaction] = useState("all");

  // Loading, Submitting & Error States
  const [loadingList, setLoadingList] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form Drawer State
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit">("create");
  const [editingNpcId, setEditingNpcId] = useState<string | null>(null);

  // Form Fields
  const [formData, setFormData] = useState({
    slug: "",
    name: "",
    title: "",
    personality_summary: "",
    dialogue_style: "",
    voice_profile: "",
    faction_alignment: "",
    animation_hints_str: "",
    memory_settings_str: "",
    metadata_str: "",
  });

  // Validation Errors
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Delete Confirmation State
  const [deletingNpc, setDeletingNpc] = useState<NPCProfile | null>(null);

  // Dialogue Debugger State (Phase 8A)
  const [isDebugDrawerOpen, setIsDebugDrawerOpen] = useState(false);
  const [debugNpc, setDebugNpc] = useState<NPCProfile | null>(null);
  const [debugPlayerMessage, setDebugPlayerMessage] = useState("");
  const [debugSearchQuery, setDebugSearchQuery] = useState("");
  const [retrievedChunks, setRetrievedChunks] = useState<QueryResult[]>([]);
  const [selectedChunkIds, setSelectedChunkIds] = useState<string[]>([]);
  const [isRetrievingLore, setIsRetrievingLore] = useState(false);
  const [isAssemblingPrompt, setIsAssemblingPrompt] = useState(false);
  const [assembleError, setAssembleError] = useState<string | null>(null);
  const [assembleResponse, setAssembleResponse] = useState<DialogueAssembleResponse | null>(null);
  const [copied, setCopied] = useState(false);

  // Dialogue Chat States (Phase 8B)
  const [debugTab, setDebugTab] = useState<"assembler" | "chat">("assembler");
  const [chatHistory, setChatHistory] = useState<Array<{
    sender: "player" | "npc";
    text: string;
    timestamp: string;
    telemetry?: DialogueChatResponse["telemetry"];
    model_used?: string;
    llm_provider?: string;
    warnings?: string[];
  }>>([]);
  const [chatMessageInput, setChatMessageInput] = useState("");
  const [isChatSending, setIsChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [modelOverride, setModelOverride] = useState("");

  const fetchNPCs = async () => {
    setLoadingList(true);
    setGlobalError(null);
    try {
      const list = await api.getNPCs();
      setNpcs(list);
    } catch (err: unknown) {
      console.error(err);
      setGlobalError("Failed to fetch NPC profiles from the server.");
    } finally {
      setLoadingList(false);
    }
  };

  const filterNPCsList = () => {
    let list = [...npcs];

    // Search query filter (name or slug)
    if (searchQuery.trim() !== "") {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (npc) =>
          npc.name.toLowerCase().includes(q) ||
          npc.slug.toLowerCase().includes(q) ||
          (npc.title && npc.title.toLowerCase().includes(q))
      );
    }

    // Faction alignment filter
    if (selectedFaction !== "all") {
      list = list.filter((npc) => {
        if (selectedFaction === "none") {
          return !npc.faction_alignment || npc.faction_alignment.trim() === "";
        }
        return npc.faction_alignment === selectedFaction;
      });
    }

    setFilteredNpcs(list);
  };

  // Get unique list of factions present for filtering
  const getFactionsList = () => {
    const factions = new Set<string>();
    npcs.forEach((npc) => {
      if (npc.faction_alignment && npc.faction_alignment.trim() !== "") {
        factions.add(npc.faction_alignment.trim());
      }
    });
    return Array.from(factions);
  };

  // Reset Form State
  const resetForm = () => {
    setFormData({
      slug: "",
      name: "",
      title: "",
      personality_summary: "",
      dialogue_style: "",
      voice_profile: "",
      faction_alignment: "",
      animation_hints_str: "",
      memory_settings_str: "",
      metadata_str: "",
    });
    setValidationErrors({});
    setEditingNpcId(null);
    setGlobalError(null);
  };

  const openCreateDrawer = () => {
    resetForm();
    setDrawerMode("create");
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (npc: NPCProfile) => {
    resetForm();
    setDrawerMode("edit");
    setEditingNpcId(npc.id);
    setFormData({
      slug: npc.slug,
      name: npc.name,
      title: npc.title || "",
      personality_summary: npc.personality_summary,
      dialogue_style: npc.dialogue_style || "",
      voice_profile: npc.voice_profile || "",
      faction_alignment: npc.faction_alignment || "",
      animation_hints_str: npc.animation_hints ? JSON.stringify(npc.animation_hints, null, 2) : "",
      memory_settings_str: npc.memory_settings ? JSON.stringify(npc.memory_settings, null, 2) : "",
      metadata_str: npc.metadata ? JSON.stringify(npc.metadata, null, 2) : "",
    });
    setIsDrawerOpen(true);
  };

  // Dialogue Debugger Action (Phase 8A)
  const openDebuggerDrawer = (npc: NPCProfile) => {
    setDebugNpc(npc);
    setDebugPlayerMessage("");
    setDebugSearchQuery("");
    setRetrievedChunks([]);
    setSelectedChunkIds([]);
    setAssembleError(null);
    setAssembleResponse(null);
    setCopied(false);
    setDebugTab("assembler");
    setChatHistory([]);
    setChatMessageInput("");
    setIsChatSending(false);
    setChatError(null);
    setModelOverride("");
    setIsDebugDrawerOpen(true);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear validation error on change
    if (validationErrors[name]) {
      setValidationErrors((prev) => {
        const copy = { ...prev };
        delete copy[name];
        return copy;
      });
    }
  };

  // Run client-side form validation
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    // 1. Slug Validation (Create Mode Only)
    if (drawerMode === "create") {
      if (!formData.slug || formData.slug.trim() === "") {
        errors.slug = "Slug identifier is required.";
      } else if (formData.slug.length < 3 || formData.slug.length > 100) {
        errors.slug = "Slug must be between 3 and 100 characters.";
      } else if (!/^[a-z0-9_-]+$/.test(formData.slug)) {
        errors.slug = "Slug must contain only lowercase letters, numbers, underscores, or hyphens.";
      }
    }

    // 2. Name Validation
    if (!formData.name || formData.name.trim() === "") {
      errors.name = "Name is required.";
    } else if (formData.name.length > 100) {
      errors.name = "Name cannot exceed 100 characters.";
    }

    // 3. Title Validation
    if (formData.title && formData.title.length > 100) {
      errors.title = "Title cannot exceed 100 characters.";
    }

    // 4. Personality Summary Validation
    if (!formData.personality_summary || formData.personality_summary.trim() === "") {
      errors.personality_summary = "Personality summary is required.";
    }

    // 5. JSON parsing validations
    const validateJSONField = (fieldName: string, value: string) => {
      if (value && value.trim() !== "") {
        try {
          JSON.parse(value);
        } catch {
          errors[fieldName] = "Must be a valid JSON object. E.g. {\"key\": \"value\"}";
        }
      }
    };

    validateJSONField("animation_hints_str", formData.animation_hints_str);
    validateJSONField("memory_settings_str", formData.memory_settings_str);
    validateJSONField("metadata_str", formData.metadata_str);

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGlobalError(null);
    setSuccessMsg(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      const parseJSON = (str: string) => {
        if (!str || str.trim() === "") return undefined;
        return JSON.parse(str);
      };

      if (drawerMode === "create") {
        const payload: NPCProfileCreate = {
          slug: formData.slug.trim(),
          name: formData.name.trim(),
          title: formData.title.trim() || undefined,
          personality_summary: formData.personality_summary.trim(),
          dialogue_style: formData.dialogue_style.trim() || undefined,
          voice_profile: formData.voice_profile.trim() || undefined,
          faction_alignment: formData.faction_alignment.trim() || undefined,
          animation_hints: parseJSON(formData.animation_hints_str),
          memory_settings: parseJSON(formData.memory_settings_str),
          metadata: parseJSON(formData.metadata_str),
        };

        const created = await api.createNPC(payload);
        setSuccessMsg(`NPC "${created.name}" created successfully.`);
        setIsDrawerOpen(false);
        fetchNPCs();
      } else {
        // Edit Mode
        if (!editingNpcId) return;

        const payload: NPCProfileUpdate = {
          name: formData.name.trim(),
          title: formData.title.trim() || undefined,
          personality_summary: formData.personality_summary.trim(),
          dialogue_style: formData.dialogue_style.trim() || undefined,
          voice_profile: formData.voice_profile.trim() || undefined,
          faction_alignment: formData.faction_alignment.trim() || undefined,
          animation_hints: parseJSON(formData.animation_hints_str),
          memory_settings: parseJSON(formData.memory_settings_str),
          metadata: parseJSON(formData.metadata_str),
        };

        const updated = await api.updateNPC(editingNpcId, payload);
        setSuccessMsg(`NPC "${updated.name}" updated successfully.`);
        setIsDrawerOpen(false);
        fetchNPCs();
      }
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setGlobalError(errMsg || "An error occurred while saving the NPC profile.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = (npc: NPCProfile, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingNpc(npc);
  };

  const handleConfirmDelete = async () => {
    if (!deletingNpc) return;
    setGlobalError(null);
    setSuccessMsg(null);
    try {
      await api.deleteNPC(deletingNpc.id);
      setSuccessMsg(`NPC "${deletingNpc.name}" has been archived/soft-deleted.`);
      setDeletingNpc(null);
      fetchNPCs();
    } catch (err: unknown) {
      console.error(err);
      setGlobalError("Failed to delete the NPC profile.");
      setDeletingNpc(null);
    }
  };

  // Dialogue Debugger Action: Retrieve Lore via RAG (Phase 8A)
  const handleRetrieveLore = async () => {
    if (!debugSearchQuery.trim()) return;
    setIsRetrievingLore(true);
    setAssembleError(null);
    try {
      const results = await api.queryLore(debugSearchQuery, 8);
      setRetrievedChunks(results.results);
      // Auto select all retrieved chunks by default
      setSelectedChunkIds(results.results.map((c) => c.chunk_id));
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setAssembleError("RAG query failed: " + errMsg);
    } finally {
      setIsRetrievingLore(false);
    }
  };

  // Toggle checklist chunk IDs
  const handleToggleChunk = (chunkId: string) => {
    setSelectedChunkIds((prev) =>
      prev.includes(chunkId) ? prev.filter((id) => id !== chunkId) : [...prev, chunkId]
    );
  };

  // Dialogue Debugger Action: Assemble Prompt (Phase 8A)
  const handleAssemblePrompt = async () => {
    if (!debugNpc) return;
    setIsAssemblingPrompt(true);
    setAssembleError(null);
    setAssembleResponse(null);
    setCopied(false);
    try {
      const response = await api.assembleDialogue({
        npc_slug: debugNpc.slug,
        player_message: debugPlayerMessage,
        selected_chunk_ids: selectedChunkIds,
      });
      setAssembleResponse(response);
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setAssembleError(errMsg || "Failed to assemble dialogue prompt.");
    } finally {
      setIsAssemblingPrompt(false);
    }
  };

  const copyPromptToClipboard = () => {
    if (assembleResponse?.assembled_prompt) {
      navigator.clipboard.writeText(assembleResponse.assembled_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Dialogue Debugger Action: Send Chat Message (Phase 8B)
  const handleSendChatMessage = async () => {
    if (!chatMessageInput.trim() || !debugNpc) return;

    const userMsgText = chatMessageInput.trim();
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const newUserMessage = {
      sender: "player" as const,
      text: userMsgText,
      timestamp
    };

    setChatHistory((prev) => [...prev, newUserMessage]);
    setChatMessageInput("");
    setIsChatSending(true);
    setChatError(null);

    try {
      const response = await api.chatDialogue({
        npc_slug: debugNpc.slug,
        player_message: userMsgText,
        selected_chunk_ids: selectedChunkIds,
        model_override: modelOverride || undefined,
        prompt_version: "v1"
      });

      const newNpcMessage = {
        sender: "npc" as const,
        text: response.response_text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        telemetry: response.telemetry,
        model_used: response.model_used,
        llm_provider: response.llm_provider,
        warnings: response.warnings
      };

      setChatHistory((prev) => [...prev, newNpcMessage]);
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      setChatError(errMsg || "Failed to execute dialogue chat.");
    } finally {
      setIsChatSending(false);
    }
  };

  const handleClearChatHistory = () => {
    setChatHistory([]);
    setChatError(null);
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchNPCs();
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    filterNPCsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [npcs, searchQuery, selectedFaction]);

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#262626] pb-4 gap-4 select-none">
        <div className="space-y-1">
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">NPC Studio</h2>
          <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
            Manage static character profiles, personalities, and behavior guidelines. Soft-deleted NPCs are excluded from active list.
          </p>
        </div>
        <div>
          <button
            onClick={openCreateDrawer}
            className="bg-[#b9ff66] text-[#0a0a0a] hover:opacity-90 active:opacity-95 px-3.5 py-1.5 rounded text-xs font-bold font-sans transition shadow-sm flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
            </svg>
            Create NPC
          </button>
        </div>
      </div>

      {/* Global Alerts */}
      {globalError && (
        <div className="p-3.5 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs flex gap-2.5 items-center font-sans font-medium">
          <svg className="w-4 h-4 flex-shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{globalError}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 text-xs flex gap-2.5 items-center font-sans font-medium">
          <svg className="w-4 h-4 flex-shrink-0 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{successMsg}</span>
        </div>
      )}

      {/* Live Search and Filter Bar */}
      <div className="flex flex-col md:flex-row gap-3 bg-[#111111]/30 p-3 rounded border border-[#262626] items-center">
        {/* Search Input */}
        <div className="relative flex-1 w-full">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none select-none text-slate-500">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            type="text"
            placeholder="Filter by name, title, or slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#0a0a0a] text-xs text-[#fafafa] placeholder-slate-500 pl-8.5 pr-3 py-1.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition font-sans"
          />
        </div>

        {/* Faction Filter Dropdown */}
        <div className="w-full md:w-56 flex items-center gap-2">
          <span className="text-[10px] font-mono text-[#a1a1aa] whitespace-nowrap uppercase font-bold select-none">
            Faction:
          </span>
          <select
            value={selectedFaction}
            onChange={(e) => setSelectedFaction(e.target.value)}
            className="w-full bg-[#0a0a0a] text-xs text-[#fafafa] py-1.5 px-3 rounded border border-[#262626] focus:border-[#fafafa] outline-none cursor-pointer transition font-sans"
          >
            <option value="all">All Factions</option>
            <option value="none">No Faction</option>
            {getFactionsList().map((fac) => (
              <option key={fac} value={fac}>
                {fac}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh count */}
        <div className="flex items-center gap-3 select-none">
          <span className="text-[10px] font-mono text-slate-500 uppercase block font-semibold whitespace-nowrap">
            {filteredNpcs.length} OF {npcs.length} NPCs
          </span>
          <button
            onClick={fetchNPCs}
            className="text-xs font-mono text-[#a1a1aa] hover:text-[#fafafa] flex items-center gap-1 transition"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89H18" />
            </svg>
          </button>
        </div>
      </div>

      {/* NPC List Table (Vercel Style) */}
      <div className="border border-[#262626] rounded bg-[#111111]/10 overflow-hidden">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider select-none">
              <th className="py-2 px-4 font-bold">NPC Name</th>
              <th className="py-2 px-4 font-bold">Slug / Identity</th>
              <th className="py-2 px-4 font-bold">Title / Rank</th>
              <th className="py-2 px-4 font-bold">Faction Alignment</th>
              <th className="py-2 px-4 font-bold">Last Updated</th>
              <th className="py-2 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#262626]/80 font-sans">
            {loadingList ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 font-mono text-xs select-none">
                  RETRIEVING NPC REGISTRY...
                </td>
              </tr>
            ) : filteredNpcs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center bg-[#111111]/5">
                  <div className="h-8 w-8 rounded bg-[#171717] border border-[#262626] text-slate-500 flex items-center justify-center mx-auto mb-3.5 select-none">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <h4 className="font-semibold text-slate-300 text-xs">No NPCs Found</h4>
                  <p className="text-[10px] text-slate-500 mt-1 max-w-xs mx-auto leading-normal">
                    {npcs.length === 0 ? "Create a new NPC profile to populate the registry." : "Try adjusting your filters or search keywords."}
                  </p>
                </td>
              </tr>
            ) : (
              filteredNpcs.map((npc) => (
                <tr
                  key={npc.id}
                  onClick={() => openEditDrawer(npc)}
                  className="cursor-pointer hover:bg-[#111111]/30 transition duration-150"
                >
                  <td className="py-2.5 px-4 font-semibold text-[#fafafa]">
                    {npc.name}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] truncate max-w-[150px]">
                    {npc.slug}
                  </td>
                  <td className="py-2.5 px-4 text-[#fafafa] italic">
                    {npc.title || <span className="text-slate-600 font-mono text-[10px]">n/a</span>}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px]">
                    {npc.faction_alignment || <span className="text-slate-600 font-mono">UNALIGNED</span>}
                  </td>
                  <td className="py-2.5 px-4 text-[#a1a1aa] font-mono text-[11px]">
                    {new Date(npc.updated_at).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-3.5">
                      <button
                        onClick={() => openDebuggerDrawer(npc)}
                        className="text-[#b9ff66] hover:opacity-80 transition text-[11px] font-mono tracking-wider uppercase font-semibold"
                      >
                        Debug
                      </button>
                      <button
                        onClick={() => openEditDrawer(npc)}
                        className="text-[#a1a1aa] hover:text-[#fafafa] transition text-[11px] font-mono tracking-wider uppercase font-semibold"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => handleDeleteClick(npc, e)}
                        className="text-slate-600 hover:text-rose-450 transition text-[11px] font-mono tracking-wider uppercase font-semibold"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Stripe-style Sidebar Drawer Form for NPC Create/Edit */}
      {isDrawerOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 z-30 transition-opacity backdrop-blur-[0.5px]"
            onClick={() => setIsDrawerOpen(false)}
          />

          {/* Drawer Container */}
          <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-[#171717] border-l border-[#262626] shadow-2xl z-40 flex flex-col justify-between overflow-hidden">
            {/* Drawer Header */}
            <div className="px-6 py-4 border-b border-[#262626] flex items-center justify-between bg-[#111111] select-none">
              <div>
                <h3 className="text-sm font-bold text-[#fafafa] uppercase tracking-wide">
                  {drawerMode === "create" ? "Configure NPC Profile" : "Edit NPC Profile"}
                </h3>
                <span className="text-[9px] font-mono text-slate-500 uppercase mt-0.5 block">
                  {drawerMode === "create" ? "Draft character settings" : `ID: ${editingNpcId}`}
                </span>
              </div>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="text-[#a1a1aa] hover:text-[#fafafa] transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Scrollable Form Body */}
            <form onSubmit={handleFormSubmit} className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
              {/* Form validation alert at top of drawer if needed */}
              {Object.keys(validationErrors).length > 0 && (
                <div className="p-3 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs font-sans font-medium">
                  Please fix the highlighted errors before saving.
                </div>
              )}

              {/* Slug (Only Editable in Create Mode) */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Unique Slug Identifier {drawerMode === "create" && <span className="text-[#b9ff66]">*</span>}
                </label>
                <input
                  type="text"
                  name="slug"
                  disabled={drawerMode === "edit"}
                  value={formData.slug}
                  onChange={handleInputChange}
                  placeholder="e.g. eldrin_mage"
                  className={`w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border ${
                    validationErrors.slug ? "border-rose-500" : "border-[#262626]"
                  } focus:border-[#fafafa] outline-none transition disabled:opacity-40 disabled:cursor-not-allowed`}
                />
                {validationErrors.slug ? (
                  <p className="text-[10px] text-rose-450 font-sans mt-1">{validationErrors.slug}</p>
                ) : (
                  <p className="text-[9px] text-slate-500 font-sans leading-normal">
                    This forms the URL identity. Lowercase alphanumeric letters, hyphens, and underscores only. Max 100 characters.
                  </p>
                )}
              </div>

              {/* Name & Title row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Name */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                    Display Name <span className="text-[#b9ff66]">*</span>
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    placeholder="e.g. Eldrin"
                    className={`w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2.5 rounded border ${
                      validationErrors.name ? "border-rose-500" : "border-[#262626]"
                    } focus:border-[#fafafa] outline-none transition font-sans`}
                  />
                  {validationErrors.name && (
                    <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.name}</p>
                  )}
                </div>

                {/* Title */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                    Title / Rank
                  </label>
                  <input
                    type="text"
                    name="title"
                    value={formData.title}
                    onChange={handleInputChange}
                    placeholder="e.g. Archmage of the Tower"
                    className={`w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2.5 rounded border ${
                      validationErrors.title ? "border-rose-500" : "border-[#262626]"
                    } focus:border-[#fafafa] outline-none transition font-sans`}
                  />
                  {validationErrors.title && (
                    <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.title}</p>
                  )}
                </div>
              </div>

              {/* Faction Alignment & Voice Profile row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Faction */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                    Faction Alignment
                  </label>
                  <input
                    type="text"
                    name="faction_alignment"
                    value={formData.faction_alignment}
                    onChange={handleInputChange}
                    placeholder="e.g. cinder_vanguard"
                    className="w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition"
                  />
                </div>

                {/* Voice Profile */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                    Voice Profile Identifier
                  </label>
                  <input
                    type="text"
                    name="voice_profile"
                    value={formData.voice_profile}
                    onChange={handleInputChange}
                    placeholder="e.g. elderly-gravelly-english"
                    className="w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition"
                  />
                </div>
              </div>

              {/* Personality Summary */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Personality Summary <span className="text-[#b9ff66]">*</span>
                </label>
                <textarea
                  name="personality_summary"
                  value={formData.personality_summary}
                  onChange={handleInputChange}
                  rows={4}
                  placeholder="Describe the character's background, personality, fears, and behaviors..."
                  className={`w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2.5 rounded border ${
                    validationErrors.personality_summary ? "border-rose-500" : "border-[#262626]"
                  } focus:border-[#fafafa] outline-none transition font-sans resize-y`}
                />
                {validationErrors.personality_summary && (
                  <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.personality_summary}</p>
                )}
              </div>

              {/* Dialogue Style */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Dialogue Style & Guidelines
                  <span className="text-[9px] text-slate-500 lowercase font-medium ml-2">optional</span>
                </label>
                <textarea
                  name="dialogue_style"
                  value={formData.dialogue_style}
                  onChange={handleInputChange}
                  rows={3}
                  placeholder="e.g. Speaks in long sentences, avoids contractions, uses archaic spell names..."
                  className="w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition font-sans resize-y"
                />
              </div>

              {/* Animation Hints JSON */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Animation Hints (JSON Object)
                  <span className="text-[9px] text-slate-500 lowercase font-medium ml-2">optional</span>
                </label>
                <textarea
                  name="animation_hints_str"
                  value={formData.animation_hints_str}
                  onChange={handleInputChange}
                  rows={3}
                  placeholder='e.g. { "neutral": "idle_read", "talking": "gesture_point" }'
                  className={`w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border ${
                    validationErrors.animation_hints_str ? "border-rose-500" : "border-[#262626]"
                  } focus:border-[#fafafa] outline-none transition resize-y`}
                />
                {validationErrors.animation_hints_str && (
                  <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.animation_hints_str}</p>
                )}
              </div>

              {/* Memory Settings JSON */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Memory Retrieval Settings (JSON Object)
                  <span className="text-[9px] text-slate-500 lowercase font-medium ml-2">optional</span>
                </label>
                <textarea
                  name="memory_settings_str"
                  value={formData.memory_settings_str}
                  onChange={handleInputChange}
                  rows={2}
                  placeholder='e.g. { "search_threshold": 0.65, "max_memories_retrieved": 3 }'
                  className={`w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border ${
                    validationErrors.memory_settings_str ? "border-rose-500" : "border-[#262626]"
                  } focus:border-[#fafafa] outline-none transition resize-y`}
                />
                {validationErrors.memory_settings_str && (
                  <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.memory_settings_str}</p>
                )}
              </div>

              {/* Metadata JSON */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                  Additional Metadata (JSON Object)
                  <span className="text-[9px] text-slate-500 lowercase font-medium ml-2">optional</span>
                </label>
                <textarea
                  name="metadata_str"
                  value={formData.metadata_str}
                  onChange={handleInputChange}
                  rows={2}
                  placeholder='e.g. { "created_by_user": "designer_01", "game_zone": "north_watch" }'
                  className={`w-full bg-[#0a0a0a] text-xs font-mono text-[#fafafa] p-2.5 rounded border ${
                    validationErrors.metadata_str ? "border-rose-500" : "border-[#262626]"
                  } focus:border-[#fafafa] outline-none transition resize-y`}
                />
                {validationErrors.metadata_str && (
                  <p className="text-[10px] text-rose-455 font-sans mt-1">{validationErrors.metadata_str}</p>
                )}
              </div>
            </form>

            {/* Drawer Footer Actions */}
            <div className="px-6 py-4 border-t border-[#262626] bg-[#111111] flex items-center justify-end gap-3 select-none">
              <button
                type="button"
                onClick={() => setIsDrawerOpen(false)}
                className="bg-transparent border border-[#262626] hover:bg-[#171717] text-[#a1a1aa] hover:text-[#fafafa] px-3.5 py-1.5 rounded text-xs font-bold font-sans transition"
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                onClick={handleFormSubmit}
                className="bg-[#b9ff66] text-[#0a0a0a] hover:opacity-90 active:opacity-95 px-3.5 py-1.5 rounded text-xs font-bold font-sans transition disabled:opacity-50"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Saving NPC..." : "Save Profile"}
              </button>
            </div>
          </div>
        </>
      )}

      {/* Monochrome Soft-Delete Archive Confirmation Dialog */}
      {deletingNpc && (
        <div className="fixed inset-0 z-50 bg-[#000000]/80 flex items-center justify-center p-4 backdrop-blur-[0.5px]">
          <div className="w-full max-w-md bg-[#171717] border border-[#262626] rounded-lg shadow-2xl p-6 space-y-5">
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-[#fafafa] uppercase tracking-wider font-mono">
                Confirm NPC Soft-Delete
              </h3>
              <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed font-sans">
                Are you sure you want to archive <span className="text-[#fafafa] font-bold">&quot;{deletingNpc.name}&quot;</span>?
              </p>
            </div>

            <div className="p-3 bg-[#0a0a0a] border border-[#262626] rounded text-[11px] font-sans text-rose-450/90 leading-relaxed font-medium">
              This action soft-deletes the NPC profile. While the record remains in the database (with a deleted_at timestamp), it will be excluded from game dialogue queries, search systems, and active profiles lists.
            </div>

            <div className="flex justify-end gap-3.5 font-sans">
              <button
                onClick={() => setDeletingNpc(null)}
                className="bg-transparent border border-[#262626] hover:bg-[#111111]/80 text-[#a1a1aa] hover:text-[#fafafa] px-3 py-1.5 rounded text-xs font-bold transition"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                className="bg-rose-600/90 hover:bg-rose-600 text-[#fafafa] px-3 py-1.5 rounded text-xs font-bold transition"
              >
                Soft-Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dialogue Debugger Side Drawer Console (Phase 8A) */}
      {isDebugDrawerOpen && debugNpc && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 z-30 transition-opacity backdrop-blur-[0.5px]"
            onClick={() => setIsDebugDrawerOpen(false)}
          />

          {/* Large Split-Pane Debugger Drawer */}
          <div className="fixed inset-y-0 right-0 w-full max-w-5xl bg-[#171717] border-l border-[#262626] shadow-2xl z-40 flex flex-col justify-between overflow-hidden font-sans">
            {/* Header */}
            <div className="px-6 py-4 border-b border-[#262626] flex items-center justify-between bg-[#111111] select-none">
              <div>
                <h3 className="text-xs font-bold text-[#b9ff66] uppercase tracking-wider font-mono">
                  Dialogue Assembly Debugger
                </h3>
                <span className="text-[9px] font-mono text-slate-500 uppercase mt-0.5 block">
                  Simulating Prompt Assembly for NPC: {debugNpc.name} ({debugNpc.slug})
                </span>
              </div>
              <button
                onClick={() => setIsDebugDrawerOpen(false)}
                className="text-[#a1a1aa] hover:text-[#fafafa] transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tabs Bar */}
            <div className="px-6 bg-[#121212] border-b border-[#262626] flex gap-4 select-none">
              <button
                type="button"
                onClick={() => setDebugTab("assembler")}
                className={`py-3 text-xs font-semibold font-mono tracking-wide transition relative border-b-2 ${
                  debugTab === "assembler"
                    ? "text-[#b9ff66] border-[#b9ff66]"
                    : "text-slate-400 border-transparent hover:text-slate-200"
                }`}
              >
                PROMPT ASSEMBLER
              </button>
              <button
                type="button"
                onClick={() => setDebugTab("chat")}
                className={`py-3 text-xs font-semibold font-mono tracking-wide transition relative border-b-2 ${
                  debugTab === "chat"
                    ? "text-[#b9ff66] border-[#b9ff66]"
                    : "text-slate-400 border-transparent hover:text-slate-200"
                }`}
              >
                CHAT SIMULATOR (GEMINI Integration)
              </button>
            </div>

            {/* Split Pane Drawer Body */}
            <div className="flex-1 flex overflow-hidden">
              {debugTab === "assembler" ? (
                <>
                  {/* Left Column: Inputs & RAG retrieval */}
                  <div className="w-1/2 border-r border-[#262626] p-6 overflow-y-auto space-y-5 flex flex-col justify-between">
                <div className="space-y-5">
                  {/* NPC Mini Profile */}
                  <div className="p-3 bg-[#0a0a0a] border border-[#262626] rounded text-[11px] space-y-1.5">
                    <span className="font-mono text-slate-500 uppercase font-bold block select-none">
                      Selected Persona Context
                    </span>
                    <div>
                      <span className="text-[#fafafa] font-bold">{debugNpc.name}</span>
                      {debugNpc.title && <span className="text-[#a1a1aa] italic ml-1">({debugNpc.title})</span>}
                    </div>
                    <p className="text-[#a1a1aa] text-[10px] leading-relaxed truncate max-w-md">
                      {debugNpc.personality_summary}
                    </p>
                  </div>

                  {/* Player Message Input */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                      Player Message Simulation
                    </label>
                    <textarea
                      value={debugPlayerMessage}
                      onChange={(e) => setDebugPlayerMessage(e.target.value)}
                      rows={3}
                      placeholder="Type simulated player dialogue here..."
                      className="w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition font-sans resize-y"
                    />
                    <div className="flex justify-between items-center text-[9px] text-slate-500 font-mono">
                      <span>Max limit: 4000 characters</span>
                      <span className={debugPlayerMessage.length > 4000 ? "text-rose-400 font-bold" : ""}>
                        {debugPlayerMessage.length} chars
                      </span>
                    </div>
                  </div>

                  {/* RAG Search Block */}
                  <div className="space-y-3 pt-2">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                        Lore Retrieval (Vector Search)
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={debugSearchQuery}
                          onChange={(e) => setDebugSearchQuery(e.target.value)}
                          placeholder="Search lore keywords (e.g. Ember Siege)..."
                          className="flex-1 bg-[#0a0a0a] text-xs text-[#fafafa] px-3 py-1.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition"
                          onKeyDown={(e) => e.key === "Enter" && handleRetrieveLore()}
                        />
                        <button
                          type="button"
                          onClick={handleRetrieveLore}
                          disabled={isRetrievingLore || !debugSearchQuery.trim()}
                          className="bg-[#262626] hover:bg-[#333] border border-[#333] hover:border-slate-700 text-[#fafafa] text-xs px-3.5 rounded transition disabled:opacity-40 disabled:cursor-not-allowed select-none font-semibold"
                        >
                          {isRetrievingLore ? "Retrieving..." : "Query RAG"}
                        </button>
                      </div>
                    </div>

                    {/* Chunks Checklist */}
                    <div className="space-y-2">
                      <span className="text-[10px] font-mono text-slate-500 uppercase block font-semibold select-none">
                        Retrieved Lore Chunks ({retrievedChunks.length} found)
                      </span>
                      
                      {retrievedChunks.length === 0 ? (
                        <div className="py-8 text-center text-slate-600 text-[11px] border border-[#262626] border-dashed rounded font-mono select-none">
                          NO LORE RETRIEVED YET
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-[190px] overflow-y-auto pr-1 border border-[#262626] rounded bg-[#0a0a0a]/50 p-2.5">
                          {retrievedChunks.map((chunk) => {
                            const isChecked = selectedChunkIds.includes(chunk.chunk_id);
                            return (
                              <div
                                key={chunk.chunk_id}
                                onClick={() => handleToggleChunk(chunk.chunk_id)}
                                className={`flex items-start gap-2.5 p-2 rounded border cursor-pointer transition select-none ${
                                  isChecked
                                    ? "bg-[#171717] border-slate-700"
                                    : "bg-transparent border-[#262626]/60 hover:bg-[#111]/30"
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {}} // handled by parent onClick
                                  className="mt-0.5 pointer-events-none accent-[#b9ff66]"
                                />
                                <div className="space-y-1 flex-1">
                                  <div className="flex items-center justify-between text-[9px] font-mono text-slate-500">
                                    <span className="truncate max-w-[150px] font-bold">
                                      {chunk.title} (#{chunk.chunk_index + 1})
                                    </span>
                                    <span>
                                      SIM: {(chunk.similarity * 100).toFixed(0)}% ({chunk.confidence})
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-[#a1a1aa] leading-relaxed font-sans line-clamp-2">
                                    {chunk.content}
                                  </p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Assemble prompt trigger at bottom left */}
                <div className="pt-4 border-t border-[#262626] flex items-center justify-between select-none">
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-semibold">
                    {selectedChunkIds.length} CHUNKS SELECTED
                  </span>
                  <button
                    type="button"
                    onClick={handleAssemblePrompt}
                    disabled={isAssemblingPrompt || !debugPlayerMessage.trim()}
                    className="bg-[#b9ff66] text-[#0a0a0a] hover:opacity-90 active:opacity-95 px-5 py-2 rounded text-xs font-bold font-sans transition disabled:opacity-45 shadow-sm"
                  >
                    {isAssemblingPrompt ? "Formatting..." : "Assemble Prompt"}
                  </button>
                </div>
              </div>

              {/* Right Column: Output & Telemetry */}
              <div className="w-1/2 bg-[#0d0d0d] p-6 overflow-y-auto flex flex-col justify-between">
                <div className="space-y-5 h-full flex flex-col justify-between">
                  <div className="space-y-4 flex-1 flex flex-col min-h-0">
                    <div className="flex items-center justify-between border-b border-[#262626] pb-3 select-none">
                      <span className="text-xs font-semibold text-[#fafafa]">Assembled Prompt Output</span>
                      {assembleResponse && (
                        <span className="text-[9px] font-mono text-slate-500 uppercase">
                          VERSION: {assembleResponse.prompt_version}
                        </span>
                      )}
                    </div>

                    {assembleError && (
                      <div className="p-3 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs flex gap-2 font-sans font-medium">
                        <svg className="w-3.5 h-3.5 flex-shrink-0 text-rose-450" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <span>{assembleError}</span>
                      </div>
                    )}

                    {assembleResponse && assembleResponse.warnings.length > 0 && (
                      <div className="p-3 rounded border border-amber-500/20 bg-amber-500/10 text-amber-400 text-xs space-y-1 font-sans">
                        <span className="font-bold block select-none">Assembly Warning(s):</span>
                        <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                          {assembleResponse.warnings.map((w, idx) => (
                            <li key={idx}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {!assembleResponse ? (
                      <div className="flex-1 flex items-center justify-center text-center p-6 border border-[#262626] border-dashed rounded bg-[#0a0a0a]/20 select-none">
                        <div className="space-y-1">
                          <p className="text-slate-500 text-xs font-sans">
                            Enter player query and selection chunks on the left.
                          </p>
                          <p className="text-[10px] text-slate-600 font-mono uppercase">
                            Then click &quot;Assemble Prompt&quot;
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col min-h-0 space-y-4 mt-2">
                        {/* Monospace telemetry */}
                        <div className="grid grid-cols-3 gap-2 text-[10px] font-mono select-none">
                          <div className="bg-[#111] border border-[#262626] p-2 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">EST. TOKENS</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5">{assembleResponse.estimated_tokens}</span>
                          </div>
                          <div className="bg-[#111] border border-[#262626] p-2 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">CHARS LENGTH</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5">{assembleResponse.character_count}</span>
                          </div>
                          <div className="bg-[#111] border border-[#262626] p-2 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">LORE CHUNKS</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5">{assembleResponse.retrieved_chunk_count}</span>
                          </div>
                        </div>

                        {/* Copyable prompt block */}
                        <div className="flex-1 flex flex-col min-h-0 relative">
                          <button
                            onClick={copyPromptToClipboard}
                            className="absolute right-3.5 top-3.5 bg-[#262626] hover:bg-[#333] border border-slate-800 text-[#a1a1aa] hover:text-[#fafafa] text-[10px] font-mono px-2 py-1 rounded transition select-none"
                          >
                            {copied ? "COPIED" : "COPY PROMPT"}
                          </button>
                          <pre className="flex-1 bg-[#0a0a0a] border border-[#262626] text-[11px] font-mono p-4 rounded overflow-auto select-all h-[260px] whitespace-pre-wrap leading-relaxed text-[#fafafa] pr-28">
                            {assembleResponse.assembled_prompt}
                          </pre>
                        </div>

                        {/* Collapsible Details */}
                        <div className="space-y-2 border-t border-[#262626]/80 pt-3 max-h-[140px] overflow-y-auto pr-1">
                          <details className="text-[11px] group">
                            <summary className="font-mono text-slate-500 hover:text-slate-300 cursor-pointer font-bold select-none uppercase outline-none list-none flex items-center justify-between">
                              <span>► SYSTEM PROMPT DIRECTIVES</span>
                              <span className="text-[9px] font-normal text-slate-600 group-open:hidden">expand</span>
                            </summary>
                            <pre className="mt-2 p-2 rounded bg-[#0a0a0a] border border-[#262626] font-mono text-[10px] text-[#a1a1aa] whitespace-pre-wrap select-all">
                              {assembleResponse.system_prompt}
                            </pre>
                          </details>
                          <details className="text-[11px] group">
                            <summary className="font-mono text-slate-500 hover:text-slate-300 cursor-pointer font-bold select-none uppercase outline-none list-none flex items-center justify-between">
                              <span>► NPC ATTRIBUTE VARIABLES</span>
                              <span className="text-[9px] font-normal text-slate-600 group-open:hidden">expand</span>
                            </summary>
                            <pre className="mt-2 p-2 rounded bg-[#0a0a0a] border border-[#262626] font-mono text-[10px] text-[#a1a1aa] whitespace-pre-wrap select-all">
                              {assembleResponse.npc_context}
                            </pre>
                          </details>
                          <details className="text-[11px] group">
                            <summary className="font-mono text-slate-500 hover:text-slate-300 cursor-pointer font-bold select-none uppercase outline-none list-none flex items-center justify-between">
                              <span>► RETRIEVED LORE METADATA</span>
                              <span className="text-[9px] font-normal text-slate-600 group-open:hidden">expand</span>
                            </summary>
                            <div className="mt-2 p-2.5 rounded bg-[#0a0a0a] border border-[#262626] space-y-2">
                              {assembleResponse.retrieved_chunks.length === 0 ? (
                                <span className="text-[10px] font-mono text-slate-600 uppercase select-none block">
                                  No chunks mapped
                                </span>
                              ) : (
                                assembleResponse.retrieved_chunks.map((meta) => (
                                  <div key={meta.id} className="text-[10px] font-mono text-[#a1a1aa] flex justify-between border-b border-[#262626]/40 pb-1.5">
                                    <span>ID: {meta.id.substring(0, 8)}... (Chunk #{meta.chunk_index + 1})</span>
                                    <span>Size: {meta.character_count} chars</span>
                                  </div>
                                ))
                              )}
                            </div>
                          </details>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Left Column: Chat Feed */}
              <div className="w-1/2 border-r border-[#262626] bg-[#121212] p-6 flex flex-col justify-between overflow-hidden h-full">
                {/* Chat Feed Header */}
                <div className="flex items-center justify-between border-b border-[#262626] pb-3 mb-4 select-none">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#b9ff66] animate-pulse"></span>
                    <span className="text-xs font-semibold text-[#fafafa] uppercase font-mono tracking-wider">Dialogue Session Active</span>
                  </div>
                  {chatHistory.length > 0 && (
                    <button
                      type="button"
                      onClick={handleClearChatHistory}
                      className="text-[9px] font-mono text-slate-500 hover:text-rose-400 uppercase tracking-tight transition"
                    >
                      Clear Session
                    </button>
                  )}
                </div>

                {/* Chat Feed Body (Scrollable Messages) */}
                <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4 flex flex-col min-h-0">
                  {chatHistory.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-center p-6 border border-[#262626] border-dashed rounded bg-[#0a0a0a]/20 select-none">
                      <div className="space-y-2 max-w-sm">
                        <p className="text-slate-500 text-xs font-sans">
                          Interactive simulation session with <strong className="text-[#fafafa]">{debugNpc.name}</strong>.
                        </p>
                        <p className="text-[10px] text-[#a1a1aa] leading-relaxed">
                          Select some World Lore Chunks on the right to ground the character, then type a message below to start chatting.
                        </p>
                      </div>
                    </div>
                  ) : (
                    chatHistory.map((msg, idx) => (
                      <div key={idx} className={`flex flex-col ${msg.sender === "player" ? "items-end" : "items-start"}`}>
                        {/* Message Header */}
                        <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-500 mb-1 select-none">
                          {msg.sender === "player" ? (
                            <>
                              <span>{msg.timestamp}</span>
                              <span className="font-bold text-slate-400">PLAYER</span>
                            </>
                          ) : (
                            <>
                              <span className="font-bold text-[#b9ff66]">{debugNpc.name.toUpperCase()}</span>
                              <span>{msg.timestamp}</span>
                            </>
                          )}
                        </div>

                        {/* Message Bubble */}
                        <div className={`max-w-[85%] rounded p-3 text-xs leading-relaxed font-sans ${
                          msg.sender === "player"
                            ? "bg-[#262626] text-[#fafafa] border border-slate-700/30"
                            : "bg-[#0d0d0d] text-[#fafafa] border border-slate-800"
                        }`}>
                          {msg.sender === "npc" && (
                            <div className="text-[9px] font-mono text-[#b9ff66] mb-1.5 select-none uppercase tracking-wide">
                              [{debugNpc.name} of {debugNpc.faction_alignment || "UNALIGNED"}]
                            </div>
                          )}
                          <p className="whitespace-pre-wrap select-text">{msg.text}</p>

                          {/* Telemetry info block for NPC response */}
                          {msg.sender === "npc" && msg.telemetry && (
                            <div className="mt-2.5 pt-2 border-t border-[#262626] flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[8.5px] font-mono text-slate-500 uppercase select-none">
                              <span>PROVIDER: {msg.llm_provider || "mock"}</span>
                              <span>•</span>
                              <span>LATENCY: {msg.telemetry.latency_ms}ms</span>
                              <span>•</span>
                              <span>TOKENS: {msg.telemetry.input_tokens}/{msg.telemetry.output_tokens}</span>
                              <span>•</span>
                              <span>COST: ${msg.telemetry.estimated_cost_usd.toFixed(6)}</span>
                              {msg.telemetry.safety_blocked && (
                                <>
                                  <span>•</span>
                                  <span className="text-rose-400 font-bold">SAFETY BLOCKED</span>
                                </>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Warnings Display */}
                        {msg.sender === "npc" && msg.warnings && msg.warnings.length > 0 && (
                          <div className="mt-1 text-[8.5px] font-mono text-amber-500/80 max-w-[85%] select-none">
                            ⚠️ {msg.warnings.join(" | ")}
                          </div>
                        )}
                      </div>
                    ))
                  )}

                  {/* Chat Sending Spinner */}
                  {isChatSending && (
                    <div className="flex flex-col items-start">
                      <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-500 mb-1 select-none">
                        <span className="font-bold text-[#b9ff66]">{debugNpc.name.toUpperCase()}</span>
                        <span>thinking...</span>
                      </div>
                      <div className="bg-[#0d0d0d] border border-slate-800 rounded p-3 max-w-[85%] flex items-center gap-2 text-xs text-slate-500 select-none">
                        <svg className="animate-spin h-3.5 w-3.5 text-[#b9ff66]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Generating response...</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Chat Input controls */}
                <div className="space-y-2 pt-2 border-t border-[#262626]">
                  {chatError && (
                    <div className="p-2.5 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs flex gap-2 font-sans font-medium">
                      <svg className="w-3.5 h-3.5 flex-shrink-0 text-rose-450" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <span className="break-all">{chatError}</span>
                    </div>
                  )}
                  
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={chatMessageInput}
                      onChange={(e) => setChatMessageInput(e.target.value)}
                      placeholder={`Ask ${debugNpc.name} something...`}
                      className="flex-1 bg-[#0a0a0a] text-xs text-[#fafafa] px-3.5 py-2.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition font-sans"
                      onKeyDown={(e) => e.key === "Enter" && !isChatSending && handleSendChatMessage()}
                      disabled={isChatSending}
                    />
                    <button
                      type="button"
                      onClick={handleSendChatMessage}
                      disabled={isChatSending || !chatMessageInput.trim()}
                      className="bg-[#b9ff66] text-[#0a0a0a] hover:opacity-90 active:opacity-95 px-5 py-2.5 rounded text-xs font-bold font-sans transition disabled:opacity-45 disabled:cursor-not-allowed shadow-sm select-none"
                    >
                      Send
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Grounding Context & Live Telemetry */}
              <div className="w-1/2 bg-[#0d0d0d] p-6 overflow-y-auto space-y-5 flex flex-col min-h-0 justify-between h-full">
                <div className="space-y-5 flex-1 min-h-0 flex flex-col justify-between">
                  <div className="space-y-5 flex-1 flex flex-col min-h-0">
                    {/* Section 1: LLM Configuration */}
                    <div className="bg-[#111] border border-[#262626] p-4 rounded space-y-3 select-none">
                      <h4 className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">
                        LLM Runtime Configuration
                      </h4>
                      <div className="space-y-3.5 text-xs">
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400 text-[11px]">Provider State:</span>
                          {chatHistory.length > 0 && chatHistory[chatHistory.length - 1].sender === "npc" ? (
                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono uppercase border ${
                              chatHistory[chatHistory.length - 1].llm_provider === "gemini"
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                            }`}>
                              {chatHistory[chatHistory.length - 1].llm_provider === "gemini" ? "GEMINI LIVE" : "MOCK OFFLINE"}
                            </span>
                          ) : (
                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono uppercase border ${
                              modelOverride.includes("gemini")
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                            }`}>
                              {modelOverride.includes("gemini") ? "GEMINI MODE" : "MOCK/OFFLINE"}
                            </span>
                          )}
                        </div>
                        
                        <div className="space-y-1">
                          <label className="text-[9px] font-mono text-slate-500 uppercase font-bold block">Model Override</label>
                          <select
                            value={modelOverride}
                            onChange={(e) => setModelOverride(e.target.value)}
                            className="w-full bg-[#0a0a0a] text-xs text-[#fafafa] p-2 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition cursor-pointer"
                          >
                            <option value="">Default (from Environment config)</option>
                            <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                            <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                            <option value="gemini-1.5-flash">gemini-1.5-flash</option>
                            <option value="mock-model">mock-model</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Section 2: Grounding (Vector Search) */}
                    <div className="space-y-3 pt-1 flex-1 flex flex-col min-h-0">
                      <div className="space-y-1.5 select-none">
                        <label className="text-[10px] font-mono font-bold text-[#a1a1aa] uppercase tracking-wider block">
                          Grounding Context (RAG Search)
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={debugSearchQuery}
                            onChange={(e) => setDebugSearchQuery(e.target.value)}
                            placeholder="Search lore keywords to add as context..."
                            className="flex-1 bg-[#0a0a0a] text-xs text-[#fafafa] px-3 py-1.5 rounded border border-[#262626] focus:border-[#fafafa] outline-none transition"
                            onKeyDown={(e) => e.key === "Enter" && handleRetrieveLore()}
                          />
                          <button
                            type="button"
                            onClick={handleRetrieveLore}
                            disabled={isRetrievingLore || !debugSearchQuery.trim()}
                            className="bg-[#262626] hover:bg-[#333] border border-[#333] hover:border-slate-700 text-[#fafafa] text-xs px-3 rounded transition disabled:opacity-40 disabled:cursor-not-allowed select-none font-semibold"
                          >
                            {isRetrievingLore ? "Searching..." : "Search"}
                          </button>
                        </div>
                      </div>

                      {/* Chunks Checklist */}
                      <div className="space-y-2 flex-1 flex flex-col min-h-0">
                        <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 font-semibold select-none">
                          <span>LORE CHUNKS ({retrievedChunks.length} FOUND)</span>
                          <span>{selectedChunkIds.length} SELECTED</span>
                        </div>
                        
                        {retrievedChunks.length === 0 ? (
                          <div className="flex-1 py-10 flex items-center justify-center text-center text-slate-600 text-[10px] border border-[#262626] border-dashed rounded font-mono select-none bg-[#0a0a0a]/10">
                            NO GROUNDING LORE RETRIEVED
                          </div>
                        ) : (
                          <div className="flex-1 overflow-y-auto space-y-2 border border-[#262626] rounded bg-[#0a0a0a]/50 p-2 max-h-[220px]">
                            {retrievedChunks.map((chunk) => {
                              const isChecked = selectedChunkIds.includes(chunk.chunk_id);
                              return (
                                <div
                                  key={chunk.chunk_id}
                                  onClick={() => handleToggleChunk(chunk.chunk_id)}
                                  className={`flex items-start gap-2 p-2 rounded border cursor-pointer transition select-none ${
                                    isChecked
                                      ? "bg-[#171717] border-slate-700"
                                      : "bg-transparent border-[#262626]/60 hover:bg-[#111]/30"
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={() => {}}
                                    className="mt-0.5 pointer-events-none accent-[#b9ff66]"
                                  />
                                  <div className="space-y-0.5 flex-1">
                                    <div className="flex items-center justify-between text-[9px] font-mono text-slate-500">
                                      <span className="truncate max-w-[150px] font-bold">
                                        {chunk.title} (#{chunk.chunk_index + 1})
                                      </span>
                                      <span>
                                        {(chunk.similarity * 100).toFixed(0)}% sim
                                      </span>
                                    </div>
                                    <p className="text-[10px] text-[#a1a1aa] leading-relaxed line-clamp-2">
                                      {chunk.content}
                                    </p>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Section 3: Telemetry Panel */}
                    {chatHistory.length > 0 && chatHistory[chatHistory.length - 1].sender === "npc" && chatHistory[chatHistory.length - 1].telemetry && (
                      <div className="border-t border-[#262626] pt-3.5 space-y-3">
                        <span className="text-[10px] font-mono font-bold text-slate-500 uppercase block select-none">
                          Dialogue Transaction Observability
                        </span>
                        
                        {/* Stats Grid */}
                        <div className="grid grid-cols-3 gap-2 text-[10px] font-mono select-none">
                          <div className="bg-[#111] border border-[#262626] p-2.5 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">LATENCY</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5">
                              {chatHistory[chatHistory.length - 1].telemetry?.latency_ms}ms
                            </span>
                          </div>
                          <div className="bg-[#111] border border-[#262626] p-2.5 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">TOTAL TOKENS</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5 text-indigo-400">
                              {Number(chatHistory[chatHistory.length - 1].telemetry?.input_tokens) + 
                               Number(chatHistory[chatHistory.length - 1].telemetry?.output_tokens)}
                            </span>
                          </div>
                          <div className="bg-[#111] border border-[#262626] p-2.5 rounded text-center">
                            <span className="text-slate-500 block uppercase text-[8px] font-semibold">EST. COST (USD)</span>
                            <span className="text-[#fafafa] font-bold block mt-0.5 text-emerald-400">
                              ${chatHistory[chatHistory.length - 1].telemetry?.estimated_cost_usd.toFixed(6)}
                            </span>
                          </div>
                        </div>
                        
                        {/* Safety Ratings Collapsible */}
                        {chatHistory[chatHistory.length - 1].telemetry?.safety_ratings && chatHistory[chatHistory.length - 1].telemetry!.safety_ratings.length > 0 && (
                          <details className="text-[11px] group">
                            <summary className="font-mono text-slate-500 hover:text-slate-300 cursor-pointer font-bold select-none uppercase outline-none list-none flex items-center justify-between">
                              <span>► safety evaluation ratings</span>
                              <span className="text-[8.5px] font-normal text-slate-600 group-open:hidden">expand</span>
                            </summary>
                            <div className="mt-2 p-2.5 rounded bg-[#0a0a0a]/50 border border-[#262626] space-y-1.5 font-mono text-[9.5px]">
                              {chatHistory[chatHistory.length - 1].telemetry!.safety_ratings.map((rating, idx) => (
                                <div key={idx} className="flex justify-between items-center text-[#a1a1aa] border-b border-[#262626]/40 pb-1 last:border-0 last:pb-0">
                                  <span className="truncate max-w-[180px]">{rating.category.replace("HARM_CATEGORY_", "")}</span>
                                  <span className={`font-bold ${
                                    rating.probability === "NEGLIGIBLE" ? "text-emerald-450" : "text-amber-500"
                                  }`}>{rating.probability}</span>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-[#262626] bg-[#111111] flex items-center justify-end select-none">
              <button
                type="button"
                onClick={() => setIsDebugDrawerOpen(false)}
                className="bg-[#262626] hover:bg-[#333] border border-slate-800 hover:border-slate-700 text-[#fafafa] px-5 py-2 rounded text-xs font-bold font-sans transition"
              >
                Close Debugger
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
