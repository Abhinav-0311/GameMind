"use client";

import { useState } from "react";
import ModalDialog from "./ModalDialog";

export interface CorrectionField { path: string; value: string; effect: string }

export function correctionFields(content: Record<string, unknown>): CorrectionField[] {
  const fields: CorrectionField[] = [];
  // Only walk these two typed record shapes; never offer arbitrary JSON paths.
  const quests = (content.quest_hooks as { content?: { quests?: { dialogue_hooks?: unknown[] }[] } })?.content?.quests;
  quests?.forEach((quest, i) => quest.dialogue_hooks?.forEach((value, j) => {
    if (typeof value === "string") fields.push({ path: `/quest_hooks/content/quests/${i}/dialogue_hooks/${j}`, value,
      effect: `Only this quest’s assumptions may gain the server’s exact “Generated quest … are creative proposals and require design approval before runtime use.” annotation, derived from its cited source. Existing assumptions remain.` });
  }));
  const npcs = (content.npc_archetypes as { content?: { npcs?: { dialogue_triggers?: { situation?: unknown }[] }[] } })?.content?.npcs;
  npcs?.forEach((npc, i) => npc.dialogue_triggers?.forEach((trigger, j) => {
    if (typeof trigger.situation === "string") fields.push({ path: `/npc_archetypes/content/npcs/${i}/dialogue_triggers/${j}/situation`, value: trigger.situation,
      effect: `Regenerate only /npc_archetypes/content/npcs/${i}/dialogue_triggers/${j}/manual_test from this situation, unchanged speech and eligibility.` });
  }));
  return fields;
}

export function CorrectionFieldChoices({ fields, selected, disabled, onChange }: {
  fields: CorrectionField[]; selected: string[]; disabled: boolean; onChange: (paths: string[]) => void;
}) {
  return <fieldset disabled={disabled} aria-describedby="correction-scope-help" className="space-y-3">
    <legend className="mb-2 text-sm font-semibold">Select one or two exact fields</legend>
    {fields.length === 0 && <p className="text-sm text-[var(--text-secondary)]">This draft has no supported correction fields.</p>}
    {fields.map((field) => <label key={field.path} className="flex gap-3 rounded-lg border border-[var(--border)] p-3 focus-within:outline-2 focus-within:outline-offset-2">
      <input type="checkbox" className="mt-1 size-4 shrink-0 accent-[var(--accent)]" checked={selected.includes(field.path)}
        disabled={disabled || (!selected.includes(field.path) && selected.length >= 2)}
        onChange={(event) => onChange(event.target.checked ? [...selected, field.path] : selected.filter((path) => path !== field.path))} />
      <span className="min-w-0 space-y-2 text-sm leading-6">
        <code className="block break-all text-xs text-[var(--text-secondary)]">{field.path}</code>
        <span className="block whitespace-pre-wrap break-words">{field.value}</span>
        <span className="block text-xs text-[var(--text-secondary)]">Dependent effect: {field.effect}</span>
      </span>
    </label>)}
  </fieldset>;
}

export default function FieldCorrectionDialog({ artifactId, content, busy, error, onClose, onSubmit }: {
  artifactId: string; content: Record<string, unknown>; busy: boolean; error: string | null;
  onClose: () => void; onSubmit: (reason: string, paths: string[], artifactId: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  return <ModalDialog labelledBy="field-correction-title" onClose={onClose} dismissible={!busy} returnFocusId="request-field-correction">
    <div className="space-y-5 p-6">
      <div><h2 id="field-correction-title" className="text-xl font-semibold">Request correction</h2>
        <p id="correction-scope-help" className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">Only selected text and the listed dependent effects may change. This is not a rejection. A failed correction leaves the draft unchanged and still approvable if its other gates allow. A saved correction uses one revision and receives a new critique.</p></div>
      <CorrectionFieldChoices fields={correctionFields(content)} selected={selected} disabled={busy} onChange={setSelected} />
      <div><label htmlFor="field-correction-reason" className="text-sm font-semibold">What should change, and why?</label>
        <textarea id="field-correction-reason" rows={4} maxLength={4000} value={reason} disabled={busy}
          onChange={(event) => setReason(event.target.value)}
          className="mt-2 w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]" />
      </div>
      {error && <p role="alert" className="text-sm leading-6 text-[var(--warning-text)]">{error}</p>}
      <div className="flex flex-wrap justify-end gap-3">
        <button type="button" className="btn-secondary" disabled={busy} onClick={onClose}>Cancel</button>
        <button type="button" className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          disabled={busy || selected.length < 1 || selected.length > 2 || !reason.trim()}
          onClick={() => onSubmit(reason.trim(), selected, artifactId)}>{busy ? "Correcting and critiquing…" : "Send correction request"}</button>
      </div>
    </div>
  </ModalDialog>;
}
