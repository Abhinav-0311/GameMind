# CyberRakshak Acceptance Case

This case demonstrates the dashboard workflow against a real long-form GDD without inventing production decisions.

## Source

- Primary source: `docs/demo/cyberrakshak_gdd.md`
- Workspace: `cyberrakshak`
- Source type: `gdd`

## Verified Outcomes

1. Source ingestion created an indexed, project-scoped GDD.
2. Blueprint generation extracted named character records for Adi, Jay, and PATCH.
3. The generated blueprint retained game systems and the Must/Should/Could MVP scope without spreading them across unrelated sections.
4. The blueprint can be approved and materialized into runtime-ready data.
5. The decision workflow identified the three implementation choices that the GDD does not settle:
   - Multi-platform delivery scope
   - Online feature boundary
   - Accessibility
6. The technical-brief template endpoint generates a local Markdown file containing these decisions and explicit placeholders for the team to complete.

## Deliberately Not Invented

The template leaves the following details open until the game team decides them:

- The MVP target platform and deferred modes
- A measurable performance target
- Online-service failure behavior
- Accessibility commitments and their test cases

This is intentional. GameMind should ground recommendations in uploaded evidence and identify missing requirements; it should not manufacture production commitments for the team.

## Reproduction

1. Start the local Docker services and dashboard.
2. Upload `cyberrakshak_gdd.md` in the `cyberrakshak` workspace as a GDD.
3. Create a blueprint from that GDD and review the NPC, missions, systems, and scope sections.
4. Open **Decisions**, run the GDD review, then download the technical-brief template.
5. After a team completes and uploads that brief as a **Technical brief**, attach it to the matching decision and mark the decision resolved.

