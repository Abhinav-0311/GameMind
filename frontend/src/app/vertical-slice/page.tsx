"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import DashboardLayout from "@/components/DashboardLayout";

// Fetch endpoints using standard headers
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DocumentItem {
  id: string;
  title: string;
  chunks_count: number;
}

interface NpcItem {
  id: string;
  slug: string;
  name: string;
  title?: string;
  animation_hints?: Record<string, string>;
}

interface Citation {
  document_id: string;
  chunk_id: string;
  title: string;
  similarity: number;
}

interface Emotions {
  trust: number;
  fear: number;
  anger: number;
  curiosity: number;
  loyalty: number;
}

interface ChatMessage {
  sender: "player" | "npc";
  text: string;
  suggested_animation?: string;
  emotions?: Emotions;
  citations?: Citation[];
  timestamp: string;
}

interface QuestObjective {
  id: string;
  objective_index: number;
  description: string;
  target_type: string;
  target_id: string;
  quantity_required: number;
}

interface Quest {
  id?: string;
  npc_slug: string;
  title: string;
  description: string;
  difficulty: string;
  rewards: {
    gold: number;
    xp: number;
    items: string[];
  };
  objectives: QuestObjective[];
}

export default function VerticalSliceSimulator() {
  // Scoping Headers
  const [projectId, setProjectId] = useState("default_project");
  const [playerId, setPlayerId] = useState("default_player");

  // Options lists
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [npcs, setNpcs] = useState<NpcItem[]>([]);

  // Selected items
  const [selectedDocId, setSelectedDocId] = useState("");
  const [selectedNpcSlug, setSelectedNpcSlug] = useState("");

  // UI States
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [questLoading, setQuestLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);

  // Chat conversation
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [messageInput, setMessageInput] = useState("");

  // Quest states
  const [generatedQuest, setGeneratedQuest] = useState<Quest | null>(null);
  const [acceptedQuestId, setAcceptedQuestId] = useState<string | null>(null);

  // Hints state
  const [hintLevel, setHintLevel] = useState(1);
  const [hintText, setHintText] = useState<string | null>(null);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const [currentHintLevel, setCurrentHintLevel] = useState(0);

  // Raw JSON display
  const [rawPayload, setRawPayload] = useState<Record<string, unknown> | null>(null);

  const handleProjectIdChange = (newProjId: string) => {
    setProjectId(newProjId);
    setLoading(true);
  };

  // Fetch initial config (documents & NPCs)
  useEffect(() => {
    const abortController = new AbortController();

    const fetchOptions = async () => {
      setError(null);
      try {
        const headers = { "X-Game-Project-ID": projectId };

        // Load documents
        const docsRes = await fetch(`${API_BASE_URL}/api/v1/documents`, { 
          headers,
          signal: abortController.signal
        });
        if (!docsRes.ok) throw new Error("Failed to fetch documents for project");
        const docsData = await docsRes.json();

        // Load NPCs
        const npcsRes = await fetch(`${API_BASE_URL}/api/v1/npcs`, { 
          headers,
          signal: abortController.signal
        });
        if (!npcsRes.ok) throw new Error("Failed to fetch NPCs for project");
        const npcsData = await npcsRes.json();

        if (!abortController.signal.aborted) {
          setDocuments(docsData);
          if (docsData.length > 0) setSelectedDocId(docsData[0].id);
          else setSelectedDocId("");

          setNpcs(npcsData);
          if (npcsData.length > 0) setSelectedNpcSlug(npcsData[0].slug);
          else setSelectedNpcSlug("");
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        const errMsg = err instanceof Error ? err.message : "Network failure fetching workspace configurations.";
        if (!abortController.signal.aborted) {
          setError(errMsg);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchOptions();

    return () => {
      abortController.abort();
    };
  }, [projectId]);

  // Manage cooldown countdown
  useEffect(() => {
    if (cooldownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCooldownRemaining((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownRemaining]);

  const handleStartChat = async () => {
    // Reset conversation
    setConversationId(null);
    setChatHistory([]);
    setGeneratedQuest(null);
    setAcceptedQuestId(null);
    setHintText(null);
    setRawPayload(null);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageInput.trim() || !selectedNpcSlug) return;

    const userMessage = messageInput;
    setMessageInput("");
    setError(null);

    // Append player message
    const newHistory: ChatMessage[] = [
      ...chatHistory,
      {
        sender: "player",
        text: userMessage,
        timestamp: new Date().toLocaleTimeString(),
      },
    ];
    setChatHistory(newHistory);

    setLoading(true);
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const payload = {
        npc_slug: selectedNpcSlug,
        player_message: userMessage,
        player_id: playerId,
        conversation_id: conversationId || undefined,
        selected_chunk_ids: selectedDocId ? [selectedDocId] : undefined,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/dialogue/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Dialogue chat request failed.");
      }

      const data = await res.json();
      setRawPayload(data);

      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }

      // Append NPC message
      setChatHistory([
        ...newHistory,
        {
          sender: "npc",
          text: data.response_text,
          suggested_animation: data.suggested_animation,
          emotions: data.npc_emotions,
          citations: data.citations,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Network failure generating NPC dialogue.";
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateQuest = async () => {
    if (!selectedNpcSlug) return;
    setQuestLoading(true);
    setError(null);
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const payload = {
        npc_slug: selectedNpcSlug,
        player_id: playerId,
        player_level: 5,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/quests/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Quest generation failed.");
      }

      const data = await res.json();
      setGeneratedQuest(data);
      setRawPayload(data);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to generate quest narrative.";
      setError(errMsg);
    } finally {
      setQuestLoading(false);
    }
  };

  const handleAcceptQuest = async () => {
    if (!generatedQuest) return;
    setQuestLoading(true);
    setError(null);
    try {
      // 1. Create the quest model in DB
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const questPayload = {
        npc_slug: generatedQuest.npc_slug,
        title: generatedQuest.title,
        description: generatedQuest.description,
        difficulty: generatedQuest.difficulty,
        gold_reward: generatedQuest.rewards.gold,
        xp_reward: generatedQuest.rewards.xp,
        item_rewards: generatedQuest.rewards.items,
        objectives: generatedQuest.objectives.map((o) => ({
          objective_index: o.objective_index,
          description: o.description,
          target_type: o.target_type,
          target_id: o.target_id,
          quantity_required: o.quantity_required,
        })),
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/quests`, {
        method: "POST",
        headers,
        body: JSON.stringify(questPayload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to register generated quest.");
      }

      const createdQuest = await res.json();

      // 2. Accept quest progress
      const acceptRes = await fetch(`${API_BASE_URL}/api/v1/quests/progress`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          quest_id: createdQuest.id,
          player_id: playerId,
        }),
      });

      if (!acceptRes.ok) {
        const errData = await acceptRes.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to accept quest progress.");
      }

      setAcceptedQuestId(createdQuest.id);
      setRawPayload(createdQuest);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to accept quest.";
      setError(errMsg);
    } finally {
      setQuestLoading(false);
    }
  };

  const handleRequestHint = async () => {
    if (!acceptedQuestId) return;
    setHintLoading(true);
    setError(null);
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const payload = {
        quest_id: acceptedQuestId,
        player_id: playerId,
        hint_level: hintLevel,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/hints/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to generate hint.");
      }

      const data = await res.json();
      setHintText(data.hint);
      setRawPayload(data);

      // Check status for cooldowns & progression level
      const statusRes = await fetch(
        `${API_BASE_URL}/api/v1/hints/status?quest_id=${acceptedQuestId}&player_id=${playerId}`,
        { headers }
      );
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setCooldownRemaining(statusData.cooldown_remaining_seconds);
        setCurrentHintLevel(statusData.current_level);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to request hint.";
      setError(errMsg);
    } finally {
      setHintLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto pb-12 space-y-8">
        {/* Header Title */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-[#262626] pb-4">
          <div className="space-y-1.5">
            <h2 className="text-xl font-bold text-[#fafafa] tracking-tight">
              Playable Vertical Slice Simulator
            </h2>
            <p className="text-xs text-[#a1a1aa] leading-relaxed">
              Verify lore upload, semantic retrieval dialogue, animation mapping, emotions, dynamic quests, and progressive hints end-to-end.
            </p>
          </div>
          <div className="mt-4 md:mt-0 flex gap-3">
            <div>
              <label className="block text-[10px] font-mono font-bold text-[#a1a1aa] uppercase mb-1">
                Project ID
              </label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => handleProjectIdChange(e.target.value)}
                className="bg-[#111111] border border-[#262626] px-3 py-1.5 text-xs text-[#fafafa] rounded font-mono w-40 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono font-bold text-[#a1a1aa] uppercase mb-1">
                Player ID
              </label>
              <input
                type="text"
                value={playerId}
                onChange={(e) => setPlayerId(e.target.value)}
                className="bg-[#111111] border border-[#262626] px-3 py-1.5 text-xs text-[#fafafa] rounded font-mono w-40 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="bg-red-950/40 border border-red-500/50 text-red-200 px-4 py-3 rounded text-xs flex justify-between items-center">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200 font-bold">&times;</button>
          </div>
        )}

        {/* Top Segment: Config Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-[#111111]/40 border border-[#262626] p-5 rounded">
          {/* Select Lore */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-[#fafafa]">
              1. Select Lore Context Document
            </label>
            {documents.length === 0 ? (
              <div className="text-xs text-[#a1a1aa] py-2">
                No documents found for this project.{" "}
                <Link href="/knowledge" className="text-purple-400 hover:underline">
                  Upload lore first &rarr;
                </Link>
              </div>
            ) : (
              <select
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full bg-[#111111] border border-[#262626] p-2 text-xs text-[#fafafa] rounded focus:outline-none"
              >
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title} ({d.chunks_count} chunks)
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Select NPC */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-[#fafafa]">
              2. Select NPC Character
            </label>
            {npcs.length === 0 ? (
              <div className="text-xs text-[#a1a1aa] py-2">
                No NPCs found for this project.{" "}
                <Link href="/npcs" className="text-purple-400 hover:underline">
                  Create an NPC &rarr;
                </Link>
              </div>
            ) : (
              <select
                value={selectedNpcSlug}
                onChange={(e) => setSelectedNpcSlug(e.target.value)}
                className="w-full bg-[#111111] border border-[#262626] p-2 text-xs text-[#fafafa] rounded focus:outline-none"
              >
                {npcs.map((n) => (
                  <option key={n.id} value={n.slug}>
                    {n.name} ({n.title || "NPC"})
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* Main Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Column A & B: Live Dialogue Chat */}
          <div className="lg:col-span-2 space-y-6 flex flex-col">
            <div className="border border-[#262626] rounded bg-[#111111]/10 flex flex-col h-[500px]">
              {/* Chat Header */}
              <div className="bg-[#111111] border-b border-[#262626] px-4 py-3 flex justify-between items-center">
                <span className="text-xs font-semibold text-[#fafafa]">
                  Dialogue Session Simulator
                </span>
                <button
                  onClick={handleStartChat}
                  className="text-[10px] font-mono bg-purple-900/50 hover:bg-purple-800 border border-purple-500/50 px-2 py-1 rounded transition text-purple-200"
                >
                  RESET SESSION
                </button>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-xs">
                {chatHistory.length === 0 && (
                  <div className="text-slate-500 text-center py-12">
                    Start a conversation with the selected NPC. Type a query below.
                  </div>
                )}
                {chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col max-w-[85%] ${
                      msg.sender === "player" ? "ml-auto items-end" : "mr-auto items-start"
                    }`}
                  >
                    <div
                      className={`px-3.5 py-2.5 rounded leading-relaxed ${
                        msg.sender === "player"
                          ? "bg-purple-900/35 border border-purple-800 text-purple-100 rounded-br-none"
                          : "bg-zinc-900/80 border border-zinc-800 text-zinc-100 rounded-bl-none"
                      }`}
                    >
                      {msg.text}
                    </div>
                    <span className="text-[10px] text-slate-500 mt-1 font-mono">
                      {msg.sender === "player" ? "Player" : "NPC"} • {msg.timestamp}
                    </span>

                    {/* NPC Metadata Expose */}
                    {msg.sender === "npc" && (msg.suggested_animation || msg.emotions || msg.citations) && (
                      <div className="mt-2 w-full bg-[#111111] border border-[#262626] rounded p-2.5 space-y-3 max-w-sm shadow-md font-sans">
                        {/* Animation suggestions */}
                        {msg.suggested_animation && (
                          <div className="flex justify-between items-center text-[10px]">
                            <span className="text-slate-400">Unity Animation Suggestion:</span>
                            <span className="bg-purple-900/50 border border-purple-500/30 text-purple-300 font-mono px-2 py-0.5 rounded uppercase font-semibold">
                              {msg.suggested_animation}
                            </span>
                          </div>
                        )}

                        {/* Emotion bars */}
                        {msg.emotions && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] text-slate-400 block border-b border-[#262626] pb-1">
                              NPC Emotion Metrics
                            </span>
                            {Object.entries(msg.emotions).map(([emotion, val]) => (
                              <div key={emotion} className="flex items-center justify-between text-[9px] font-mono">
                                <span className="capitalize text-slate-300 w-16">{emotion}:</span>
                                <div className="flex-1 bg-zinc-800 rounded-full h-1.5 mx-2 overflow-hidden">
                                  <div
                                    className="bg-purple-500 h-1.5 rounded-full"
                                    style={{ width: `${(val * 100)}%` }}
                                  />
                                </div>
                                <span className="text-purple-300 w-8 text-right font-bold">
                                  {Math.round(val * 100)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Citations */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] text-slate-400 block border-b border-[#262626] pb-1">
                              Lore Grounding Citations
                            </span>
                            {msg.citations.map((cit, idx) => (
                              <div key={idx} className="bg-zinc-950 p-1.5 rounded border border-[#262626] text-[9px] space-y-1">
                                <div className="flex justify-between text-purple-300 font-semibold">
                                  <span>{cit.title}</span>
                                  <span>Similarity: {Math.round(cit.similarity * 100)}%</span>
                                </div>
                                <div className="text-slate-500 font-mono flex flex-col text-[8px]">
                                  <span>Doc ID: {cit.document_id}</span>
                                  <span>Chunk ID: {cit.chunk_id}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Chat Input */}
              <form onSubmit={handleSendMessage} className="p-3 border-t border-[#262626] bg-[#111111] flex gap-2">
                <input
                  type="text"
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  placeholder="Type a message or ask NPC about lore..."
                  className="flex-1 bg-[#0a0a0a] border border-[#262626] px-3.5 py-2 text-xs text-[#fafafa] rounded focus:outline-none focus:border-purple-500 font-sans"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-purple-900 border border-purple-500 text-purple-200 px-4 py-2 rounded text-xs font-semibold hover:bg-purple-800 transition disabled:opacity-50"
                >
                  {loading ? "..." : "SEND"}
                </button>
              </form>
            </div>
          </div>

          {/* Column C: Quest and Hints */}
          <div className="space-y-6">
            {/* Quest Generation Panel */}
            <div className="border border-[#262626] rounded bg-[#111111]/30 p-4 space-y-4">
              <div className="border-b border-[#262626] pb-2 flex justify-between items-center">
                <span className="text-xs font-bold text-[#fafafa] uppercase tracking-wide">
                  Dynamic Quest Generator
                </span>
                {questLoading && <span className="text-[10px] text-purple-400 font-mono animate-pulse">GENERATING...</span>}
              </div>

              {!generatedQuest ? (
                <div className="space-y-3">
                  <p className="text-slate-500 text-xs">
                    No active quest generated. Request a quest contextually matched to current world state.
                  </p>
                  <button
                    onClick={handleGenerateQuest}
                    disabled={questLoading || !selectedNpcSlug}
                    className="w-full bg-purple-900 hover:bg-purple-800 border border-purple-500 text-purple-200 px-3 py-2 rounded text-xs font-semibold transition disabled:opacity-50"
                  >
                    GENERATE QUEST NARRATIVE
                  </button>
                </div>
              ) : (
                <div className="space-y-3 text-xs">
                  <div className="bg-zinc-900/60 p-3 rounded border border-purple-900/40 space-y-2">
                    <div className="flex justify-between items-center">
                      <h4 className="font-bold text-[#fafafa]">{generatedQuest.title}</h4>
                      <span className="bg-purple-950 text-purple-300 border border-purple-800/50 px-2 py-0.5 rounded text-[10px] font-mono font-semibold">
                        {generatedQuest.difficulty}
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px] leading-normal">{generatedQuest.description}</p>
                    
                    {/* Objectives */}
                    <div className="space-y-1 mt-2">
                      <span className="text-[10px] font-semibold text-purple-300">Objectives:</span>
                      {generatedQuest.objectives.map((obj, i) => (
                        <div key={i} className="text-slate-400 text-[11px] flex gap-1.5">
                          <span>•</span>
                          <span>{obj.description} (Target ID: {obj.target_id})</span>
                        </div>
                      ))}
                    </div>

                    {/* Rewards */}
                    <div className="flex justify-between border-t border-[#262626]/80 pt-2 text-[10px] font-mono">
                      <span className="text-yellow-400/90 font-bold">Gold: {generatedQuest.rewards.gold}</span>
                      <span className="text-teal-400 font-bold">XP: {generatedQuest.rewards.xp}</span>
                      <span className="text-purple-400 font-bold">
                        Items: {generatedQuest.rewards.items.length > 0 ? generatedQuest.rewards.items.join(", ") : "None"}
                      </span>
                    </div>
                  </div>

                  {!acceptedQuestId ? (
                    <button
                      onClick={handleAcceptQuest}
                      disabled={questLoading}
                      className="w-full bg-emerald-900 hover:bg-emerald-800 border border-emerald-500 text-emerald-200 px-3 py-2 rounded text-xs font-semibold transition"
                    >
                      ACCEPT QUEST & START PROGRESSION
                    </button>
                  ) : (
                    <div className="bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 px-3 py-2 rounded text-center font-semibold text-[11px]">
                      Quest Accepted & Registered! Progress active.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Progressive Hints Panel */}
            <div className="border border-[#262626] rounded bg-[#111111]/30 p-4 space-y-4">
              <div className="border-b border-[#262626] pb-2 flex justify-between items-center">
                <span className="text-xs font-bold text-[#fafafa] uppercase tracking-wide">
                  Progressive Hints Studio
                </span>
                {hintLoading && <span className="text-[10px] text-purple-400 font-mono animate-pulse">REQUESTING...</span>}
              </div>

              {!acceptedQuestId ? (
                <p className="text-slate-500 text-xs">
                  Accept a quest first to test progressive hints progression and cooldown gates.
                </p>
              ) : (
                <div className="space-y-4 text-xs font-sans">
                  {/* Select Hint Level */}
                  <div>
                    <label className="block text-[10px] font-mono font-bold text-[#a1a1aa] uppercase mb-1">
                      Hint Level (1: Subtle, 2: Medium, 3: Direct)
                    </label>
                    <div className="flex gap-2">
                      {[1, 2, 3].map((lvl) => (
                        <button
                          key={lvl}
                          type="button"
                          onClick={() => setHintLevel(lvl)}
                          className={`flex-1 py-1 px-2.5 text-xs font-mono font-bold border rounded transition ${
                            hintLevel === lvl
                              ? "bg-purple-900/60 border-purple-500 text-purple-200"
                              : "bg-[#111111] border-[#262626] text-slate-400 hover:text-[#fafafa]"
                          }`}
                        >
                          Lvl {lvl}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleRequestHint}
                    disabled={hintLoading || cooldownRemaining > 0}
                    className="w-full bg-purple-900 hover:bg-purple-800 border border-purple-500 text-purple-200 px-3 py-2 rounded text-xs font-semibold transition disabled:opacity-50"
                  >
                    {cooldownRemaining > 0 ? `COOLDOWN ACTIVE (${cooldownRemaining}s)` : "GENERATE ESCALATION HINT"}
                  </button>

                  {/* Cooldown tracker / Progression badge */}
                  <div className="flex justify-between items-center bg-[#111111] border border-[#262626] p-2 rounded text-[10px] font-mono text-slate-400">
                    <span>Active Cooldown Gate:</span>
                    <span className={cooldownRemaining > 0 ? "text-amber-400 font-bold" : "text-emerald-400 font-bold"}>
                      {cooldownRemaining > 0 ? `${cooldownRemaining}s remaining` : "READY"}
                    </span>
                  </div>

                  <div className="flex justify-between items-center bg-[#111111] border border-[#262626] p-2 rounded text-[10px] font-mono text-slate-400">
                    <span>Highest Escalation Level:</span>
                    <span className="text-purple-300 font-bold">Level {currentHintLevel} / 3</span>
                  </div>

                  {/* Generated Hint Text */}
                  {hintText && (
                    <div className="bg-purple-950/20 border border-purple-900/50 p-3 rounded text-slate-300 leading-relaxed text-[11px] font-sans">
                      <span className="text-[10px] font-bold text-purple-300 block mb-1 uppercase font-mono">
                        Generated Hint Content:
                      </span>
                      {hintText}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Segment: Raw Payload Inspector */}
        <div className="border border-[#262626] rounded bg-[#111111]/40 overflow-hidden">
          <div className="bg-[#111111] border-b border-[#262626] px-4 py-3 flex justify-between items-center select-none">
            <span className="text-xs font-bold text-[#fafafa] uppercase tracking-wide">
              API DTO Raw Payload Inspector
            </span>
            <span className="text-[10px] font-mono text-purple-400">
              API Version: 1.0 (Version Frozen)
            </span>
          </div>
          <div className="p-4 bg-[#0a0a0a] min-h-[150px] max-h-[300px] overflow-y-auto font-mono text-[11px] text-[#fafafa]/90">
            {rawPayload ? (
              <pre className="whitespace-pre-wrap">{JSON.stringify(rawPayload, null, 2)}</pre>
            ) : (
              <div className="text-slate-500 text-center py-8">
                Perform actions (chat, generate quest, request hint) to inspect raw structured JSON envelopes.
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
