# Dashboard Workspace Workflow

Use this workflow when GameMind is acting as a game design command center, not as a live runtime service.

## Who This Mode Is For

- Students building a first game project.
- Writers organizing lore, factions, characters, and quests.
- Indie teams turning rough design notes into a shared plan.
- Developers who want structured game data before engine integration.

## Goal

Turn source design material into grounded, reviewable, exportable game systems.

```text
Source documents -> Lore search -> Blueprint -> Review -> Export
```

## Workflow

### 1. Add Source Truth

Upload or load:

- Game design documents.
- Lore files.
- NPC sheets.
- Quest notes.
- Level briefs.
- Item or faction rules.

GameMind stores the document, chunks it, and indexes the chunks for local retrieval.

### 2. Ask Grounded Lore Questions

Use Lore Search before generation.

Good checks:

- Who is the main ruler or antagonist?
- What event caused the current conflict?
- Which faction controls a location?
- What rules govern quest rewards?

The goal is to verify that the system can retrieve relevant source evidence before generating new structures.

### 3. Generate A Blueprint

Generate a blueprint from a selected source document.

Current blueprint sections:

- Game summary.
- Narrative direction.
- Art style direction.
- NPC cast.
- NPC memory design.
- Level design suggestions.
- Quest hooks.
- Unity/runtime preview.

Treat the blueprint as a draft. It should be reviewed, not blindly accepted.

### 4. Review Quality

Look for:

- Strong citations.
- High confidence.
- Clear NPC motivations.
- Usable quest objectives.
- Specific level ideas.
- Warnings about missing or weak source information.

If a section feels generic, improve the source GDD and regenerate.

### 5. Export For The Team

Useful exports:

- Blueprint JSON for developers.
- Markdown design summary for teammates.
- Runtime bundle JSON for technical review.

This mode is complete when the team can explain the game direction, NPC roles, quest hooks, and runtime shape without opening Unity.

## What This Mode Is Not

- It is not a final narrative writer.
- It is not a replacement for game design judgment.
- It is not tied to Unity.
- It is not dependent on paid model APIs in the MVP.

## Quality Bar

The dashboard workspace is successful when a new developer can upload a rough GDD and leave with a clearer, structured, source-grounded game plan.

