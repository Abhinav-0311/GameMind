# GameMind MVP Acceptance Checklist

Use this checklist before recording a demo, pushing a release branch, or presenting the project.

## 1. Local Stack

- Docker Desktop is running.
- `docker compose up -d --build` completes.
- `http://localhost:8000/health` returns:
  - `status: healthy`
  - `database: healthy`
  - `chromadb: healthy`
  - `ai_mode: local_demo`
  - `vector_collection: lore_chunks_local`
- No external model key is required.
- Paid API cost remains `$0`.

## 2. Dashboard Golden Path

- Home clearly shows the next recommended step.
- Sources can load the Frostpeak demo GDD.
- Sources show indexed chunks after loading the document.
- Blueprints can generate from the Frostpeak source.
- Blueprint sections are readable without opening raw structured data.
- Blueprint approval succeeds.
- Materialization creates or safely skips runtime records with a clear report.
- Lore Search returns cited chunks for `Who is King Arven?`.
- Runtime Test can:
  - select a source and NPC
  - send dialogue
  - generate a quest
  - accept a quest
  - request a progressive hint

## 3. Unity Vertical Slice

- Unity opens `Unity/Assets/Scenes/GameMindVerticalSlice.unity`.
- The scene compiles without C# errors.
- Play mode shows backend connection status.
- Quest panel loads from runtime data.
- Dialogue/quest/hint UI is clickable.
- Unity contract data is consumed from the backend, not hardcoded in the scene.

## 4. Verification Gates

Backend:

```bash
docker exec gamemind_backend pytest
```

Frontend:

```bash
cd frontend
npm.cmd run lint
npm.cmd run build
```

Optional browser QA:

- Check `/`, `/knowledge`, `/blueprints`, `/query`, and `/vertical-slice`.
- Check desktop and mobile widths.
- Confirm no console errors.
- Confirm no horizontal overflow.

## 5. Repo Quality

- `.env` files are not tracked.
- Unity generated folders are not tracked:
  - `Unity/Library`
  - `Unity/Logs`
  - `Unity/UserSettings`
  - `Unity/Temp`
- Brand assets are present:
  - `assets/brand/gamemind-logo.svg`
  - `assets/brand/gamemind-icon.svg`
  - `frontend/public/brand/*`
- README explains:
  - product goal
  - zero-cost local mode
  - architecture
  - demo flow
  - current MVP status

## 6. Demo Quality Bar

The MVP is acceptable when a viewer can understand this without extra explanation:

```text
GameMind converts a GDD into grounded, reviewable, Unity-ready game systems.
```

Do not present the project as complete production software. Present it as a polished vertical slice that proves backend AI workflows, RAG, structured generation, product UX, and Unity integration.
