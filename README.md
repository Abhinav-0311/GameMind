# GameMind

GameMind is an AI-powered game design co-pilot and Unity runtime assistant for students, new game developers, and indie teams. It turns uploaded game design documents, lore files, NPC notes, quest ideas, and level concepts into structured game systems that can be reviewed in a dashboard and exported for Unity.

The project combines a FastAPI backend, PostgreSQL, ChromaDB vector search, a Next.js developer dashboard, and Unity C# runtime scripts. It is designed to run in a zero-cost local demo mode without mandatory paid AI APIs, while keeping the AI provider layer optional and swappable.

## What It Does

- Upload and index game documents such as GDDs, lore files, character notes, and quest rules.
- Query the lore index with citations, confidence scores, and local Chroma retrieval.
- Generate game blueprints from uploaded GDDs using local rules, templates, and schema validation.
- Review narrative direction, art style direction, NPC archetypes, memory design, level suggestions, quest hooks, and Unity runtime previews.
- Manage NPC profiles, quests, world state, memory, dialogue assembly, progressive hints, and analytics.
- Export structured JSON that Unity can consume for NPC dialogue, quests, hints, emotions, and animation suggestions.

## Tech Stack

- **Frontend:** Next.js, TypeScript
- **Backend:** FastAPI, Python, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **Vector Search:** ChromaDB
- **Game Runtime:** Unity, C#
- **Infrastructure:** Docker Compose
- **AI Mode:** zero-cost local demo by default, optional provider integrations

## Project Structure

```text
backend/        FastAPI app, services, models, migrations, tests
frontend/       Next.js developer dashboard
Unity/          Unity C# runtime integration scripts
docs/demo/      Demo GDD used for the blueprint golden path
docker-compose.yml
```

## Local Setup

1. Copy the environment example:

```bash
cp .env.example .env
```

2. Start backend services:

```bash
docker compose up -d --build
```

This starts PostgreSQL, ChromaDB, and the FastAPI backend. Backend migrations run automatically on local container startup.

3. Start the dashboard:

```bash
cd frontend
npm install
npm.cmd run dev
```

Open:

```text
http://localhost:3000
http://localhost:8000/docs
```

## Verification

Run backend tests:

```bash
docker exec gamemind_backend pytest
```

Run frontend checks:

```bash
cd frontend
npm.cmd run lint
npm.cmd run build
```

Check backend health:

```bash
curl http://localhost:8000/health
```

Expected local demo mode:

```json
{
  "status": "healthy",
  "database": "healthy",
  "chromadb": "healthy",
  "gemini_api": "not_configured",
  "ai_mode": "local_demo",
  "embedding_provider": "chroma_default",
  "vector_collection": "lore_chunks_local",
  "vector_dimension": 384
}
```

## Demo Flow

1. Upload `docs/demo/sample_gdd_frostpeak.md` through the Knowledge Base.
2. Open Blueprint Studio.
3. Generate a blueprint from the uploaded GDD.
4. Review all generated sections with citations, confidence, and warnings.
5. Approve and export the Unity runtime JSON.
6. Use the Unity scripts as the runtime integration base for NPC dialogue, quest, and hint flows.

## Production Notes

Local development runs migrations automatically in the backend container. Production deployments should run `alembic upgrade head` as a separate migration job before application replicas start.

Gemini/cloud model integrations are optional. The main demo path is intentionally provider-agnostic and works without paid API usage.
