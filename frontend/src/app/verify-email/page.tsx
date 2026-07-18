"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";
function VerifyEmailContent() { const token = useSearchParams().get("token") || ""; const [text, setText] = useState(""); const verify = async () => { try { await api.confirmEmailVerification(token); setText("Email verified. You can sign in."); } catch (e) { setText(e instanceof Error ? e.message : "Verification failed."); } }; return <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6"><section className="w-full max-w-md"><p className="text-xs uppercase tracking-[.16em] text-[var(--accent)]">GameMind account</p><h1 className="mt-3 font-serif text-4xl">Verify your email.</h1><p className="mt-4 text-sm text-[var(--text-secondary)]">Confirm ownership of this account.</p><button className="btn-primary mt-8 h-12 w-full" onClick={verify} disabled={!token}>Verify email</button>{text && <p className="mt-4 text-sm" role="status">{text}</p>}<Link className="mt-6 inline-block text-sm text-[var(--accent)]" href="/login">Sign in</Link></section></main>; }
export default function VerifyEmailPage() { return <Suspense><VerifyEmailContent /></Suspense>; }
