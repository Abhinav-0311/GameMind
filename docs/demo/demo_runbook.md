# GameMind MVP Demo Runbook

This runbook is the controlled golden path for demonstrating GameMind as a zero-cost local game design co-pilot and Unity runtime assistant.

## Goal

Show that a developer can start from a GDD, generate a structured game blueprint, materialize runtime data, and test that data through the dashboard and Unity scene.

The story of the demo is:

```text
Sources -> Blueprints -> Lore Search -> Runtime Test -> Unity
```

## Prerequisites

- Docker Desktop is running.
- Backend stack is running:

```bash
docker compose up -d --build
```

- Frontend dashboard is running:

```bash
cd frontend
npm.cmd run dev
```

- Open:

```text
http://localhost:3000
http://localhost:8000/health
```

Expected health mode:

```json
{
  "status": "healthy",
  "database": "healthy",
  "chromadb": "healthy",
  "ai_mode": "local_demo",
  "llm_provider": "mock",
  "embedding_provider": "chroma_default",
  "vector_collection": "lore_chunks_local",
  "vector_dimension": 384
}
```

## Demo Script

### 1. Start At Home

Open `http://localhost:3000`.

Explain:

> GameMind turns game design documents into structured game systems: narrative direction, NPCs, quests, memory, world flags, and Unity runtime data.

Point out:

- Zero-cost local mode.
- Backend, database, and vector index readiness.
- Recommended path.

### 2. Load The GDD

Go to **Sources**.

Recommended path:

```text
Click "Load Frostpeak demo"
```

Alternative manual path:

```text
docs/demo/sample_gdd_frostpeak.md
```

Expected result:

- Document appears in the uploaded documents list.
- Chunk preview shows parsed GDD fragments.
- The document is ready for blueprint generation.

Explain:

> The system stores the document, splits it into searchable chunks, and indexes those chunks for local semantic retrieval.

### 3. Generate A Blueprint

Go to **Blueprints**.

Select:

```text
sample_gdd_frostpeak.md
```

Click:

```text
Generate blueprint
```

Expected generated sections:

- Game summary
- Narrative direction
- Art style
- NPC cast
- Memory design
- Level design
- Quest hooks
- Unity preview

Expected clean sample output:

- NPCs: `Eldrin`, `Kaelen`
- Quests:
  - `Reclaim the Ash Pass border post`
  - `Mine 5 chunks of raw sky-iron ore from the cliffside veins`

Explain:

> This MVP uses deterministic local extraction rules instead of paid LLM calls. The goal is to prove the pipeline and product workflow without spending money.

### 4. Approve The Blueprint

Review the sections.

Click:

```text
Approve
```

Explain:

> Approval is the boundary between generated draft content and runtime data. Nothing should be written into the playable backend until the developer approves it.

### 5. Materialize Runtime Data

Click:

```text
Materialize
```

Expected result:

- NPCs, quests, memories, and world flags are created or updated.
- The blueprint becomes runtime-ready.
- A materialization summary appears.
- If any generated fragment is unsafe, it appears as skipped instead of being written to runtime data.

Explain:

> Materialization converts the blueprint into active database records that the game runtime can use.

### 6. Inspect Runtime Bundle

Click:

```text
Runtime bundle
```

Expected result:

- Runtime JSON includes NPCs, quests, memories, and world flags.
- This is the Unity contract.

Explain:

> Unity does not need to understand the original GDD. It only needs this clean runtime contract.

### 7. Test Lore Query

Go to **Lore Search**.

Ask:

```text
Who is King Arven?
```

Expected result:

- Local Chroma returns cited lore chunks.
- The answer should cite the Frostpeak GDD chunk mentioning King Arven.

Explain:

> RAG retrieves relevant source chunks so generated systems remain grounded in the uploaded document. If citations are weak, the source document needs more detail.

### 8. Test Runtime In The Dashboard

Go to **Runtime Test**.

Expected result:

- Select the Frostpeak source and an NPC.
- Send a dialogue message.
- Generate a quest.
- Accept the quest.
- Request a progressive hint.
- Open **Unity contract** only if you need to inspect the raw runtime data.

Explain:

> Runtime Test proves the playable loop before Unity is opened. It checks dialogue, quest registration, and hint progression through the same backend contracts Unity uses.

### 9. Test Unity Scene

Open the Unity project in:

```text
Unity/
```

Open scene:

```text
Assets/Scenes/GameMindVerticalSlice.unity
```

In `GameMindManager`, set the target blueprint ID to the runtime-ready blueprint.

Press Play.

Expected result:

- Status shows connected/runtime-ready.
- Quest panel loads.
- Talk button appears.
- Accept quest unlocks hint flow.

Explain:

> Unity is the final consumer, not the place where the AI logic lives. The game scene calls the backend and renders the prepared runtime data.

## Important Demo Notes

- Do not add paid API keys for the MVP demo. The project is intentionally local-first and zero-cost.
- If materialization skips records, the dev database already contains records with the same slug/title/flag. That is a safety guard, not a crash.
- For a clean public demo, use a clean database volume or a fresh project ID so the generated records are not mixed with older test data.
- Hide expanded JSON/contract panels during a non-technical demo unless someone asks how Unity receives the data.

## Verification Commands

Backend:

```bash
docker exec gamemind_backend pytest -q
```

Frontend:

```bash
cd frontend
npm.cmd run lint
npm.cmd run build
```

Expected backend result:

```text
All tests pass with no live-provider key required.
```
