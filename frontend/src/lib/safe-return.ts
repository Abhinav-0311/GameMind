const fallbackPath = "/";

/**
 * Keeps post-auth navigation inside GameMind. Query strings are preserved so
 * invitation links can be resumed, but protocol-relative and backslash paths
 * are rejected to avoid open redirects.
 */
export function safeReturnPath(candidate: string | null | undefined, fallback: string = fallbackPath): string {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//") || candidate.startsWith("/\\")) {
    return fallback;
  }

  try {
    const parsed = new URL(candidate, "http://gamemind.local");
    if (parsed.origin !== "http://gamemind.local") return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

export function loginContinuationPath(path: string): string {
  return `/login?continue=${encodeURIComponent(safeReturnPath(path))}`;
}
