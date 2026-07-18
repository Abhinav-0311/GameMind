"use client";

import { FormEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { api, getActiveProjectId, subscribeToProjectChange, type WorkspaceMember } from "@/lib/api";

const roleDescription = {
  owner: "Full workspace control",
  editor: "Can shape sources and blueprints",
  viewer: "Can review workspace material",
};

export default function WorkspacePage() {
  const projectId = useSyncExternalStore(subscribeToProjectChange, getActiveProjectId, () => "default_project");

  return <WorkspaceContent key={projectId} projectId={projectId} />;
}

function WorkspaceContent({ projectId }: { projectId: string }) {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "viewer">("editor");
  const [isInviting, setIsInviting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [currentEmail, setCurrentEmail] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    Promise.all([api.getWorkspaceMembers(projectId), api.getAuthSession()])
      .then(([result, session]) => {
        if (!active) return;
        setMembers(result);
        setCurrentEmail(session.user?.email ?? null);
      })
      .catch((reason: unknown) => active && setError(reason instanceof Error ? reason.message : "Could not load workspace members."))
      .finally(() => active && setIsLoading(false));

    return () => { active = false; };
  }, [projectId]);

  const currentMember = useMemo(
    () => members.find((member) => member.email === currentEmail),
    [currentEmail, members]
  );
  const canInvite = currentMember?.role === "owner";

  const submitInvite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const invitee = email.trim().toLowerCase();
    if (!invitee) return;

    setIsInviting(true);
    setError(null);
    setNotice(null);
    try {
      await api.inviteWorkspaceMember(projectId, invitee, role);
      setEmail("");
      setNotice(`Invitation created for ${invitee}.`);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Could not create the invitation.");
    } finally {
      setIsInviting(false);
    }
  };

  return (
    <main className="page-shell max-w-5xl">
      <header className="max-w-2xl py-6 sm:py-10">
        <p className="page-kicker">Workspace</p>
        <h1 className="display-title mt-4 text-4xl leading-tight sm:text-5xl">Bring the right people into the build.</h1>
        <p className="mt-4 text-base leading-7 text-[var(--text-secondary)]">
          Members work from the same sources, decisions, and blueprints. Editors can contribute; viewers can review without changing the plan.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="panel overflow-hidden rounded-3xl" aria-labelledby="members-heading">
          <div className="border-b border-[var(--border)] px-6 py-5">
            <p className="page-kicker">People</p>
            <h2 id="members-heading" className="mt-2 text-xl font-semibold text-[var(--foreground)]">Workspace members</h2>
          </div>
          {isLoading ? (
            <div className="px-6 py-10 text-sm text-[var(--text-secondary)]">Loading members...</div>
          ) : members.length === 0 ? (
            <div className="px-6 py-10 text-sm text-[var(--text-secondary)]">No members are available yet.</div>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {members.map((member) => (
                <li key={member.id} className="flex items-center justify-between gap-4 px-6 py-5">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[var(--foreground)]">{member.email}</p>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{roleDescription[member.role]}</p>
                  </div>
                  <span className="rounded-full bg-[var(--card-muted)] px-3 py-1 text-xs font-semibold capitalize text-[var(--text-secondary)]">{member.role}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="panel h-fit rounded-3xl p-6" aria-labelledby="invite-heading">
          <p className="page-kicker">Invite</p>
          <h2 id="invite-heading" className="mt-2 text-xl font-semibold text-[var(--foreground)]">Add a collaborator</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            {canInvite ? "They will receive a seven-day invitation link." : "Only workspace owners can invite collaborators."}
          </p>
          {canInvite ? <form className="mt-6 space-y-4" onSubmit={submitInvite}>
            <label className="block text-sm font-medium text-[var(--foreground)]">
              Email address
              <input
                required
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="teammate@example.com"
                className="mt-2 w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-sm outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
              />
            </label>
            <label className="block text-sm font-medium text-[var(--foreground)]">
              Access level
              <select value={role} onChange={(event) => setRole(event.target.value as "editor" | "viewer")} className="mt-2 w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-sm outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]">
                <option value="editor">Editor</option>
                <option value="viewer">Viewer</option>
              </select>
            </label>
            <button type="submit" disabled={isInviting} className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-60">
              {isInviting ? "Creating invitation..." : "Send invitation"}
            </button>
          </form>
          : <div className="mt-6 rounded-2xl bg-[var(--card-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
            Your access is {currentMember?.role ?? "not yet available"}. Ask a workspace owner to manage collaborators.
          </div>}
          {notice && <p className="mt-4 text-sm text-emerald-700 dark:text-emerald-300" role="status">{notice}</p>}
          {error && <p className="mt-4 text-sm text-rose-700 dark:text-rose-300" role="alert">{error}</p>}
        </aside>
      </div>
    </main>
  );
}
