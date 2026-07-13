"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, NPCProfile, NPCProfileCreate, NPCProfileUpdate } from "@/lib/api";

type FormMode = "create" | "edit";

interface NpcFormState {
  slug: string;
  name: string;
  title: string;
  personality_summary: string;
  dialogue_style: string;
  voice_profile: string;
  faction_alignment: string;
}

const emptyForm: NpcFormState = {
  slug: "",
  name: "",
  title: "",
  personality_summary: "",
  dialogue_style: "",
  voice_profile: "",
  faction_alignment: "",
};

const malformedNamePrefixes = [
  "the story",
  "story ",
  "section ",
  "project ",
  "version ",
  "quest ",
  "objective ",
  "players ",
  "visual ",
  "level ",
  "game ",
  "faction ",
  "memory ",
  "narrative ",
  "art style",
  "unity ",
];

function isLikelyGeneratedFragment(npc: NPCProfile) {
  const name = npc.name.trim().toLowerCase();
  const slug = npc.slug.trim().toLowerCase();
  const personality = npc.personality_summary.trim().toLowerCase();
  const wordCount = npc.name.trim().split(/\s+/u).filter(Boolean).length;

  return (
    malformedNamePrefixes.some((prefix) => name.startsWith(prefix)) ||
    npc.name.includes("**") ||
    slug.startsWith("--") ||
    (personality === "extracted profile" && !npc.dialogue_style) ||
    (wordCount > 4 && !npc.dialogue_style && !npc.title)
  );
}

export default function NPCStudioPage() {
  const [npcs, setNpcs] = useState<NPCProfile[]>([]);
  const [selectedNpcId, setSelectedNpcId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFaction, setSelectedFaction] = useState("all");
  const [showReviewItems, setShowReviewItems] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingNpcId, setEditingNpcId] = useState<string | null>(null);
  const [form, setForm] = useState<NpcFormState>(emptyForm);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [deletingNpc, setDeletingNpc] = useState<NPCProfile | null>(null);

  const loadNpcs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const list = await api.getNPCs();
      setNpcs(list);
      setSelectedNpcId((current) => {
        if (current && list.some((npc) => npc.id === current)) return current;
        return list.find((npc) => !isLikelyGeneratedFragment(npc))?.id ?? list[0]?.id ?? null;
      });
    } catch (err) {
      console.error("Failed to load NPCs:", err);
      setError("NPC profiles could not be loaded. Check that the backend is running.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadNpcs);
  }, [loadNpcs]);

  const playableNpcs = useMemo(() => npcs.filter((npc) => !isLikelyGeneratedFragment(npc)), [npcs]);
  const reviewNpcs = useMemo(() => npcs.filter(isLikelyGeneratedFragment), [npcs]);
  const visibleNpcs = showReviewItems ? npcs : playableNpcs;

  const factions = useMemo(
    () =>
      Array.from(
        new Set(
          playableNpcs
            .map((npc) => npc.faction_alignment?.trim())
            .filter((faction): faction is string => Boolean(faction))
        )
      ).sort(),
    [playableNpcs]
  );

  const filteredNpcs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return visibleNpcs.filter((npc) => {
      const matchesQuery =
        !query ||
        npc.name.toLowerCase().includes(query) ||
        npc.slug.toLowerCase().includes(query) ||
        (npc.title ?? "").toLowerCase().includes(query);

      const matchesFaction =
        selectedFaction === "all" ||
        (selectedFaction === "none" && !npc.faction_alignment) ||
        npc.faction_alignment === selectedFaction;

      return matchesQuery && matchesFaction;
    });
  }, [searchQuery, selectedFaction, visibleNpcs]);

  const selectedNpc = useMemo(
    () => filteredNpcs.find((npc) => npc.id === selectedNpcId) ?? filteredNpcs[0] ?? null,
    [filteredNpcs, selectedNpcId]
  );

  const runtimeReadyCount = playableNpcs.filter((npc) => npc.personality_summary && npc.dialogue_style).length;

  const openCreateForm = () => {
    setForm(emptyForm);
    setFormMode("create");
    setEditingNpcId(null);
    setValidationErrors({});
    setError(null);
    setSuccess(null);
    setFormOpen(true);
  };

  const openEditForm = (npc: NPCProfile) => {
    setForm({
      slug: npc.slug,
      name: npc.name,
      title: npc.title ?? "",
      personality_summary: npc.personality_summary,
      dialogue_style: npc.dialogue_style ?? "",
      voice_profile: npc.voice_profile ?? "",
      faction_alignment: npc.faction_alignment ?? "",
    });
    setFormMode("edit");
    setEditingNpcId(npc.id);
    setValidationErrors({});
    setError(null);
    setSuccess(null);
    setFormOpen(true);
  };

  const updateForm = (field: keyof NpcFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setValidationErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  };

  const validateForm = () => {
    const errors: Record<string, string> = {};

    if (formMode === "create") {
      if (!form.slug.trim()) {
        errors.slug = "Slug is required.";
      } else if (!/^[a-z0-9_-]{3,100}$/.test(form.slug.trim())) {
        errors.slug = "Use 3-100 lowercase letters, numbers, underscores, or hyphens.";
      }
    }

    if (!form.name.trim()) errors.name = "Name is required.";
    if (!form.personality_summary.trim()) errors.personality_summary = "Personality summary is required.";

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const saveNpc = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!validateForm()) return;

    setIsSaving(true);

    try {
      if (formMode === "create") {
        const payload: NPCProfileCreate = {
          slug: form.slug.trim(),
          name: form.name.trim(),
          title: form.title.trim() || undefined,
          personality_summary: form.personality_summary.trim(),
          dialogue_style: form.dialogue_style.trim() || undefined,
          voice_profile: form.voice_profile.trim() || undefined,
          faction_alignment: form.faction_alignment.trim() || undefined,
        };

        const created = await api.createNPC(payload);
        setSelectedNpcId(created.id);
        setSuccess(`${created.name} is ready for runtime testing.`);
      } else if (editingNpcId) {
        const payload: NPCProfileUpdate = {
          name: form.name.trim(),
          title: form.title.trim() || undefined,
          personality_summary: form.personality_summary.trim(),
          dialogue_style: form.dialogue_style.trim() || undefined,
          voice_profile: form.voice_profile.trim() || undefined,
          faction_alignment: form.faction_alignment.trim() || undefined,
        };

        const updated = await api.updateNPC(editingNpcId, payload);
        setSelectedNpcId(updated.id);
        setSuccess(`${updated.name} was updated.`);
      }

      setFormOpen(false);
      await loadNpcs();
    } catch (err) {
      const message = err instanceof Error ? err.message : "NPC profile could not be saved.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deletingNpc) return;
    setError(null);
    setSuccess(null);

    try {
      await api.deleteNPC(deletingNpc.id);
      setSuccess(`${deletingNpc.name} was removed from the active roster.`);
      setDeletingNpc(null);
      await loadNpcs();
    } catch (err) {
      console.error("Failed to delete NPC:", err);
      setError("NPC profile could not be deleted.");
      setDeletingNpc(null);
    }
  };

  return (
    <main className="page-shell">
      <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-12">
        <div className="max-w-3xl">
          <p className="page-kicker">NPC Studio</p>
          <h1 className="display-title mt-5 text-[2.05rem] leading-tight sm:text-[2.85rem]">
            Tune the characters your blueprint created.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
            Use this as a supporting workspace after blueprint generation. Keep each NPC short, playable, and grounded:
            role, personality, faction, and dialogue direction are enough for the runtime test.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={openCreateForm}
              className="btn-primary"
            >
              Create NPC
            </button>
            {selectedNpc && (
              <button
                type="button"
                onClick={() => openEditForm(selectedNpc)}
                className="btn-secondary"
              >
                Edit selected
              </button>
            )}
            <Link href="/blueprints" className="btn-secondary">
              Back to blueprints
            </Link>
          </div>
        </div>

        <aside className="panel self-start rounded-xl p-5">
          <p className="mono-label text-[var(--text-secondary)]">Roster health</p>
          <div className="mt-5 divide-y divide-[var(--border)]">
            <FactRow label="Playable NPCs" value={isLoading ? "--" : String(playableNpcs.length)} />
            <FactRow label="Factions" value={isLoading ? "--" : String(factions.length)} />
            <FactRow label="Dialogue ready" value={isLoading ? "--" : String(runtimeReadyCount)} />
            <FactRow label="Needs review" value={isLoading ? "--" : String(reviewNpcs.length)} />
          </div>
          <p className="mt-5 rounded-md border border-[var(--border)] bg-[var(--card)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
            MVP rule: one strong quest giver and one opposing character are more useful than a large unfinished cast.
            Suspicious extracted fragments are hidden from the playable roster until reviewed.
          </p>
        </aside>
      </section>

      {error && <Alert tone="error" message={error} />}
      {success && <Alert tone="success" message={success} />}

      <section className="mt-8 grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="panel overflow-hidden rounded-xl">
          <div className="border-b border-[var(--border)] p-4">
            <label className="sr-only" htmlFor="npc-search">
              Search NPCs
            </label>
            <input
              id="npc-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by name, title, or slug..."
              className="min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
            />
            <label className="sr-only" htmlFor="faction-filter">
              Filter by faction
            </label>
            <select
              id="faction-filter"
              value={selectedFaction}
              onChange={(event) => setSelectedFaction(event.target.value)}
              className="mt-3 min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
            >
              <option value="all">All factions</option>
              <option value="none">No faction</option>
              {factions.map((faction) => (
                <option key={faction} value={faction}>
                  {faction}
                </option>
              ))}
            </select>
            {reviewNpcs.length > 0 && (
              <button
                type="button"
                onClick={() => setShowReviewItems((current) => !current)}
                className="mt-3 flex min-h-11 w-full items-center justify-between rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-left text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
                aria-pressed={showReviewItems}
              >
                <span>{showReviewItems ? "Hide review items" : "Show review items"}</span>
                <span className="rounded-full bg-[var(--accent-soft)] px-2 py-1 text-[10px] uppercase tracking-normal text-[var(--accent)]">
                  {reviewNpcs.length}
                </span>
              </button>
            )}
          </div>

          <div className="max-h-[34rem] overflow-y-auto">
            {isLoading ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-20 animate-pulse rounded-md bg-[var(--card-muted)]" />
                ))}
              </div>
            ) : filteredNpcs.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <h2 className="text-sm font-semibold text-[var(--foreground)]">No NPCs found</h2>
                <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-[var(--text-secondary)]">
                  {reviewNpcs.length > 0 && !showReviewItems
                    ? "Only review items match this workspace right now. Show review items or create a clean NPC."
                    : "Create a character or clear the current filters."}
                </p>
                <button
                  type="button"
                  onClick={openCreateForm}
                  className="mt-5 inline-flex min-h-10 items-center justify-center rounded-md bg-[var(--foreground)] px-4 text-sm font-semibold text-[var(--card)] transition hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--foreground)] focus:ring-offset-2 focus:ring-offset-[var(--background)]"
                >
                  Create NPC
                </button>
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {filteredNpcs.map((npc) => {
                  const active = selectedNpc?.id === npc.id;
                  const needsReview = isLikelyGeneratedFragment(npc);

                  return (
                    <button
                      key={npc.id}
                      type="button"
                      onClick={() => setSelectedNpcId(npc.id)}
                      className={`w-full px-4 py-4 text-left transition focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[var(--accent)] ${
                        active ? "bg-[var(--card-muted)]" : "hover:bg-[var(--card-muted)]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-[var(--foreground)]">{npc.name}</h3>
                          <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">{npc.title || npc.slug}</p>
                        </div>
                        <span className="rounded-full border border-[var(--border-strong)] px-2 py-1 text-[10px] font-semibold uppercase tracking-normal text-[var(--accent)]">
                          {needsReview ? "Review" : npc.faction_alignment || "Solo"}
                        </span>
                      </div>
                      <p className="mt-3 line-clamp-2 text-sm leading-6 text-[var(--text-secondary)]">{npc.personality_summary}</p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="panel overflow-hidden rounded-xl">
          {selectedNpc ? (
            <div>
              <div className="flex flex-col gap-4 border-b border-[var(--border)] p-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="mono-label text-[var(--text-secondary)]">
                    {selectedNpc.slug}
                  </p>
                  <h2 className="mt-3 font-display text-4xl font-semibold text-[var(--foreground)]">{selectedNpc.name}</h2>
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">{selectedNpc.title || "Untitled character"}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openEditForm(selectedNpc)}
                    className="inline-flex min-h-10 items-center rounded-md border border-[var(--border-strong)] px-4 text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeletingNpc(selectedNpc)}
                    className="inline-flex min-h-10 items-center rounded-md border border-rose-500/25 px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-500/10 focus:outline-none focus:ring-2 focus:ring-rose-500/30"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_300px]">
                <div className="space-y-6 p-5">
                  <ProfileSection title="Personality" body={selectedNpc.personality_summary} />
                  <ProfileSection
                    title="Dialogue direction"
                    body={selectedNpc.dialogue_style || "No dialogue style has been defined yet."}
                  />
                  <ProfileSection
                    title="Voice profile"
                    body={selectedNpc.voice_profile || "No voice profile has been defined yet."}
                  />
                </div>

                <aside className="border-t border-[var(--border)] p-5 lg:border-l lg:border-t-0">
                  <h3 className="text-sm font-semibold text-[var(--foreground)]">Runtime readiness</h3>
                  <div className="mt-4 space-y-3">
                    <ReadinessItem label="Personality" ready={Boolean(selectedNpc.personality_summary)} />
                    <ReadinessItem label="Dialogue style" ready={Boolean(selectedNpc.dialogue_style)} />
                    <ReadinessItem label="Faction" ready={Boolean(selectedNpc.faction_alignment)} />
                    <ReadinessItem label="Memory settings" ready={Boolean(selectedNpc.memory_settings)} />
                  </div>
                  <div className="mt-6 rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
                    <p className="mono-label text-[var(--text-secondary)]">Faction</p>
                    <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
                      {selectedNpc.faction_alignment || "Unaligned"}
                    </p>
                  </div>
                </aside>
              </div>
            </div>
          ) : (
            <div className="px-5 py-16 text-center">
              <h2 className="text-sm font-semibold text-[var(--foreground)]">Select an NPC</h2>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[var(--text-secondary)]">
                Choose a character from the roster or create the first runtime-ready NPC.
              </p>
            </div>
          )}
        </div>
      </section>

      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 px-4 py-10 backdrop-blur-sm">
          <form
            onSubmit={saveNpc}
            className="panel w-full max-w-2xl rounded-xl"
          >
            <div className="border-b border-[var(--border-strong)] px-5 py-5">
              <p className="mono-label text-[var(--text-secondary)]">
                {formMode === "create" ? "Create character" : "Edit character"}
              </p>
              <h2 className="mt-2 font-display text-3xl font-semibold text-[var(--foreground)]">
                {formMode === "create" ? "Add an NPC to the runtime roster." : "Refine this NPC profile."}
              </h2>
            </div>

            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <Field
                label="Slug"
                value={form.slug}
                onChange={(value) => updateForm("slug", value)}
                error={validationErrors.slug}
                disabled={formMode === "edit"}
                placeholder="eldrin"
              />
              <Field
                label="Name"
                value={form.name}
                onChange={(value) => updateForm("name", value)}
                error={validationErrors.name}
                placeholder="Eldrin"
              />
              <Field
                label="Title"
                value={form.title}
                onChange={(value) => updateForm("title", value)}
                placeholder="Archivist of Frostpeak"
              />
              <Field
                label="Faction"
                value={form.faction_alignment}
                onChange={(value) => updateForm("faction_alignment", value)}
                placeholder="Frostpeak Resistance"
              />
              <Field
                label="Voice profile"
                value={form.voice_profile}
                onChange={(value) => updateForm("voice_profile", value)}
                placeholder="Calm, precise, wary"
                className="sm:col-span-2"
              />
              <TextArea
                label="Personality summary"
                value={form.personality_summary}
                onChange={(value) => updateForm("personality_summary", value)}
                error={validationErrors.personality_summary}
                placeholder="Describe what drives this character and how they behave in play."
              />
              <TextArea
                label="Dialogue style"
                value={form.dialogue_style}
                onChange={(value) => updateForm("dialogue_style", value)}
                placeholder="Define sentence style, tone, taboo topics, and how they guide the player."
              />
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-[var(--border-strong)] px-5 py-4 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="inline-flex min-h-10 items-center justify-center rounded-md border border-[var(--border-strong)] px-4 text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-[var(--foreground)] px-4 text-sm font-semibold text-[var(--card)] transition hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--foreground)] focus:ring-offset-2 focus:ring-offset-[var(--background)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSaving ? "Saving..." : formMode === "create" ? "Create NPC" : "Save changes"}
              </button>
            </div>
          </form>
        </div>
      )}

      {deletingNpc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="panel w-full max-w-md rounded-xl p-5">
            <h2 className="font-display text-3xl font-semibold text-[var(--foreground)]">Delete {deletingNpc.name}?</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              This removes the character from the active roster. Use this only when the NPC should no longer appear in
              runtime testing.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setDeletingNpc(null)}
                className="inline-flex min-h-10 items-center justify-center rounded-md border border-[var(--border-strong)] px-4 text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] hover:bg-[var(--card-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-rose-200 px-4 text-sm font-semibold text-rose-950 transition hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-500/30 focus:ring-offset-2 focus:ring-offset-[var(--background)]"
              >
                Delete NPC
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function Alert({ tone, message }: { tone: "error" | "success"; message: string }) {
  const styles =
    tone === "error"
      ? "border-rose-500/25 bg-rose-500/10 text-rose-800"
      : "border-emerald-500/25 bg-emerald-500/10 text-emerald-800";

  return <div role={tone === "error" ? "alert" : "status"} className={`mb-4 rounded-xl border px-4 py-3 text-sm ${styles}`}>{message}</div>;
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--foreground)]">{value}</span>
    </div>
  );
}

function ProfileSection({ title, body }: { title: string; body: string }) {
  return (
    <section>
      <h3 className="font-display text-2xl font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="mt-3 max-w-3xl whitespace-pre-wrap text-base leading-8 text-[var(--text-secondary)]">{body}</p>
    </section>
  );
}

function ReadinessItem({ label, ready }: { label: string; ready: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span
        className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-normal ${
          ready ? "bg-emerald-500/10 text-emerald-800" : "bg-[#e5edf3] text-[var(--text-secondary)]"
        }`}
      >
        {ready ? "Ready" : "Missing"}
      </span>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  error,
  placeholder,
  disabled,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs font-semibold text-[var(--text-secondary)]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="mt-2 min-h-11 w-full rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 text-sm text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-55"
      />
      {error && <span className="mt-2 block text-xs text-rose-700">{error}</span>}
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
  error,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
}) {
  return (
    <label className="block sm:col-span-2">
      <span className="text-xs font-semibold text-[var(--text-secondary)]">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={5}
        className="mt-2 w-full resize-y rounded-md border border-[var(--border-strong)] bg-[var(--card)] px-3 py-3 text-sm leading-6 text-[var(--foreground)] outline-none transition placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
      />
      {error && <span className="mt-2 block text-xs text-rose-700">{error}</span>}
    </label>
  );
}
