"use client";

import React, { useState, useEffect, useRef } from "react";
import { api, QuestResponse, HintResponse, HintStatusResponse } from "@/lib/api";

export default function HintStudioPage() {
  // Quest state
  const [quests, setQuests] = useState<QuestResponse[]>([]);
  const [selectedQuestId, setSelectedQuestId] = useState("");
  const [useCustomQuestId, setUseCustomQuestId] = useState(false);
  const [customQuestId, setCustomQuestId] = useState("");

  // Input state
  const [playerId, setPlayerId] = useState("default_player");
  const [hintLevel, setHintLevel] = useState<number>(1);

  // Async UI states
  const [isQuestsLoading, setIsQuestsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);

  // Result payloads
  const [generatedHint, setGeneratedHint] = useState<HintResponse | null>(null);
  const [statusInfo, setStatusInfo] = useState<HintStatusResponse | null>(null);

  // Warnings & Error Banners
  const [validationError, setValidationError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);

  // Real-time Cooldown Timer
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const activeQuestId = useCustomQuestId ? customQuestId.trim() : selectedQuestId;

  const loadQuests = async () => {
    setIsQuestsLoading(true);
    setNetworkError(null);
    try {
      const list = await api.getQuests();
      setQuests(list);
      if (list.length > 0) {
        setSelectedQuestId(list[0].id);
      }
    } catch (err: unknown) {
      console.error(err);
      setNetworkError("Backend unavailable: Failed to fetch quests list. Please ensure the backend container is running.");
    } finally {
      setIsQuestsLoading(false);
    }
  };

  const triggerCooldown = (seconds: number) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCooldownSeconds(seconds);
  };

  const formatCooldown = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins}:${remaining < 10 ? "0" : ""}${remaining}`;
  };

  // POST Hint Generation Request
  const handleGenerateHint = async () => {
    if (!activeQuestId) {
      setValidationError("Quest ID is required.");
      return;
    }
    setIsGenerating(true);
    setValidationError(null);
    setNetworkError(null);
    try {
      const res = await api.generateHint({
        quest_id: activeQuestId,
        player_id: playerId.trim(),
        hint_level: hintLevel,
      });
      setGeneratedHint(res);
      // Immediately retrieve updated status (cooldown remaining & current progression level)
      await handleCheckStatus(true);
    } catch (err: unknown) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : String(err);
      // Surface validation warnings (e.g. HTTP 422 details)
      if (errMsg && (errMsg.includes("violation") || errMsg.includes("wait") || errMsg.includes("Cooldown") || errMsg.includes("Progression") || errMsg.includes("cooldown"))) {
        setValidationError(errMsg);
      } else {
        setNetworkError("Network Failure: Failed to generate hint. Ensure backend container is online.");
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // GET Hint Status Request
  const handleCheckStatus = async (silent: boolean = false) => {
    if (!activeQuestId) {
      if (!silent) setValidationError("Quest ID is required.");
      return;
    }
    if (!silent) setIsCheckingStatus(true);
    setValidationError(null);
    setNetworkError(null);
    try {
      const res = await api.getHintStatus(activeQuestId, playerId.trim());
      setStatusInfo(res);
      triggerCooldown(res.cooldown_remaining_seconds);
    } catch (err: unknown) {
      console.error(err);
      if (!silent) {
        setNetworkError("Network Failure: Failed to query progression status. Ensure backend container is online.");
      }
    } finally {
      if (!silent) setIsCheckingStatus(false);
    }
  };

  // Load quests list on page mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadQuests();
  }, []);

  // Cooldown countdown mechanism
  useEffect(() => {
    if (cooldownSeconds > 0) {
      timerRef.current = setInterval(() => {
        setCooldownSeconds((prev) => {
          if (prev <= 1) {
            if (timerRef.current) clearInterval(timerRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [cooldownSeconds]);

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12 animate-fade-in font-sans">
      {/* Header */}
      <div className="space-y-1.5 border-b border-[#262626] pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
            Progressive Hint Studio
          </h2>
          <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
            Test progressive escalation paths, simulate cooldown thresholds, and verify live cache validations.
          </p>
        </div>
        <button
          onClick={loadQuests}
          className="bg-[#111111] hover:bg-[#171717] border border-[#262626] rounded text-slate-400 font-mono text-[10px] uppercase tracking-wider py-1 px-3 outline-none transition"
        >
          Reload Quests
        </button>
      </div>

      {/* Network Failure / Offline Banner */}
      {networkError && (
        <div className="rounded border border-red-950 bg-red-950/20 p-4 flex items-start gap-3 animate-pulse">
          <span className="text-red-400 text-sm">⚠️</span>
          <div className="space-y-1 text-xs">
            <span className="font-bold text-red-200">System Connection Error</span>
            <p className="text-red-400 leading-relaxed font-mono">{networkError}</p>
          </div>
        </div>
      )}

      {/* Validation Error Banner */}
      {validationError && (
        <div className="rounded border border-amber-950 bg-amber-950/20 p-4 flex items-start gap-3">
          <span className="text-amber-400 text-sm">⚠️</span>
          <div className="space-y-1 text-xs">
            <span className="font-bold text-amber-200">Progression Request Blocked</span>
            <p className="text-amber-400 leading-relaxed font-mono">{validationError}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Form Settings (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded border border-[#262626] bg-[#111111]/45 p-6 space-y-5">
            <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-2.5 block uppercase tracking-wider">
              Hint Configuration Settings
            </span>

            {/* Player ID Field */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">
                Player Account Identifier
              </label>
              <input
                type="text"
                value={playerId}
                onChange={(e) => setPlayerId(e.target.value)}
                className="w-full bg-[#0a0a0a] border border-[#262626] rounded text-slate-300 font-mono text-xs py-2 px-3 placeholder-slate-700 outline-none focus:border-slate-700 transition"
                placeholder="Enter unique player_id..."
              />
            </div>

            {/* Quest ID Selection toggle and inputs */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide">
                  Active World Quest
                </label>
                <button
                  type="button"
                  onClick={() => setUseCustomQuestId(!useCustomQuestId)}
                  className="text-[10px] font-mono text-slate-400 hover:text-[#fafafa] transition hover:underline"
                >
                  {useCustomQuestId ? "Use Quest Selector Dropdown" : "Use Custom UUID Fallback"}
                </button>
              </div>

              {useCustomQuestId ? (
                <input
                  type="text"
                  value={customQuestId}
                  onChange={(e) => setCustomQuestId(e.target.value)}
                  className="w-full bg-[#0a0a0a] border border-[#262626] rounded text-slate-300 font-mono text-xs py-2 px-3 placeholder-slate-700 outline-none focus:border-slate-700 transition"
                  placeholder="Enter quest UUID (e.g. f81d4fae-7dec-11d0-a765-00a0c91e6bf6)..."
                />
              ) : isQuestsLoading ? (
                <div className="w-full py-2 px-3 bg-[#0a0a0a] border border-[#262626] rounded text-slate-600 font-mono text-xs animate-pulse">
                  LOADING WORKSPACE QUESTS...
                </div>
              ) : quests.length === 0 ? (
                <div className="w-full py-2 px-3 bg-[#0a0a0a] border border-[#262626] rounded text-amber-500 font-mono text-xs">
                  NO ACTIVE QUESTS FOUND - SWITCH TO CUSTOM UUID FALLBACK
                </div>
              ) : (
                <select
                  value={selectedQuestId}
                  onChange={(e) => setSelectedQuestId(e.target.value)}
                  className="w-full bg-[#0a0a0a] border border-[#262626] rounded text-slate-300 text-xs py-2 px-3 outline-none focus:border-slate-700 transition"
                >
                  {quests.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.title} (Giver: {q.npc_slug})
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Hint Escalation Level Radio Group */}
            <div className="space-y-2">
              <label className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wide block">
                Requested Hint Level (Escalation Phase)
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { level: 1, name: "Subtle (Level 1)", desc: "Thematic cluing" },
                  { level: 2, name: "Medium (Level 2)", desc: "Location/Target details" },
                  { level: 3, name: "Direct (Level 3)", desc: "LLM action solution" },
                ].map((item) => (
                  <button
                    key={item.level}
                    type="button"
                    onClick={() => setHintLevel(item.level)}
                    className={`p-3 rounded border text-left flex flex-col justify-between transition ${
                      hintLevel === item.level
                        ? "bg-[#171717] border-[#262626] text-[#fafafa] font-bold"
                        : "bg-[#0a0a0a] border-transparent text-[#a1a1aa] hover:border-[#262626]/50"
                    }`}
                  >
                    <span className="text-xs font-semibold">{item.name}</span>
                    <span className="text-[10px] text-slate-500 font-mono font-medium block mt-1">
                      {item.desc}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Controls Actions row */}
            <div className="pt-2 flex items-center gap-3">
              <button
                onClick={handleGenerateHint}
                disabled={isGenerating || isQuestsLoading || !activeQuestId || cooldownSeconds > 0}
                className={`flex-1 py-2 px-4 rounded text-xs font-semibold tracking-wide transition uppercase ${
                  cooldownSeconds > 0
                    ? "bg-[#171717] text-slate-600 border border-[#262626] cursor-not-allowed"
                    : isGenerating
                    ? "bg-slate-800 text-slate-400 cursor-wait"
                    : "bg-[#b9ff66] text-[#0a0a0a] hover:bg-[#a6e655]"
                }`}
              >
                {isGenerating
                  ? "Generating Hint..."
                  : cooldownSeconds > 0
                  ? `Cooldown Active (${formatCooldown(cooldownSeconds)})`
                  : "Request Hint"}
              </button>

              <button
                onClick={() => handleCheckStatus(false)}
                disabled={isCheckingStatus || isQuestsLoading || !activeQuestId}
                className="py-2 px-4 bg-[#111111] hover:bg-[#171717] border border-[#262626] rounded text-slate-300 font-mono text-xs uppercase tracking-wide transition outline-none"
              >
                {isCheckingStatus ? "Checking..." : "Sync Status"}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Output / Display (1 col) */}
        <div className="space-y-6">
          {/* Progression State Summary */}
          <div className="rounded border border-[#262626] bg-[#111111] p-5 space-y-4">
            <span className="text-xs font-semibold text-[#fafafa] border-b border-[#262626] pb-2 block uppercase tracking-wider">
              Progression Registry
            </span>

            <div className="space-y-3 font-mono text-[11px]">
              {/* Cooldown timer row */}
              <div className="flex items-center justify-between border-b border-[#262626]/50 pb-2">
                <span className="text-slate-500">REQUEST COOLDOWN</span>
                {cooldownSeconds > 0 ? (
                  <span className="font-bold text-amber-500 animate-pulse font-mono">
                    {formatCooldown(cooldownSeconds)} REMAINING
                  </span>
                ) : (
                  <span className="font-bold text-emerald-400 uppercase tracking-wide">NO COOLDOWN</span>
                )}
              </div>

              {/* Progression level badges row */}
              <div className="flex items-center justify-between border-b border-[#262626]/50 pb-2.5">
                <span className="text-slate-500">CURRENT HINT LEVEL</span>
                <div className="flex items-center gap-1">
                  {[0, 1, 2, 3].map((l) => {
                    const current = statusInfo?.current_level ?? 0;
                    const isActive = l === current;
                    return (
                      <span
                        key={l}
                        className={`h-4.5 w-6 text-[9px] font-bold rounded flex items-center justify-center border font-mono select-none ${
                          isActive
                            ? "bg-[#b9ff66] text-[#0a0a0a] border-[#b9ff66]"
                            : l < current
                            ? "bg-[#171717] text-slate-400 border-[#262626]"
                            : "bg-[#0a0a0a] text-slate-700 border-[#262626]/30"
                        }`}
                      >
                        L{l}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Cache status badge row */}
              <div className="flex items-center justify-between border-b border-[#262626]/50 pb-2">
                <span className="text-slate-500">CACHE STATUS</span>
                {generatedHint ? (
                  generatedHint.cache_status === "hit" ? (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[9px] font-bold uppercase tracking-wider">
                      Cache Hit
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-slate-500/10 border border-slate-500/20 text-slate-400 text-[9px] font-bold uppercase tracking-wider">
                      Cache Miss
                    </span>
                  )
                ) : (
                  <span className="text-slate-600">AWAITING GENERATION</span>
                )}
              </div>

              {/* Last requested timestamp */}
              <div className="flex flex-col gap-1">
                <span className="text-slate-500 text-[9px] uppercase tracking-wide">LAST GENERATED AT</span>
                <span className="text-slate-400 text-[10px]">
                  {statusInfo?.last_requested_at
                    ? new Date(statusInfo.last_requested_at).toLocaleString()
                    : "Never requested"}
                </span>
              </div>
            </div>
          </div>

          {/* Hint Output Box */}
          <div className="rounded border border-[#262626] bg-[#111111]/40 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#262626] pb-2">
              <span className="text-xs font-semibold text-[#fafafa] uppercase tracking-wider">
                Hint Output Clue
              </span>
              {generatedHint && (
                <span
                  className={`px-1.5 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider ${
                    generatedHint.spoiler_level === "low"
                      ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                      : generatedHint.spoiler_level === "medium"
                      ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      : "bg-red-500/10 border-red-500/20 text-red-400"
                  }`}
                >
                  {generatedHint.spoiler_level} spoiler
                </span>
              )}
            </div>

            {generatedHint ? (
              <div className="p-3 bg-[#0a0a0a] rounded border border-[#262626] text-xs text-[#fafafa] leading-relaxed font-sans select-text font-medium">
                {generatedHint.hint}
              </div>
            ) : (
              <div className="py-8 text-center text-slate-500 font-mono text-[10px] uppercase tracking-wider select-none">
                No hint generated yet. Choose settings and click request.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
