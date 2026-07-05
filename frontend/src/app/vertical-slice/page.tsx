"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";

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
  id?: string;
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
  const [projectId, setProjectId] = useState("default_project");
  const [playerId, setPlayerId] = useState("default_player");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [npcs, setNpcs] = useState<NpcItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [selectedNpcSlug, setSelectedNpcSlug] = useState("");
  const [isLoadingSetup, setIsLoadingSetup] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [questLoading, setQuestLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [generatedQuest, setGeneratedQuest] = useState<Quest | null>(null);
  const [acceptedQuestId, setAcceptedQuestId] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState(1);
  const [hintText, setHintText] = useState<string | null>(null);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const [currentHintLevel, setCurrentHintLevel] = useState(0);
  const [rawPayload, setRawPayload] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    const fetchOptions = async () => {
      setIsLoadingSetup(true);
      setError(null);

      try {
        const headers = { "X-Game-Project-ID": projectId };
        const [docsRes, npcsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/documents`, { headers, signal: abortController.signal }),
          fetch(`${API_BASE_URL}/api/v1/npcs`, { headers, signal: abortController.signal }),
        ]);

        if (!docsRes.ok) throw new Error("Documents could not be loaded for this project.");
        if (!npcsRes.ok) throw new Error("NPCs could not be loaded for this project.");

        const docsData: DocumentItem[] = await docsRes.json();
        const npcsData: NpcItem[] = await npcsRes.json();

        if (!abortController.signal.aborted) {
          setDocuments(docsData);
          setNpcs(npcsData);
          setSelectedDocId((current) => current || docsData[0]?.id || "");
          setSelectedNpcSlug((current) => current || npcsData[0]?.slug || "");
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        const message = err instanceof Error ? err.message : "Runtime setup could not be loaded.";
        if (!abortController.signal.aborted) setError(message);
      } finally {
        if (!abortController.signal.aborted) setIsLoadingSetup(false);
      }
    };

    void Promise.resolve().then(fetchOptions);

    return () => abortController.abort();
  }, [projectId]);

  useEffect(() => {
    if (cooldownRemaining <= 0) return;

    const timer = window.setInterval(() => {
      setCooldownRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [cooldownRemaining]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocId) ?? null,
    [documents, selectedDocId]
  );

  const selectedNpc = useMemo(
    () => npcs.find((npc) => npc.slug === selectedNpcSlug) ?? null,
    [npcs, selectedNpcSlug]
  );

  const setupReady = Boolean(selectedDocument && selectedNpc);
  const hasDialogue = chatHistory.some((message) => message.sender === "npc");
  const runState = acceptedQuestId ? "Quest active" : generatedQuest ? "Quest generated" : hasDialogue ? "Dialogue ready" : "Setup";

  const resetSession = () => {
    setConversationId(null);
    setChatHistory([]);
    setGeneratedQuest(null);
    setAcceptedQuestId(null);
    setHintText(null);
    setCooldownRemaining(0);
    setCurrentHintLevel(0);
    setRawPayload(null);
    setError(null);
  };

  const sendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!messageInput.trim() || !selectedNpcSlug) return;

    const playerMessage = messageInput.trim();
    const nextHistory: ChatMessage[] = [
      ...chatHistory,
      {
        sender: "player",
        text: playerMessage,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ];

    setMessageInput("");
    setChatHistory(nextHistory);
    setIsSending(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/dialogue/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Game-Project-ID": projectId,
          "X-Player-ID": playerId,
        },
        body: JSON.stringify({
          npc_slug: selectedNpcSlug,
          player_message: playerMessage,
          player_id: playerId,
          conversation_id: conversationId || undefined,
          prompt_version: "v1",
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Dialogue request failed.");
      }

      const data = await res.json();
      setRawPayload(data);
      if (data.conversation_id) setConversationId(data.conversation_id);

      setChatHistory([
        ...nextHistory,
        {
          sender: "npc",
          text: data.response_text,
          suggested_animation: data.suggested_animation,
          emotions: data.npc_emotions,
          citations: data.citations,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "NPC dialogue could not be generated.";
      setError(message);
    } finally {
      setIsSending(false);
    }
  };

  const generateQuest = async () => {
    if (!selectedNpcSlug) return;
    setQuestLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/quests/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Game-Project-ID": projectId,
          "X-Player-ID": playerId,
        },
        body: JSON.stringify({
          npc_slug: selectedNpcSlug,
          player_id: playerId,
          player_level: 5,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Quest generation failed.");
      }

      const data = await res.json();
      setGeneratedQuest(data);
      setAcceptedQuestId(null);
      setHintText(null);
      setRawPayload(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Quest narrative could not be generated.";
      setError(message);
    } finally {
      setQuestLoading(false);
    }
  };

  const acceptQuest = async () => {
    if (!generatedQuest) return;
    setQuestLoading(true);
    setError(null);

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/quests`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          npc_slug: generatedQuest.npc_slug,
          title: generatedQuest.title,
          description: generatedQuest.description,
          difficulty: generatedQuest.difficulty,
          gold_reward: generatedQuest.rewards.gold,
          xp_reward: generatedQuest.rewards.xp,
          item_rewards: generatedQuest.rewards.items,
          objectives: generatedQuest.objectives.map((objective) => ({
            objective_index: objective.objective_index,
            description: objective.description,
            target_type: objective.target_type,
            target_id: objective.target_id,
            quantity_required: objective.quantity_required,
          })),
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Generated quest could not be registered.");
      }

      const createdQuest = await res.json();

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
        throw new Error(errData.detail || "Quest progress could not be started.");
      }

      setAcceptedQuestId(createdQuest.id);
      setRawPayload(createdQuest);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Quest could not be accepted.";
      setError(message);
    } finally {
      setQuestLoading(false);
    }
  };

  const requestHint = async () => {
    if (!acceptedQuestId) return;
    setHintLoading(true);
    setError(null);

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Game-Project-ID": projectId,
        "X-Player-ID": playerId,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/hints/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          quest_id: acceptedQuestId,
          player_id: playerId,
          hint_level: hintLevel,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Hint could not be generated.");
      }

      const data = await res.json();
      setHintText(data.hint);
      setRawPayload(data);

      const statusRes = await fetch(
        `${API_BASE_URL}/api/v1/hints/status?quest_id=${acceptedQuestId}&player_id=${playerId}`,
        { headers }
      );

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setCooldownRemaining(statusData.cooldown_remaining_seconds);
        setCurrentHintLevel(statusData.current_level);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Hint request failed.";
      setError(message);
    } finally {
      setHintLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl pb-14">
      <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-12">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c8794]">
            Narrative Simulator
          </p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#f7f8fa] sm:text-5xl">
            Play through the AI narrative loop.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[#a5afbd]">
            Test the exact MVP path a Unity scene needs: grounded NPC dialogue, quest generation, quest acceptance,
            and progressive hints.
          </p>
        </div>

        <aside className="self-start rounded-lg border border-[#222a33] bg-[#101419] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.22)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c8794]">Current run</p>
              <h2 className="mt-3 text-lg font-semibold text-[#f7f8fa]">{runState}</h2>
            </div>
            <StatusPill ready={setupReady && !isLoadingSetup} label={setupReady ? "Ready" : "Setup"} />
          </div>
          <div className="mt-5 divide-y divide-[#222a33]">
            <FactRow label="Document" value={selectedDocument?.title ?? "Missing"} />
            <FactRow label="NPC" value={selectedNpc?.name ?? "Missing"} />
            <FactRow label="Messages" value={String(chatHistory.length)} />
            <FactRow label="Hint level" value={`${currentHintLevel} / 3`} />
          </div>
          <button
            type="button"
            onClick={resetSession}
            className="mt-5 inline-flex min-h-10 w-full items-center justify-center rounded-md border border-[#303a46] px-4 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
          >
            Reset session
          </button>
        </aside>
      </section>

      {error && (
        <div className="mb-6 flex items-center justify-between gap-4 rounded-md border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="rounded px-2 py-1 text-xs font-semibold text-rose-100 transition hover:bg-rose-500/10 focus:outline-none focus:ring-2 focus:ring-rose-300"
          >
            Dismiss
          </button>
        </div>
      )}

      <section className="rounded-lg border border-[#222a33] bg-[#101419]">
        <div className="grid gap-0 lg:grid-cols-2">
          <SetupSelect
            label="Lore source"
            value={selectedDocId}
            onChange={setSelectedDocId}
            emptyText="Upload a document before running dialogue."
            emptyHref="/knowledge"
            emptyAction="Open Knowledge"
            disabled={isLoadingSetup}
            options={documents.map((doc) => ({
              value: doc.id,
              label: `${doc.title} (${doc.chunks_count} chunks)`,
            }))}
          />
          <SetupSelect
            label="NPC"
            value={selectedNpcSlug}
            onChange={setSelectedNpcSlug}
            emptyText="Create or materialize an NPC before playtesting."
            emptyHref="/npcs"
            emptyAction="Open NPC Studio"
            disabled={isLoadingSetup}
            options={npcs.map((npc) => ({
              value: npc.slug,
              label: `${npc.name}${npc.title ? `, ${npc.title}` : ""}`,
            }))}
          />
        </div>
        <details className="border-t border-[#222a33] px-5 py-4">
          <summary className="cursor-pointer text-sm font-semibold text-[#a5afbd] transition hover:text-[#f7f8fa]">
            Project and player scope
          </summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Project ID" value={projectId} onChange={setProjectId} />
            <Field label="Player ID" value={playerId} onChange={setPlayerId} />
          </div>
        </details>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-h-[36rem] flex-col rounded-lg border border-[#222a33] bg-[#101419]">
          <div className="flex items-center justify-between border-b border-[#222a33] px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-[#f7f8fa]">Dialogue playtest</h2>
              <p className="mt-1 text-xs text-[#7c8794]">
                Ask the selected NPC about the world, quest, faction, or current objective.
              </p>
            </div>
            <StatusPill ready={Boolean(conversationId || chatHistory.length)} label={conversationId ? "Live" : "Idle"} />
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {chatHistory.length === 0 ? (
              <div className="flex h-full min-h-80 items-center justify-center text-center">
                <div className="max-w-sm">
                  <h3 className="text-sm font-semibold text-[#f7f8fa]">Start the conversation</h3>
                  <p className="mt-2 text-sm leading-6 text-[#a5afbd]">
                    Try asking who the NPC is, what the player should do next, or what danger exists nearby.
                  </p>
                </div>
              </div>
            ) : (
              chatHistory.map((message, index) => (
                <ChatBubble key={`${message.timestamp}-${index}`} message={message} />
              ))
            )}
            {isSending && (
              <div className="mr-auto max-w-[82%] rounded-lg border border-[#222a33] bg-[#0b0f13] px-4 py-3 text-sm text-[#a5afbd]">
                {selectedNpc?.name ?? "NPC"} is responding...
              </div>
            )}
          </div>

          <form onSubmit={sendMessage} className="border-t border-[#222a33] p-4">
            <label className="sr-only" htmlFor="dialogue-message">
              Message to NPC
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                id="dialogue-message"
                type="text"
                value={messageInput}
                onChange={(event) => setMessageInput(event.target.value)}
                placeholder={setupReady ? `Ask ${selectedNpc?.name ?? "the NPC"} something...` : "Complete setup first"}
                disabled={isSending || !setupReady}
                className="min-h-11 flex-1 rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20 disabled:cursor-not-allowed disabled:opacity-55"
              />
              <button
                type="submit"
                disabled={isSending || !messageInput.trim() || !setupReady}
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#f7f8fa] px-5 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#101419] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </div>
          </form>
        </div>

        <aside className="space-y-6">
          <QuestPanel
            quest={generatedQuest}
            acceptedQuestId={acceptedQuestId}
            loading={questLoading}
            disabled={!selectedNpcSlug}
            onGenerate={generateQuest}
            onAccept={acceptQuest}
          />

          <HintPanel
            acceptedQuestId={acceptedQuestId}
            hintLevel={hintLevel}
            setHintLevel={setHintLevel}
            hintText={hintText}
            cooldownRemaining={cooldownRemaining}
            currentHintLevel={currentHintLevel}
            loading={hintLoading}
            onRequest={requestHint}
          />

          <details className="rounded-lg border border-[#222a33] bg-[#101419]">
            <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-[#f7f8fa] transition hover:bg-[#121922]">
              Structured payload
            </summary>
            <div className="max-h-80 overflow-y-auto border-t border-[#222a33] bg-[#0b0f13] p-4">
              {rawPayload ? (
                <pre className="whitespace-pre-wrap text-xs leading-5 text-[#a5afbd]">
                  {JSON.stringify(rawPayload, null, 2)}
                </pre>
              ) : (
                <p className="text-sm leading-6 text-[#7c8794]">
                  Send dialogue, generate a quest, or request a hint to inspect the runtime JSON.
                </p>
              )}
            </div>
          </details>
        </aside>
      </section>
    </main>
  );
}

function SetupSelect({
  label,
  value,
  onChange,
  options,
  emptyText,
  emptyHref,
  emptyAction,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  emptyText: string;
  emptyHref: string;
  emptyAction: string;
  disabled: boolean;
}) {
  return (
    <div className="border-b border-[#222a33] p-5 lg:border-b-0 lg:border-r last:border-r-0">
      <label className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7c8794]">{label}</label>
      {options.length === 0 ? (
        <div className="mt-3 rounded-md border border-[#222a33] bg-[#0b0f13] p-4">
          <p className="text-sm leading-6 text-[#a5afbd]">{emptyText}</p>
          <Link
            href={emptyHref}
            className="mt-3 inline-flex min-h-9 items-center rounded-md border border-[#303a46] px-3 text-xs font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
          >
            {emptyAction}
          </Link>
        </div>
      ) : (
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          className="mt-3 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20 disabled:cursor-not-allowed disabled:opacity-55"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-[#a5afbd]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
      />
    </label>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isPlayer = message.sender === "player";

  return (
    <article className={`flex ${isPlayer ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[86%] rounded-lg border px-4 py-3 ${
          isPlayer
            ? "border-[#34505b] bg-[#10212a] text-[#f7f8fa]"
            : "border-[#222a33] bg-[#0b0f13] text-[#f7f8fa]"
        }`}
      >
        <div className="mb-2 flex items-center justify-between gap-4 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7c8794]">
          <span>{isPlayer ? "Player" : "NPC"}</span>
          <span>{message.timestamp}</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.text}</p>

        {!isPlayer && (message.suggested_animation || message.emotions || message.citations?.length) && (
          <details className="mt-3 border-t border-[#222a33] pt-3">
            <summary className="cursor-pointer text-xs font-semibold text-[#8bdff0] transition hover:text-[#a6edfa]">
              Runtime metadata
            </summary>
            <div className="mt-3 space-y-3">
              {message.suggested_animation && (
                <FactRow label="Suggested animation" value={message.suggested_animation} />
              )}
              {message.emotions && (
                <div className="space-y-2">
                  {Object.entries(message.emotions).map(([emotion, value]) => (
                    <div key={emotion}>
                      <div className="flex justify-between text-xs text-[#a5afbd]">
                        <span className="capitalize">{emotion}</span>
                        <span>{Math.round(value * 100)}%</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#1a212a]">
                        <div className="h-full rounded-full bg-[#8bdff0]" style={{ width: `${value * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {message.citations && message.citations.length > 0 && (
                <div className="space-y-2">
                  {message.citations.map((citation) => (
                    <div key={citation.chunk_id} className="rounded-md border border-[#222a33] bg-[#090d11] p-3">
                      <div className="flex justify-between gap-3 text-xs">
                        <span className="font-semibold text-[#f7f8fa]">{citation.title}</span>
                        <span className="text-[#8bdff0]">{Math.round(citation.similarity * 100)}%</span>
                      </div>
                      <p className="mt-2 break-all text-[10px] leading-4 text-[#7c8794]">Chunk: {citation.chunk_id}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </details>
        )}
      </div>
    </article>
  );
}

function QuestPanel({
  quest,
  acceptedQuestId,
  loading,
  disabled,
  onGenerate,
  onAccept,
}: {
  quest: Quest | null;
  acceptedQuestId: string | null;
  loading: boolean;
  disabled: boolean;
  onGenerate: () => void;
  onAccept: () => void;
}) {
  return (
    <section className="rounded-lg border border-[#222a33] bg-[#101419]">
      <div className="border-b border-[#222a33] px-5 py-4">
        <h2 className="text-base font-semibold text-[#f7f8fa]">Quest</h2>
        <p className="mt-1 text-xs text-[#7c8794]">Generate a contextual objective and register it for the player.</p>
      </div>
      <div className="p-5">
        {!quest ? (
          <div>
            <p className="text-sm leading-6 text-[#a5afbd]">
              No quest is active. Generate one after selecting the NPC and source document.
            </p>
            <button
              type="button"
              onClick={onGenerate}
              disabled={loading || disabled}
              className="mt-5 inline-flex min-h-10 w-full items-center justify-center rounded-md bg-[#8bdff0] px-4 text-sm font-semibold text-[#061014] transition hover:bg-[#a6edfa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] focus:ring-offset-2 focus:ring-offset-[#101419] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Generating..." : "Generate quest"}
            </button>
          </div>
        ) : (
          <div>
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-sm font-semibold leading-6 text-[#f7f8fa]">{quest.title}</h3>
              <span className="rounded-full border border-[#27303a] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8bdff0]">
                {quest.difficulty}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-[#a5afbd]">{quest.description}</p>
            <div className="mt-4 space-y-2">
              {quest.objectives.map((objective) => (
                <div key={`${objective.objective_index}-${objective.description}`} className="rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
                  <p className="text-sm leading-6 text-[#f7f8fa]">{objective.description}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <FactTile label="Gold" value={String(quest.rewards.gold)} />
              <FactTile label="XP" value={String(quest.rewards.xp)} />
            </div>
            {acceptedQuestId ? (
              <div className="mt-5 rounded-md border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-center text-sm font-semibold text-emerald-200">
                Quest accepted
              </div>
            ) : (
              <button
                type="button"
                onClick={onAccept}
                disabled={loading}
                className="mt-5 inline-flex min-h-10 w-full items-center justify-center rounded-md bg-[#f7f8fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#101419] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Accepting..." : "Accept quest"}
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function HintPanel({
  acceptedQuestId,
  hintLevel,
  setHintLevel,
  hintText,
  cooldownRemaining,
  currentHintLevel,
  loading,
  onRequest,
}: {
  acceptedQuestId: string | null;
  hintLevel: number;
  setHintLevel: (level: number) => void;
  hintText: string | null;
  cooldownRemaining: number;
  currentHintLevel: number;
  loading: boolean;
  onRequest: () => void;
}) {
  return (
    <section className="rounded-lg border border-[#222a33] bg-[#101419]">
      <div className="border-b border-[#222a33] px-5 py-4">
        <h2 className="text-base font-semibold text-[#f7f8fa]">Progressive hints</h2>
        <p className="mt-1 text-xs text-[#7c8794]">Escalate from subtle guidance to direct help.</p>
      </div>
      <div className="p-5">
        {!acceptedQuestId ? (
          <p className="text-sm leading-6 text-[#a5afbd]">Accept a quest before requesting hints.</p>
        ) : (
          <div>
            <div className="grid grid-cols-3 gap-2">
              {[1, 2, 3].map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setHintLevel(level)}
                  className={`min-h-10 rounded-md border text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0] ${
                    hintLevel === level
                      ? "border-[#8bdff0] bg-[#8bdff0] text-[#061014]"
                      : "border-[#27303a] text-[#a5afbd] hover:border-[#4a5563] hover:bg-[#151b22]"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={onRequest}
              disabled={loading || cooldownRemaining > 0}
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-md bg-[#f7f8fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#101419] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {cooldownRemaining > 0 ? `Cooldown ${cooldownRemaining}s` : loading ? "Requesting..." : "Request hint"}
            </button>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <FactTile label="Current level" value={`${currentHintLevel} / 3`} />
              <FactTile label="Cooldown" value={cooldownRemaining > 0 ? `${cooldownRemaining}s` : "Ready"} />
            </div>
            {hintText && (
              <div className="mt-4 rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7c8794]">Hint</p>
                <p className="mt-2 text-sm leading-6 text-[#f7f8fa]">{hintText}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function StatusPill({ ready, label }: { ready: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
        ready ? "bg-emerald-500/10 text-emerald-300" : "bg-[#1a212a] text-[#7c8794]"
      }`}
    >
      {label}
    </span>
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
    <div className="rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
      <p className="text-xs text-[#7c8794]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[#f7f8fa]">{value}</p>
    </div>
  );
}
