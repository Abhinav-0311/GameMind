# GameMind - AI-Powered Game Development Dashboard

GameMind is an intelligent AI narrative engine, knowledge graph, and developer platform designed to connect game content with AI. It enables game studios and indie developers to manage game lore, configure NPC profiles, traverse relationship graphs, test dialogue generation, and monitor progressive hint systems.

This is **Release 3C.3 (Stabilized Product)**, which stabilizes the core APIs, vector search indexes, NPC dialogue pipelines, and progressive hints testing suite under a unified developer workspace.

---

## Technical Stack

* **Backend:** FastAPI (Python 3.11), SQLAlchemy, PostgreSQL (15), ChromaDB (0.5.23)
* **Frontend:** Next.js (TypeScript, Tailwind CSS, App Router)
* **AI Engine:** Google Gemini API (`text-embedding-004` & `gemini-1.5-flash`) with Mock Fallback provider
* **Infrastructure:** Docker & Docker Compose

---

## Implemented Core Features

1. **Lore Knowledge Base (RAG)**
   - Text extraction (TXT, MD, PDF) and whitespace boundary chunking.
   - Vector embeddings generation (`text-embedding-004`) with Cosine distance indexing in ChromaDB.
   - Semantic query console with source citations, similarity score mapping, and confidence ratings.

2. **NPC Studio & Dialogue Debugger**
   - NPC profile management (create, update, soft-delete with exclusion flags).
   - Dialogue prompt assembly pipeline with manual RAG chunk checklist selection.
   - Interactive live chat debugger with support for custom models and multi-turn conversation persistence.

3. **World Knowledge Graph & Memory Engine**
   - Node entities, directed relationships, and BFS/DFS graph traversals.
   - Episodic NPC memory with importance scoring.
   - Graph-aware memory ranking: adjacent entities in the graph receive vector search score boosts.

4. **Progressive Hint Studio**
   - Progressive hint escalation (Level 1 → Level 2 → Level 3).
   - Enforces sequential levels, rate-limiting cooldown timers, and telemetry validation.
   - Interactive testing panel for Player ID, Quest ID, and Hint Level with real-time countdown display and validation error banners.

5. **Analytics & Telemetry Dashboard**
   - KPI metrics for total API calls, token usage, cost estimation, and cache stats.
   - Dedicated Progressive Hint telemetry section (`hints_generated_total`, `cache_hits`, `cache_misses`, `cooldown_blocks`).
   - Logging table for auditing telemetry metrics and LLM responses.

---

## Setup Instructions

### Prerequisites
1. **Docker Desktop** installed and running on your system.
2. A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/) (optional, fallbacks to Mock provider if missing).
3. **Node.js** (v18+) installed on your host machine to run the frontend.

### Canonical Development Setup

1. **Configure Environment Variables**:
   Copy `.env.example` to `.env` in the project root:
   ```bash
   cp .env.example .env
   ```
   Modify `.env` to configure settings:
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gamemind
   CHROMA_HOST=localhost
   CHROMA_PORT=8000
   GEMINI_API_KEY=your_real_gemini_api_key_here
   LLM_PROVIDER=mock
   GEMINI_MODEL=gemini-1.5-flash
   ```

2. **Start Services via Docker Compose**:
   Run the following from the root directory:
   ```bash
   docker compose up -d --build
   ```
   This initializes:
   - **PostgreSQL Database** (`gamemind_db`) exposed on host port `5432`.
   - **ChromaDB Server** (`gamemind_chroma` running image `0.5.23` with telemetry disabled) mapped to host port `8001`.
   - **FastAPI Backend Server** (`gamemind_backend`) exposed on host port `8000`.

3. **Start Frontend Locally**:
   From the `frontend` directory:
   ```bash
   npm install
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) to view the developer dashboard.

---

## Quality Gates and Verification

The system maintains strict production-level quality gates:

- **Backend Verification:** 97/97 tests passing cleanly (`pytest`) with defensive query clamping to prevent HNSW contiguous array exceptions when query sizes exceed collection counts.
- **Frontend Verification:** `npm run lint` passes with 0 errors and 0 warnings.
- **Offline Builds:** Production builds (`npm run build`) complete successfully without internet access (using a local system font stack fallback instead of loading Google Fonts from the network).
- **Docker Connectivity:** Connects directly via `chromadb.HttpClient` without local fallback or PostHog telemetry error logs.
