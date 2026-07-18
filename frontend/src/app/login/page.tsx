"use client";

import { FormEvent, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Mode = "sign-in" | "create-account";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAuthSession().then((session) => {
      if (session.user) router.replace("/");
    }).catch(() => undefined);
  }, [router]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "create-account") {
        await api.register(email, password);
      } else {
        await api.login(email, password);
      }
      router.replace("/");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const isCreate = mode === "create-account";
  return (
    <main className="min-h-dvh bg-[var(--background)] px-5 py-8 text-[var(--foreground)] sm:grid sm:place-items-center sm:p-8">
      <section className="mx-auto w-full max-w-md">
        <div className="mb-12 flex items-center gap-3">
          <Image src="/brand/gamemind-icon.svg" alt="GameMind" width={42} height={42} priority />
          <div>
            <p className="text-lg font-semibold tracking-tight">GameMind</p>
            <p className="text-xs text-[var(--text-secondary)]">Guided game builder</p>
          </div>
        </div>

        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">Your workspace</p>
        <h1 className="mt-3 font-serif text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          {isCreate ? "Start with one game." : "Welcome back."}
        </h1>
        <p className="mt-4 max-w-sm text-sm leading-6 text-[var(--text-secondary)]">
          {isCreate
            ? "Create a private workspace for your game documents, decisions, and runtime data."
            : "Sign in to continue building from your source material."}
        </p>

        <form className="mt-10 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Email address
            <input
              className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_24%,transparent)]"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_24%,transparent)]"
              type="password"
              autoComplete={isCreate ? "new-password" : "current-password"}
              minLength={12}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            {isCreate && <span className="mt-2 block text-xs text-[var(--text-secondary)]">Use at least 12 characters.</span>}
          </label>
          {!isCreate && <Link href="/forgot-password" className="block text-right text-xs font-medium text-[var(--accent)] hover:underline">Forgot password?</Link>}
          {error && <p className="rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">{error}</p>}
          <button className="btn-primary h-12 w-full" type="submit" disabled={submitting}>
            {submitting ? "Please wait" : isCreate ? "Create account" : "Sign in"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(isCreate ? "sign-in" : "create-account");
            setError(null);
          }}
          className="mt-6 text-sm font-medium text-[var(--accent)] underline-offset-4 hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        >
          {isCreate ? "Already have an account? Sign in" : "New to GameMind? Create an account"}
        </button>
      </section>
    </main>
  );
}
