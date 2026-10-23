"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
function VerifyEmailContent() {
  const token = useSearchParams().get("token")?.trim() || "";
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [requestStatus, setRequestStatus] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const verify = async () => {
    if (!token || busy || status) return;
    setBusy(true);
    setError(null);
    try {
      await api.confirmEmailVerification(token);
      setStatus("Email verified. You can sign in.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Verification failed. Request a new link below.");
    } finally { setBusy(false); }
  };
  const requestLink = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setRequestStatus(null);
    setRequestError(null);
    try {
      await api.requestEmailVerification(email);
      setRequestStatus("If this account needs verification, a new link is on its way.");
    } catch {
      setRequestError("Could not request a new link. Check the API connection and try again.");
    } finally { setBusy(false); }
  };
  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6 text-[var(--foreground)]">
      <section className="w-full max-w-md" aria-busy={busy}>
        <p className="page-kicker">GameMind account</p>
        <h1 className="display-title mt-3 text-4xl">Verify your email.</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-secondary)]">Confirm ownership of this account using the full link in your email.</p>
        {!token && <p role="alert" className="mt-6 text-sm text-[var(--danger-text)]">This verification link is incomplete. Open the full email link or request a new one below.</p>}
        <button className="btn-primary mt-8 h-12 w-full" onClick={verify} disabled={!token || busy || Boolean(status)}>{busy ? "Working…" : status ? "Email verified" : "Verify email"}</button>
        {status && <p className="mt-4 text-sm text-[var(--success-text)]" role="status">{status}</p>}
        {error && <p className="mt-4 text-sm text-[var(--danger-text)]" role="alert">{error}</p>}
        {(!token || error) && <form onSubmit={requestLink} className="mt-8 space-y-3">
          <label htmlFor="verification-email" className="block text-sm font-semibold">Email address</label>
          <input id="verification-email" name="email" autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} required aria-describedby={requestError ? "verification-request-error" : undefined} className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 focus-visible:outline-2 focus-visible:outline-[var(--accent)]" />
          <button disabled={busy} className="btn-secondary w-full">Request a new verification link</button>
          {requestStatus && <p role="status" className="text-sm text-[var(--success-text)]">{requestStatus}</p>}
          {requestError && <p id="verification-request-error" role="alert" className="text-sm text-[var(--danger-text)]">{requestError}</p>}
        </form>}
        <Link className="mt-6 inline-block text-sm font-medium text-[var(--accent)] hover:underline" href="/login">Sign in</Link>
      </section>
    </main>
  );
}
export default function VerifyEmailPage() {
  return <Suspense fallback={<p role="status">Loading email verification…</p>}><VerifyEmailContent /></Suspense>;
}
