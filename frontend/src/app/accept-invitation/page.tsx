"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, setActiveProjectId } from "@/lib/api";
function InvitationContent() { const token = useSearchParams().get("token") || ""; const [text, setText] = useState(""); const accept = async () => { try { const project = await api.acceptInvitation(token); setActiveProjectId(project.id); setText(`Joined ${project.name}.`); } catch (e) { setText(e instanceof Error ? e.message : "Invitation failed."); } }; return <main className="grid min-h-dvh place-items-center bg-[var(--background)] p-6"><section className="w-full max-w-md"><p className="text-xs uppercase tracking-[.16em] text-[var(--accent)]">Workspace invitation</p><h1 className="mt-3 font-serif text-4xl">Join this game.</h1><p className="mt-4 text-sm text-[var(--text-secondary)]">Sign in with the invited email, then accept access.</p><button className="btn-primary mt-8 h-12 w-full" onClick={accept} disabled={!token}>Accept invitation</button>{text && <p className="mt-4 text-sm" role="status">{text}</p>}<Link className="mt-6 inline-block text-sm text-[var(--accent)]" href="/login">Sign in</Link></section></main>; }
export default function AcceptInvitationPage() { return <Suspense><InvitationContent /></Suspense>; }
