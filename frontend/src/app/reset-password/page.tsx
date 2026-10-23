"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
function ResetPasswordContent() {
  const token = useSearchParams().get("token")?.trim() || "";
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || busy || status) return;
    setBusy(true);
    setError(null);
    try {
      await api.confirmPasswordReset(token, password);
      setPassword("");
      setStatus("Password updated. Sign in with your new password.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reset failed. Request a new reset link.");
    } finally { setBusy(false); }
  };
  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6 text-[var(--foreground)]">
      <section className="w-full max-w-md">
        <p className="page-kicker">Account recovery</p>
        <h1 className="display-title mt-3 text-4xl">Choose a new password.</h1>
        <p id="password-guidance" className="mt-4 text-sm leading-6 text-[var(--text-secondary)]">Use at least 12 characters. After resetting, sign in again on your devices.</p>
        {!token && <p role="alert" className="mt-6 text-sm text-[var(--danger-text)]">This reset link is incomplete. Open the full link from your email or request a new reset link below.</p>}
        <form onSubmit={submit} className="mt-8 space-y-4" aria-busy={busy}>
          <label htmlFor="new-password" className="block text-sm font-semibold">New password</label>
          <input id="new-password" name="password" autoComplete="new-password" aria-describedby={`password-guidance${error ? " reset-error" : ""}`} className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 focus-visible:outline-2 focus-visible:outline-[var(--accent)]" type="password" minLength={12} disabled={!token || busy || Boolean(status)} value={password} onChange={(event) => setPassword(event.target.value)} required />
          <button className="btn-primary h-12 w-full" disabled={!token || busy || Boolean(status)}>{busy ? "Updating…" : status ? "Password updated" : "Update password"}</button>
          {status && <p className="text-sm text-[var(--success-text)]" role="status">{status}</p>}
          {error && <p id="reset-error" className="text-sm text-[var(--danger-text)]" role="alert">{error}</p>}
        </form>
        <div className="mt-6 flex flex-wrap gap-4 text-sm font-medium text-[var(--accent)]">
          <Link className="hover:underline" href="/forgot-password">Request a new reset link</Link>
          <Link className="hover:underline" href="/login">Sign in</Link>
        </div>
      </section>
    </main>
  );
}
export default function ResetPasswordPage() {
  return <Suspense fallback={<p role="status">Loading password recovery…</p>}><ResetPasswordContent /></Suspense>;
}
