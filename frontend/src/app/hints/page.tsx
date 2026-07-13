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
    <main className="page-shell">
      <section className="flex flex-col gap-5 py-8 sm:py-10 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="page-kicker">Hint Studio</p>
          <h1 className="display-title mt-4 text-[2.05rem] leading-tight sm:text-[2.8rem]">
            Tune guidance without spoiling the game.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-[var(--text-secondary)]">
            Choose an active quest, decide how much help the player needs, and review the exact hint they will see.
          </p>
        </div>

        <aside className="panel w-full rounded-2xl p-5 lg:w-72">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="mono-label text-[var(--text-tertiary)]">Hint state</p>
              <p className="mt-1 text-sm font-semibold text-[var(--foreground)]">
                {cooldownSeconds > 0 ? "Cooldown active" : activeQuestId ? "Ready to guide" : "Choose a quest"}
              </p>
            </div>
            <span className="rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)]">
              Level {currentLevel}/3
            </span>
          </div>
          <div className="mt-4 divide-y divide-[var(--border)]">
            <FactRow label="Current level" value={`${currentLevel} / 3`} />
            <FactRow label="Cooldown" value={cooldownSeconds > 0 ? formatCooldown(cooldownSeconds) : "Ready"} />
          </div>
          <div className="mt-4">
            <ProgressDots currentLevel={currentLevel} />
          </div>
        </aside>
      </section>

      {error && <Alert tone="error" message={error} onDismiss={() => setError(null)} />}
      {notice && <Alert tone="notice" message={notice} onDismiss={() => setNotice(null)} />}

      <section className="grid gap-6 lg:grid-cols-[390px_minmax(0,1fr)]">
        <div className="panel overflow-hidden rounded-2xl">
          <div className="border-b border-[var(--border)] px-5 py-4">
            <p className="mono-label text-[var(--text-tertiary)]">01 / Configure</p>
            <h2 className="mt-1 font-display text-xl font-semibold text-[var(--foreground)]">Choose the next hint</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
              Start with the least revealing useful answer.
            </p>
          </div>

          <div className="space-y-5 p-5">
            <label className="block">
              <span className="text-xs font-semibold text-[var(--text-secondary)]">Player ID</span>
              <input
                type="text"
                value={playerId}
                onChange={(event) => setPlayerId(event.target.value)}
                className="mt-2 min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
              />
            </label>

            <div>
              <div className="flex items-center justify-between gap-4">
                <label className="text-xs font-semibold text-[var(--text-secondary)]" htmlFor="quest-select">
                  Quest
                </label>
                <button
                  type="button"
                  onClick={loadQuests}
                  className="rounded-md px-2 py-1 text-xs font-semibold text-[var(--accent)] transition hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  Reload
                </button>
              </div>

              {isLoadingQuests ? (
                <div className="mt-2 h-11 animate-pulse rounded-md bg-[var(--card-muted)]" />
              ) : quests.length === 0 && !useCustomQuestId ? (
                <div className="mt-2 rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
                  <p className="text-sm leading-6 text-[var(--text-secondary)]">
                    No quests are available yet. Generate and accept one in the simulator first.
                  </p>
                  <Link
                    href="/vertical-slice"
                    className="mt-3 inline-flex min-h-9 items-center rounded-md border border-[var(--border-strong)] px-3 text-xs font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
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
                  className="mt-2 min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {quests.map((quest) => (
                    <option key={quest.id} value={quest.id}>
                      {quest.title} ({quest.npc_slug})
                    </option>
                  ))}
                </select>
              )}
            </div>

            {selectedQuest && !useCustomQuestId && (
              <div className="panel-muted rounded-xl p-4">
                <p className="mono-label text-[var(--text-tertiary)]">Selected quest</p>
                <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">{selectedQuest.title}</p>
                <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                  Given by {selectedQuest.npc_slug} · {selectedQuest.difficulty}
                </p>
              </div>
            )}

            <details className="rounded-xl border border-[var(--border)] bg-[var(--card-muted)]">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-[var(--text-secondary)] transition hover:text-[var(--foreground)]">
                Use a custom quest ID
              </summary>
              <div className="space-y-3 border-t border-[var(--border)] p-4">
                <label className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
                  <input
                    type="checkbox"
                    checked={useCustomQuestId}
                    onChange={(event) => setUseCustomQuestId(event.target.checked)}
                    className="h-4 w-4 accent-[var(--accent)]"
                  />
                  Use a custom quest ID
                </label>
                <input
                  type="text"
                  value={customQuestId}
                  onChange={(event) => setCustomQuestId(event.target.value)}
                  disabled={!useCustomQuestId}
                  placeholder="Quest UUID"
                  className="min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>
            </details>

            <div>
              <p className="mono-label text-[var(--text-tertiary)]">02 / Guidance strength</p>
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
                    aria-pressed={hintLevel === item.level}
                    className={`min-h-24 rounded-xl border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
                      hintLevel === item.level
                        ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--card)]"
                        : "border-[var(--border-strong)] bg-[var(--card)] text-[var(--foreground)] hover:border-[var(--accent)] hover:bg-[var(--card-muted)]"
                    }`}
                  >
                    <span className="text-xs font-semibold uppercase tracking-normal">Level {item.level}</span>
                    <span className="mt-2 block text-sm font-semibold">{item.title}</span>
                    <span className={`mt-1 block text-xs leading-5 ${hintLevel === item.level ? "text-white/85" : "text-[var(--text-secondary)]"}`}>
                      {item.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-[var(--border)] pt-5 sm:flex-row">
              <button
                type="button"
                onClick={requestHint}
                disabled={!canRequest}
                className="btn-primary flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isGenerating ? "Requesting..." : cooldownSeconds > 0 ? `Ready in ${formatCooldown(cooldownSeconds)}` : "Request hint"}
              </button>
              <button
                type="button"
                onClick={() => syncStatus(false)}
                disabled={!activeQuestId || isCheckingStatus}
                className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isCheckingStatus ? "Syncing..." : "Sync"}
              </button>
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <section className="panel min-h-[28rem] overflow-hidden rounded-2xl">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <p className="mono-label text-[var(--text-tertiary)]">03 / Player-facing result</p>
              <h2 className="mt-1 font-display text-xl font-semibold text-[var(--foreground)]">The next hint</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">This is the exact text the player will receive.</p>
            </div>
            <div className="p-5">
              {generatedHint ? (
                <div>
                  <div className="mb-4 flex items-center gap-2">
                    <span className="rounded-full bg-[var(--accent)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-normal text-[var(--card)]">
                      Level {generatedHint.hint_level}
                    </span>
                    <span className="rounded-full border border-[var(--border-strong)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-normal text-[var(--text-secondary)]">
                      {generatedHint.spoiler_level}
                    </span>
                  </div>
                  <p className="rounded-xl border border-[var(--border)] bg-[var(--card-muted)] p-5 text-base leading-7 text-[var(--foreground)]">
                    {generatedHint.hint}
                  </p>
                </div>
              ) : (
                <div className="flex min-h-72 items-center justify-center py-10 text-center">
                  <div>
                  <h3 className="text-sm font-semibold text-[var(--foreground)]">No hint yet</h3>
                  <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-[var(--text-secondary)]">
                    Select an active quest, choose a strength, then request the next useful nudge.
                  </p>
                  </div>
                </div>
              )}
            </div>
          </section>

          <Link href="/vertical-slice" className="btn-secondary w-full">
            Open Runtime Test
          </Link>
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
      ? "border-rose-500/25 bg-rose-500/10 text-rose-800"
      : "border-amber-500/25 bg-amber-500/10 text-amber-800";

  return (
    <div role={tone === "error" ? "alert" : "status"} className={`mb-6 flex items-center justify-between gap-4 rounded-xl border px-4 py-3 text-sm ${styles}`}>
      <span>{message}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded px-2 py-1 text-xs font-semibold transition hover:bg-[var(--accent-hover)]/5 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
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
          className={`rounded-md border px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-normal ${
            level === currentLevel
              ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--card)]"
              : level < currentLevel
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-800"
                : "border-[var(--border)] bg-[var(--card)] text-[var(--text-secondary)]"
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
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span className="max-w-40 truncate text-right text-sm font-semibold capitalize text-[var(--foreground)]">{value}</span>
    </div>
  );
}

function formatCooldown(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}
