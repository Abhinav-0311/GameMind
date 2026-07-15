# CyberRakshak Case-Study Demo Script

Use this script with `assets/demo/gamemind-cyberrakshak-walkthrough.webm`. The video is silent by design; narrate it live or record the voice-over separately.

## Opening

> This is CyberRakshak, a game design document being used as a real case study for GameMind. Instead of starting with a chat prompt, I start with the project source of truth.

## Sources

> GameMind stores the GDD in a project workspace, breaks it into searchable chunks, and keeps later design outputs tied to this evidence.

## Decisions

> The system identifies what the GDD does not yet decide. For CyberRakshak, that is the delivery platform, online feature boundary, and accessibility. It does not invent these commitments. It creates a technical-brief template so the developer can make, document, and attach the real decision.

## Blueprint

> The blueprint converts the source into a reviewable game plan. Here, the NPC section extracts Adi, Jay, and PATCH as separate profiles. The Memory section is deliberately empty because the GDD does not contain explicit memory rules. That absence is shown as a source gap, not fabricated content.

## Grounding

> Lore Search is the retrieval layer. It returns source-backed fragments so the developer can inspect what GameMind knows before trusting downstream output.

## Runtime

> The runtime test surface validates the contracts a game client would use for dialogue, quests, and progressive hints. Unity is one adapter, not a product requirement: the dashboard remains useful before any engine integration begins.

## Closing

> GameMind demonstrates AI engineering and game development together: source ingestion, retrieval, structured generation, review gates, durable project data, and engine-ready contracts. The point is not to replace the developer. The point is to make the game design process more grounded and actionable.
