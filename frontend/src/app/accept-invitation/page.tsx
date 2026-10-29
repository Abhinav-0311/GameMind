"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, setActiveProjectId, setActiveProjectUser } from "@/lib/api";
import { loginContinuationPath } from "@/lib/safe-return";

function InvitationContent() {
  const token = useSearchParams().get("token")?.trim() || "";
  const [status, setStatus] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const invitationPath = token ? `/accept-invitation?token=${encodeURIComponent(token)}` : "/accept-invitation";

  const accept = async () => {
    if (!token || accepting || status) return;

    setAccepting(true);
    setStatus(null);
    setError(null);
    try {
      const session = await api.getAuthSession();
      setActiveProjectUser(session.user?.id ?? null);
      const project = await api.acceptInvitation(token);
      setActiveProjectId(project.id);
      setStatus(`Joined ${project.name}. You can now open the workspace.`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Invitation failed. Ask the owner for a new link.");
    } finally {
      setAccepting(false);
    }
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6 text-[var(--foreground)]">
      <section className="w-full max-w-md" aria-busy={accepting}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">Workspace invitation</p>
        <h1 className="mt-3 font-serif text-4xl font-semibold tracking-tight">Join this game.</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-secondary)]">
          Sign in with the invited email, then explicitly accept access to this workspace.
        </p>

        {!token ? (
          <p className="mt-6 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-[var(--danger-text)]" role="alert">
            This invitation link is missing its token. Ask the workspace owner to send it again.
          </p>
        ) : null}

        <button className="btn-primary mt-8 h-12 w-full" onClick={accept} disabled={!token || accepting || Boolean(status)}>
          {accepting ? "Joining..." : status ? "Invitation accepted" : "Accept invitation"}
        </button>
        {status ? <p className="mt-4 text-sm text-[var(--text-secondary)]" role="status">{status}</p> : null}
        {error && <p className="mt-4 text-sm text-[var(--danger-text)]" role="alert">{error} Ask the workspace owner for a new invitation if this link has expired.</p>}

        <div className="mt-6 flex items-center gap-4 text-sm">
          <Link className="font-medium text-[var(--accent)] hover:underline" href={loginContinuationPath(invitationPath)}>
            Sign in
          </Link>
          {status?.startsWith("Joined") ? (
            <Link className="font-medium text-[var(--accent)] hover:underline" href="/">
              Open workspace
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense>
      <InvitationContent />
    </Suspense>
  );
}
