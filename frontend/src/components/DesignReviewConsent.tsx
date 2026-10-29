export default function DesignReviewConsent({ provider, critiqueOnly = false }: {
  provider: string | null;
  critiqueOnly?: boolean;
}) {
  const source = critiqueOnly ? "The saved draft and its frozen source text" : "The selected source text";
  return (
    <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
      {provider === "mock" ? (
        "This run is offline. The mock provider processes source excerpts locally and sends nothing to a hosted provider. It uses deterministic extraction, not newly generated content."
      ) : (
        <>
          {source} may be sent to {provider === "gemini" ? "Google's Gemini API" : `the configured hosted provider${provider ? ` (${provider})` : ""}`} {critiqueOnly ? "for critique only." : "to create a cited draft and independent critique."}{" "}
          {critiqueOnly && "Planning, retrieval and generation will not repeat. The draft stays unchanged; nothing is approved. "}
          {provider === "gemini" && "On the free tier, Google may use submitted content to improve its products. Use only demo or non-confidential material. Mock mode runs offline and sends nothing to a hosted provider. "}
          No provider request is made until you confirm.
        </>
      )}
    </p>
  );
}
