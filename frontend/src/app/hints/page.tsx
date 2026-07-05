"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, HintResponse, HintStatusResponse, QuestResponse } from "@/lib/api";

export default function HintStudioPage() {
  const [quests, setQuests] = useState<QuestResponse[]>([]);
  const [selectedQuestId, setSelectedQuestId] = useState("");
  const [customQuestId, setCustomQuestId] = useState("");
  const [useCustomQuestId, setUseCustomQuestId] = useState(false);
  const [playerId, setPlayerId] = useState("default_player");
  const [hintLevel, setHintLevel] = useState(1);
  const [isLoadingQuests, setIsLoadingQuests] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);
  const [generatedHint, setGeneratedHint] = useState<HintResponse | null>(null);
  const [statusInfo, setStatusInfo] = useState<HintStatusResponse | null>(null);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeQuestId = useCustomQuestId ? customQuestId.trim() : selectedQuestId;

  const selectedQuest = useMemo(
    () => quests.find((quest) => quest.id === selectedQuestId) ?? null,
    [quests, selectedQuestId]
  );

  const loadQuests = useCallback(async () => {
    setIsLoadingQuests(true);
    setError(null);

    try {
      const list = await api.getQuests();
      setQuests(list);
      setSelectedQuestId((current) => {
        if (current && list.some((quest) => quest.id === current)) return current;
        return list[0]?.id ?? "";
      });
    } catch (err) {
      console.error("Failed to load quests:", err);
      setError("Quests could not be loaded. Check that the backend is running.");
    } finally {
      setIsLoadingQuests(false);
    }
  }, []);

  const syncStatus = useCallback(
    async (silent = false) => {
      if (!activeQuestId) {
        if (!silent) setNotice("Choose a quest before checking progression.");
        return;
      }

      if (!silent) setIsCheckingStatus(true);
      setNotice(null);
      setError(null);

      try {
        const response = await api.getHintStatus(activeQuestId, playerId.trim());
        setStatusInfo(response);
        setCooldownSeconds(response.cooldown_remaining_seconds);
      } catch (err) {
        console.error("Failed to sync hint status:", err);
        if (!silent) setError("Hint progression could not be loaded for this quest and player.");
      } finally {
        if (!silent) setIsCheckingStatus(false);
      }
    },
    [activeQuestId, playerId]
  );

  useEffect(() => {
    void Promise.resolve().then(loadQuests);
  }, [loadQuests]);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;

    const timer = window.setInterval(() => {
      setCooldownSeconds((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [cooldownSeconds]);

  const requestHint = async () => {
    if (!activeQuestId) {
      setNotice("Choose a quest before requesting a hint.");
      return;
    }

    setIsGenerating(true);
    setNotice(null);
    setError(null);

    try {
      const response = await api.generateHint({
        quest_id: activeQuestId,
        player_id: playerId.trim(),
        hint_level: hintLevel,
      });
      setGeneratedHint(response);
      await syncStatus(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Hint could not be generated.";
      if (
        message.toLowerCase().includes("cooldown") ||
        message.toLowerCase().includes("progression") ||
        message.toLowerCase().includes("wait") ||
        message.toLowerCase().includes("violation")
      ) {
        setNotice(message);
      } else {
        setError(message);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const currentLevel = statusInfo?.current_level ?? 0;
  const canRequest = Boolean(activeQuestId) && cooldownSeconds === 0 && !isGenerating && !isLoadingQuests;

  return (
    <main className="mx-auto max-w-6xl pb-14">
      <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-12">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c8794]">Hint Studio</p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#f7f8fa] sm:text-5xl">
            Test help that respects progression.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[#a5afbd]">
            Progressive hints should guide players without spoiling the solution too early. Check the current level,
            cooldown, cache state, and generated hint for a selected quest.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={requestHint}
              disabled={!canRequest}
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#f7f8fa] px-5 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isGenerating ? "Requesting..." : cooldownSeconds > 0 ? `Cooldown ${formatCooldown(cooldownSeconds)}` : "Request hint"}
            </button>
            <button
              type="button"
              onClick={() => syncStatus(false)}
              disabled={!activeQuestId || isCheckingStatus}
              className="inline-flex min-h-11 items-center justify-center rounded-md border border-[#27303a] px-5 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#3b4654] hover:bg-[#12161b] focus:outline-none focus:ring-2 focus:ring-[#3b4654] focus:ring-offset-2 focus:ring-offset-[#090b0e] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isCheckingStatus ? "Syncing..." : "Sync status"}
            </button>
          </div>
        </div>

        <aside className="self-start rounded-lg border border-[#222a33] bg-[#101419] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c8794]">Player state</p>
          <div className="mt-5 divide-y divide-[#222a33]">
            <FactRow label="Current level" value={`${currentLevel} / 3`} />
            <FactRow label="Cooldown" value={cooldownSeconds > 0 ? formatCooldown(cooldownSeconds) : "Ready"} />
            <FactRow label="Cache" value={generatedHint?.cache_status ?? "None"} />
            <FactRow label="Spoiler" value={generatedHint?.spoiler_level ?? "None"} />
          </div>
          <div className="mt-5">
            <ProgressDots currentLevel={currentLevel} />
          </div>
        </aside>
      </section>

      {error && <Alert tone="error" message={error} onDismiss={() => setError(null)} />}
      {notice && <Alert tone="notice" message={notice} onDismiss={() => setNotice(null)} />}

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border border-[#222a33] bg-[#101419]">
          <div className="border-b border-[#222a33] px-5 py-4">
            <h2 className="text-base font-semibold text-[#f7f8fa]">Hint request</h2>
            <p className="mt-1 text-sm leading-6 text-[#a5afbd]">
              Select the player and quest, then request the next useful level of help.
            </p>
          </div>

          <div className="space-y-5 p-5">
            <label className="block">
              <span className="text-xs font-semibold text-[#a5afbd]">Player ID</span>
              <input
                type="text"
                value={playerId}
                onChange={(event) => setPlayerId(event.target.value)}
                className="mt-2 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
              />
            </label>

            <div>
              <div className="flex items-center justify-between gap-4">
                <label className="text-xs font-semibold text-[#a5afbd]" htmlFor="quest-select">
                  Quest
                </label>
                <button
                  type="button"
                  onClick={loadQuests}
                  className="rounded-md px-2 py-1 text-xs font-semibold text-[#8bdff0] transition hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
                >
                  Reload
                </button>
              </div>

              {isLoadingQuests ? (
                <div className="mt-2 h-11 animate-pulse rounded-md bg-[#151b22]" />
              ) : quests.length === 0 && !useCustomQuestId ? (
                <div className="mt-2 rounded-md border border-[#222a33] bg-[#0b0f13] p-4">
                  <p className="text-sm leading-6 text-[#a5afbd]">
                    No quests are available yet. Generate and accept one in the simulator first.
                  </p>
                  <Link
                    href="/vertical-slice"
                    className="mt-3 inline-flex min-h-9 items-center rounded-md border border-[#303a46] px-3 text-xs font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
                  >
                    Open simulator
                  </Link>
                </div>
              ) : (
                <select
                  id="quest-select"
                  value={selectedQuestId}
                  onChange={(event) => setSelectedQuestId(event.target.value)}
                  disabled={useCustomQuestId}
                  className="mt-2 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {quests.map((quest) => (
                    <option key={quest.id} value={quest.id}>
                      {quest.title} ({quest.npc_slug})
                    </option>
                  ))}
                </select>
              )}
            </div>

            <details className="rounded-md border border-[#222a33] bg-[#0b0f13]">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[#a5afbd] transition hover:text-[#f7f8fa]">
                Advanced quest ID
              </summary>
              <div className="space-y-3 border-t border-[#222a33] p-4">
                <label className="flex items-center gap-3 text-sm text-[#a5afbd]">
                  <input
                    type="checkbox"
                    checked={useCustomQuestId}
                    onChange={(event) => setUseCustomQuestId(event.target.checked)}
                    className="h-4 w-4 accent-[#8bdff0]"
                  />
                  Use a custom quest ID
                </label>
                <input
                  type="text"
                  value={customQuestId}
                  onChange={(event) => setCustomQuestId(event.target.value)}
                  disabled={!useCustomQuestId}
                  placeholder="Quest UUID"
                  className="min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>
            </details>

            <div>
              <p className="text-xs font-semibold text-[#a5afbd]">Requested hint level</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {[
                  { level: 1, title: "Subtle", description: "Nudge without revealing the answer." },
                  { level: 2, title: "Directed", description: "Name a location, target, or next step." },
                  { level: 3, title: "Direct", description: "Give the clearest action to take." },
                ].map((item) => (
                  <button
                    key={item.level}
                    type="button"
                    onClick={() => setHintLevel(item.level)}
                    className={`min-h-32 rounded-lg border p-4 text-left transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0] ${
                      hintLevel === item.level
                        ? "border-[#8bdff0] bg-[#8bdff0] text-[#061014]"
                        : "border-[#27303a] bg-[#0a0e12] text-[#f7f8fa] hover:border-[#4a5563] hover:bg-[#121922]"
                    }`}
                  >
                    <span className="text-xs font-semibold uppercase tracking-[0.16em]">Level {item.level}</span>
                    <span className="mt-3 block text-lg font-semibold">{item.title}</span>
                    <span className={`mt-2 block text-sm leading-6 ${hintLevel === item.level ? "text-[#14323a]" : "text-[#a5afbd]"}`}>
                      {item.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-6">
          <section className="rounded-lg border border-[#222a33] bg-[#101419]">
            <div className="border-b border-[#222a33] px-5 py-4">
              <h2 className="text-base font-semibold text-[#f7f8fa]">Generated hint</h2>
              <p className="mt-1 text-xs text-[#7c8794]">The player-facing text returned by the hint engine.</p>
            </div>
            <div className="p-5">
              {generatedHint ? (
                <div>
                  <div className="mb-4 flex items-center gap-2">
                    <span className="rounded-full bg-[#8bdff0] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#061014]">
                      Level {generatedHint.hint_level}
                    </span>
                    <span className="rounded-full border border-[#27303a] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#a5afbd]">
                      {generatedHint.spoiler_level}
                    </span>
                  </div>
                  <p className="rounded-md border border-[#222a33] bg-[#0b0f13] p-4 text-sm leading-7 text-[#f7f8fa]">
                    {generatedHint.hint}
                  </p>
                </div>
              ) : (
                <div className="py-10 text-center">
                  <h3 className="text-sm font-semibold text-[#f7f8fa]">No hint generated</h3>
                  <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-[#a5afbd]">
                    Select a quest and request a level when the cooldown is ready.
                  </p>
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-[#222a33] bg-[#101419] p-5">
            <h2 className="text-base font-semibold text-[#f7f8fa]">Selected quest</h2>
            {selectedQuest && !useCustomQuestId ? (
              <div className="mt-4 space-y-3">
                <p className="text-sm font-semibold text-[#f7f8fa]">{selectedQuest.title}</p>
                <p className="text-sm leading-6 text-[#a5afbd]">{selectedQuest.description}</p>
                <div className="grid grid-cols-2 gap-3">
                  <FactTile label="Giver" value={selectedQuest.npc_slug} />
                  <FactTile label="Difficulty" value={selectedQuest.difficulty} />
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-[#a5afbd]">
                {useCustomQuestId ? "Using custom quest ID." : "No quest selected."}
              </p>
            )}
          </section>
        </aside>
      </section>
    </main>
  );
}

function Alert({
  tone,
  message,
  onDismiss,
}: {
  tone: "error" | "notice";
  message: string;
  onDismiss: () => void;
}) {
  const styles =
    tone === "error"
      ? "border-rose-500/25 bg-rose-500/10 text-rose-100"
      : "border-amber-500/25 bg-amber-500/10 text-amber-100";

  return (
    <div className={`mb-6 flex items-center justify-between gap-4 rounded-md border px-4 py-3 text-sm ${styles}`}>
      <span>{message}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded px-2 py-1 text-xs font-semibold transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
      >
        Dismiss
      </button>
    </div>
  );
}

function ProgressDots({ currentLevel }: { currentLevel: number }) {
  return (
    <div className="grid grid-cols-4 gap-2">
      {[0, 1, 2, 3].map((level) => (
        <div
          key={level}
          className={`rounded-md border px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.12em] ${
            level === currentLevel
              ? "border-[#8bdff0] bg-[#8bdff0] text-[#061014]"
              : level < currentLevel
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                : "border-[#222a33] bg-[#0b0f13] text-[#7c8794]"
          }`}
        >
          L{level}
        </div>
      ))}
    </div>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[#a5afbd]">{label}</span>
      <span className="max-w-40 truncate text-right text-sm font-semibold capitalize text-[#f7f8fa]">{value}</span>
    </div>
  );
}

function FactTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
      <p className="text-xs text-[#7c8794]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[#f7f8fa]">{value}</p>
    </div>
  );
}

function formatCooldown(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}
