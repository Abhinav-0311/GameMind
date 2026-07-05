"use client";

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

export default function NPCStudioPage() {
  const [npcs, setNpcs] = useState<NPCProfile[]>([]);
  const [selectedNpcId, setSelectedNpcId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFaction, setSelectedFaction] = useState("all");
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
        return list[0]?.id ?? null;
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

  const factions = useMemo(
    () =>
      Array.from(
        new Set(
          npcs
            .map((npc) => npc.faction_alignment?.trim())
            .filter((faction): faction is string => Boolean(faction))
        )
      ).sort(),
    [npcs]
  );

  const filteredNpcs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return npcs.filter((npc) => {
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
  }, [npcs, searchQuery, selectedFaction]);

  const selectedNpc = useMemo(
    () => npcs.find((npc) => npc.id === selectedNpcId) ?? filteredNpcs[0] ?? null,
    [filteredNpcs, npcs, selectedNpcId]
  );

  const runtimeReadyCount = npcs.filter((npc) => npc.personality_summary && npc.dialogue_style).length;
  const memoryReadyCount = npcs.filter((npc) => npc.memory_settings && Object.keys(npc.memory_settings).length > 0).length;

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
    <main className="mx-auto max-w-6xl pb-14">
      <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-12">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7c8794]">NPC Studio</p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#f7f8fa] sm:text-5xl">
            Shape characters the runtime can actually use.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[#a5afbd]">
            Keep NPC profiles concise, grounded, and playable. Each character should have a clear role, personality,
            faction, and dialogue direction before it enters the Unity slice.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={openCreateForm}
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#f7f8fa] px-5 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#090b0e]"
            >
              Create NPC
            </button>
            {selectedNpc && (
              <button
                type="button"
                onClick={() => openEditForm(selectedNpc)}
                className="inline-flex min-h-11 items-center justify-center rounded-md border border-[#27303a] px-5 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#3b4654] hover:bg-[#12161b] focus:outline-none focus:ring-2 focus:ring-[#3b4654] focus:ring-offset-2 focus:ring-offset-[#090b0e]"
              >
                Edit selected
              </button>
            )}
          </div>
        </div>

        <aside className="self-start rounded-lg border border-[#222a33] bg-[#101419] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c8794]">Roster health</p>
          <div className="mt-5 divide-y divide-[#222a33]">
            <FactRow label="Active NPCs" value={isLoading ? "--" : String(npcs.length)} />
            <FactRow label="Factions" value={isLoading ? "--" : String(factions.length)} />
            <FactRow label="Dialogue ready" value={isLoading ? "--" : String(runtimeReadyCount)} />
            <FactRow label="Memory tuned" value={isLoading ? "--" : String(memoryReadyCount)} />
          </div>
          <p className="mt-5 rounded-md border border-[#222a33] bg-[#0b0f13] p-3 text-xs leading-5 text-[#a5afbd]">
            MVP rule: fewer strong characters beat a large unfocused cast. Start with one quest giver and one opposing
            faction character.
          </p>
        </aside>
      </section>

      {error && <Alert tone="error" message={error} />}
      {success && <Alert tone="success" message={success} />}

      <section className="mt-8 grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="rounded-lg border border-[#222a33] bg-[#101419]">
          <div className="border-b border-[#222a33] p-4">
            <label className="sr-only" htmlFor="npc-search">
              Search NPCs
            </label>
            <input
              id="npc-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by name, title, or slug..."
              className="min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
            />
            <label className="sr-only" htmlFor="faction-filter">
              Filter by faction
            </label>
            <select
              id="faction-filter"
              value={selectedFaction}
              onChange={(event) => setSelectedFaction(event.target.value)}
              className="mt-3 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
            >
              <option value="all">All factions</option>
              <option value="none">No faction</option>
              {factions.map((faction) => (
                <option key={faction} value={faction}>
                  {faction}
                </option>
              ))}
            </select>
          </div>

          <div className="max-h-[34rem] overflow-y-auto">
            {isLoading ? (
              <div className="space-y-3 p-4">
                {[1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-20 animate-pulse rounded-md bg-[#151b22]" />
                ))}
              </div>
            ) : filteredNpcs.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <h2 className="text-sm font-semibold text-[#f7f8fa]">No NPCs found</h2>
                <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-[#a5afbd]">
                  Create a character or clear the current filters.
                </p>
                <button
                  type="button"
                  onClick={openCreateForm}
                  className="mt-5 inline-flex min-h-10 items-center justify-center rounded-md bg-[#f7f8fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#101419]"
                >
                  Create NPC
                </button>
              </div>
            ) : (
              <div className="divide-y divide-[#222a33]">
                {filteredNpcs.map((npc) => {
                  const active = selectedNpc?.id === npc.id;

                  return (
                    <button
                      key={npc.id}
                      type="button"
                      onClick={() => setSelectedNpcId(npc.id)}
                      className={`w-full px-4 py-4 text-left transition focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8bdff0] ${
                        active ? "bg-[#151d25]" : "hover:bg-[#121922]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-[#f7f8fa]">{npc.name}</h3>
                          <p className="mt-1 truncate text-xs text-[#7c8794]">{npc.title || npc.slug}</p>
                        </div>
                        <span className="rounded-full border border-[#27303a] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8bdff0]">
                          {npc.faction_alignment || "Solo"}
                        </span>
                      </div>
                      <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#a5afbd]">{npc.personality_summary}</p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-[#222a33] bg-[#101419]">
          {selectedNpc ? (
            <div>
              <div className="flex flex-col gap-4 border-b border-[#222a33] p-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c8794]">
                    {selectedNpc.slug}
                  </p>
                  <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[#f7f8fa]">{selectedNpc.name}</h2>
                  <p className="mt-2 text-sm text-[#a5afbd]">{selectedNpc.title || "Untitled character"}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openEditForm(selectedNpc)}
                    className="inline-flex min-h-10 items-center rounded-md border border-[#303a46] px-4 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeletingNpc(selectedNpc)}
                    className="inline-flex min-h-10 items-center rounded-md border border-rose-500/25 px-4 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/10 focus:outline-none focus:ring-2 focus:ring-rose-300"
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

                <aside className="border-t border-[#222a33] p-5 lg:border-l lg:border-t-0">
                  <h3 className="text-sm font-semibold text-[#f7f8fa]">Runtime readiness</h3>
                  <div className="mt-4 space-y-3">
                    <ReadinessItem label="Personality" ready={Boolean(selectedNpc.personality_summary)} />
                    <ReadinessItem label="Dialogue style" ready={Boolean(selectedNpc.dialogue_style)} />
                    <ReadinessItem label="Faction" ready={Boolean(selectedNpc.faction_alignment)} />
                    <ReadinessItem label="Memory settings" ready={Boolean(selectedNpc.memory_settings)} />
                  </div>
                  <div className="mt-6 rounded-md border border-[#222a33] bg-[#0b0f13] p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7c8794]">Faction</p>
                    <p className="mt-2 text-sm font-semibold text-[#f7f8fa]">
                      {selectedNpc.faction_alignment || "Unaligned"}
                    </p>
                  </div>
                </aside>
              </div>
            </div>
          ) : (
            <div className="px-5 py-16 text-center">
              <h2 className="text-sm font-semibold text-[#f7f8fa]">Select an NPC</h2>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#a5afbd]">
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
            className="w-full max-w-2xl rounded-xl border border-[#27303a] bg-[#10161d] shadow-2xl"
          >
            <div className="border-b border-[#27303a] px-5 py-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7c8794]">
                {formMode === "create" ? "Create character" : "Edit character"}
              </p>
              <h2 className="mt-2 text-xl font-semibold text-[#f7f8fa]">
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

            <div className="flex flex-col-reverse gap-3 border-t border-[#27303a] px-5 py-4 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="inline-flex min-h-10 items-center justify-center rounded-md border border-[#303a46] px-4 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-[#f7f8fa] px-4 text-sm font-semibold text-[#090b0e] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#f7f8fa] focus:ring-offset-2 focus:ring-offset-[#10161d] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSaving ? "Saving..." : formMode === "create" ? "Create NPC" : "Save changes"}
              </button>
            </div>
          </form>
        </div>
      )}

      {deletingNpc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-[#27303a] bg-[#10161d] p-5 shadow-2xl">
            <h2 className="text-lg font-semibold text-[#f7f8fa]">Delete {deletingNpc.name}?</h2>
            <p className="mt-3 text-sm leading-6 text-[#a5afbd]">
              This removes the character from the active roster. Use this only when the NPC should no longer appear in
              runtime testing.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setDeletingNpc(null)}
                className="inline-flex min-h-10 items-center justify-center rounded-md border border-[#303a46] px-4 text-sm font-semibold text-[#f7f8fa] transition hover:border-[#4a5563] hover:bg-[#151b22] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-rose-200 px-4 text-sm font-semibold text-rose-950 transition hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 focus:ring-offset-2 focus:ring-offset-[#10161d]"
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
      ? "border-rose-500/25 bg-rose-500/10 text-rose-100"
      : "border-emerald-500/25 bg-emerald-500/10 text-emerald-100";

  return <div className={`mb-4 rounded-md border px-4 py-3 text-sm ${styles}`}>{message}</div>;
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <span className="text-sm text-[#a5afbd]">{label}</span>
      <span className="text-sm font-semibold text-[#f7f8fa]">{value}</span>
    </div>
  );
}

function ProfileSection({ title, body }: { title: string; body: string }) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-[#f7f8fa]">{title}</h3>
      <p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-7 text-[#a5afbd]">{body}</p>
    </section>
  );
}

function ReadinessItem({ label, ready }: { label: string; ready: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-[#222a33] bg-[#0b0f13] px-3 py-2">
      <span className="text-sm text-[#a5afbd]">{label}</span>
      <span
        className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
          ready ? "bg-emerald-500/10 text-emerald-300" : "bg-[#1a212a] text-[#7c8794]"
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
      <span className="text-xs font-semibold text-[#a5afbd]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="mt-2 min-h-11 w-full rounded-md border border-[#27303a] bg-[#0a0e12] px-3 text-sm text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20 disabled:cursor-not-allowed disabled:opacity-55"
      />
      {error && <span className="mt-2 block text-xs text-rose-200">{error}</span>}
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
      <span className="text-xs font-semibold text-[#a5afbd]">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={5}
        className="mt-2 w-full resize-y rounded-md border border-[#27303a] bg-[#0a0e12] px-3 py-3 text-sm leading-6 text-[#f7f8fa] outline-none transition placeholder:text-[#6f7a87] focus:border-[#8bdff0] focus:ring-2 focus:ring-[#8bdff0]/20"
      />
      {error && <span className="mt-2 block text-xs text-rose-200">{error}</span>}
    </label>
  );
}
