"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await api.requestPasswordReset(email);
      setStatus("If an account exists for this email, a reset link is on its way.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not request a reset link.");
    }
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6 text-[var(--foreground)]">
      <section className="w-full max-w-md">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">Account recovery</p>
        <h1 className="mt-3 font-serif text-4xl font-semibold">Reset your password.</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-secondary)]">Enter the email used for your GameMind account.</p>
        <form className="mt-8 space-y-4" onSubmit={submit}>
          <input className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
          {status && <p className="text-sm text-emerald-700" role="status">{status}</p>}
          {error && <p className="text-sm text-rose-700" role="alert">{error}</p>}
          <button className="btn-primary h-12 w-full">Send reset link</button>
        </form>
        <Link className="mt-6 inline-block text-sm font-medium text-[var(--accent)] hover:underline" href="/login">Back to sign in</Link>
      </section>
    </main>
  );
}
