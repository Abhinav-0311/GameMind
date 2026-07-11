# GameMind 2-Minute Demo Script

Use this when recording a video, presenting in class, or walking someone through the MVP.

## Positioning

GameMind is a local-first AI game builder for students, new developers, and indie teams. It turns a game design document into grounded, reviewable, Unity-ready game systems: lore search, blueprint sections, NPCs, quests, memories, world flags, runtime dialogue, and progressive hints.

The key message:

```text
GameMind does not just chat about a game idea. It converts source design documents into structured runtime data a Unity scene can consume.
```

## Recording Setup

- Start Docker Desktop.
- Run `docker compose up -d --build`.
- Run the dashboard with `cd frontend` then `npm.cmd run dev`.
- Open `http://localhost:3000`.
- Keep browser zoom at `100%`.
- Use the light or dark theme, but do not switch themes during the recording.
- Close raw JSON panels unless you are explaining the Unity contract.
- Do not mention paid APIs. The MVP is zero-cost local mode.

## Timeline

### 0:00-0:15 - Home

Show the Home screen.

Say:

> GameMind is a local-first AI game builder. It helps a small game team start from a GDD and move toward playable runtime systems: sources, blueprints, lore search, dialogue, quests, hints, and Unity data.

Point out:

- Connected status.
- Zero-cost local mode.
- The guided build flow.

### 0:15-0:35 - Sources

Open Sources.

Click `Load Frostpeak demo` if the demo document is not already loaded.

Say:

> The first step is source truth. The developer uploads a GDD, lore file, NPC sheet, or quest notes. GameMind stores it, chunks it, and indexes it locally so later outputs can be traced back to source evidence.

Show:

- The Frostpeak document.
- Chunk count or preview.

### 0:35-1:05 - Blueprints

Open Blueprints.

Select `sample_gdd_frostpeak.md`.

Click `Generate blueprint` if needed.

Say:

> The blueprint turns the document into a structured game plan. Instead of a free-form chat answer, the output is split into useful production sections: summary, narrative direction, art style, NPC cast, memory, levels, quest hooks, and Unity runtime preview.

Then show approval/materialization.

Say:

> Approval matters because generated content should stay draft-only until the developer accepts it. Materialization converts the approved blueprint into backend records the game can use.

### 1:05-1:25 - Lore Search

Open Lore Search.

Search:

```text
Who is King Arven?
```

Say:

> Lore Search is the RAG layer. It retrieves relevant chunks from the uploaded document and returns citations, so we can check whether the system is grounded before trusting generated content.

Show:

- Citation result.
- Match confidence.

### 1:25-1:50 - Runtime Test

Open Runtime Test.

Show dialogue, quest, and hint areas.

Say:

> Runtime Test verifies the playable loop before Unity is opened. The dashboard tests the same backend contracts Unity uses: NPC dialogue, quest generation, quest acceptance, progressive hints, and runtime bundle data.

If the data is already loaded, click through:

- Talk to NPC.
- Generate quest.
- Accept quest.
- Request hint.

### 1:50-2:10 - Unity

Show the Unity scene only if it is ready and clean.

Say:

> Unity is the consumer. The AI logic and source grounding stay in the backend; Unity receives clean runtime data and renders it as game interaction.

If Unity is not visually polished enough for the audience, say:

> The Unity scene is a vertical-slice integration proof. The strongest part of this MVP is the pipeline from document to runtime contract.

## What To Avoid

- Do not open old cluttered analytics pages unless asked.
- Do not expand long raw JSON during the main demo.
- Do not frame the MVP as a finished commercial product.
- Do not apologize for local mode. Local mode is a product decision: it proves the workflow with zero model cost.
- Do not manually explain every backend table. Focus on the developer journey.

## Strong Closing

Say:

> This project demonstrates both game development and AI engineering: document ingestion, RAG, structured generation, review gates, durable backend data, dashboard UX, and Unity runtime integration. The next production step is improving blueprint quality with an optional provider, while preserving this zero-cost local workflow.

