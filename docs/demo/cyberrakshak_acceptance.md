# CyberRakshak Acceptance Case

This case demonstrates the dashboard workflow against a real long-form GDD, then makes proposed implementation decisions explicit through traceable companion sources.

## Source

- Primary source: `docs/demo/cyberrakshak_gdd.md`
- Technical companion: `docs/demo/cyberrakshak_technical_brief.md`
- Runtime companion: `docs/demo/cyberrakshak_runtime_extension.md`
- Workspace: `cyberrakshak`
- Source types: `gdd`, `technical_brief`, and `quest_brief`

## Verified Outcomes

1. Source ingestion created an indexed, project-scoped GDD.
2. Blueprint generation extracted named character records for Adi, Jay, and PATCH.
3. The runtime blueprint contains the named profiles Jay, PATCH, and Adi, plus three explicit quest records owned by Jay.
4. The final blueprint is approved and materialized into runtime-ready data without warnings.
5. The decision workflow identified the three implementation choices that the GDD does not settle:
   - Multi-platform delivery scope
   - Online feature boundary
   - Accessibility
6. The technical brief records proposed MVP decisions for delivery scope, offline operation, performance, and accessibility; each resolved decision retains that document as evidence.
7. The final runtime bundle exposes three NPCs and three quests while retaining the original GDD and both companion sources as blueprint provenance.

## Explicitly Proposed

The original GDD does not settle the following details. They are therefore recorded in a separate, reviewable technical brief instead of being treated as extracted facts:

- The MVP target platform and deferred modes
- A measurable performance target
- Online-service failure behavior
- Accessibility commitments and their test cases

The runtime extension also defines the initial NPC and quest records required for a playable vertical slice. These are proposed design inputs, not hidden model output. A team can revise either companion source, upload a revision, and generate a new blueprint with a complete audit trail.

## Reproduction

1. Start the local Docker services and dashboard.
2. Upload `cyberrakshak_gdd.md` in the `cyberrakshak` workspace as a GDD.
3. Upload `cyberrakshak_technical_brief.md` as a **Technical brief** and resolve the three decision records with it as evidence.
4. Upload `cyberrakshak_runtime_extension.md` as a **Quest brief**.
5. Generate a blueprint using the runtime extension as primary source and the GDD plus technical brief as supporting sources.
6. Review the NPC and Quest sections, approve the blueprint, then materialize it.
7. Confirm the runtime bundle contains Jay, PATCH, Adi, and the three named quests.
