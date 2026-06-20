# GameMind - AI-Powered Game Development Dashboard

GameMind is an AI narrative engine and developer platform that lets game studios and indie developers upload game lore, extract and chunk text, generate vector embeddings, and run semantic queries against their lore knowledge base.

This is **Release 1 (MVP)**, which focuses on the core developer dashboard, vector search (RAG) pipelines, and API integrations.

---

## Technical Stack

* **Backend:** FastAPI, Python, SQLAlchemy, PostgreSQL, ChromaDB (Vector DB)
* **Frontend:** Next.js (TypeScript, Tailwind CSS, App Router)
* **AI Engine:** Gemini API (`text-embedding-004`)
* **Infrastructure:** Docker & Docker Compose

---

## Project Structure

```text
gamemind/
├── backend/            # FastAPI backend application
│   ├── app/            # Source code package
│   ├── main.py         # App entrypoint & health checks
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/           # Next.js web application
├── ember_siege.txt     # Fictional lore document for testing
├── .env.example        # Environment variables template
├── docker-compose.yml  # Docker Compose config
└── README.md
```

---

## Setup Instructions

### Prerequisites
1. **Docker Desktop** installed and running on your system.
2. A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/) (required if running with live LLM).
3. **Node.js** (v18+) installed on your host machine for the frontend.

### Canonical Development Setup (Recommended)

1. **Configure Environment Variables**:
   Copy `.env.example` to `.env` in the project root:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and replace settings:
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gamemind
   CHROMA_HOST=localhost
   CHROMA_PORT=8000
   GEMINI_API_KEY=your_real_gemini_api_key_here
   LLM_PROVIDER=mock
   GEMINI_MODEL=gemini-1.5-flash
   ```

2. **Docker Compose Orchestration**:
   Start the backend, database, and ChromaDB servers inside Docker containers by running:
   ```bash
   docker compose up --build
   ```
   This initializes the unified network mapping:
   * **Active Canonical Network Mapping**:
     * Inside Container Network: Backend connects to PostgreSQL at `db:5432` and ChromaDB at `chromadb:8000` (HttpClient mode).
     * Windows Host Mapping: PostgreSQL port `5432` is forwarded to `localhost:5432`. ChromaDB server port `8000` is forwarded to host port `8001` (to prevent host conflicts).
   * **FastAPI Backend Server**: Available at [http://localhost:8000](http://localhost:8000) (Docs: [http://localhost:8000/docs](http://localhost:8000/docs)).

3. **Start Frontend Locally**:
   From the `frontend` directory on your Windows host:
   ```bash
   npm install
   npm run dev
   ```
   * Open [http://localhost:3000](http://localhost:3000) to view the developer dashboard.

---

### Alternative Host-Only Setup (Fallback / Local Dev)

If you prefer to run all backend services natively on your Windows host:
1. Ensure a local PostgreSQL service is running on `localhost:5432` with a database named `gamemind`.
2. Install requirements and start uvicorn:
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m uvicorn main:app --reload
   ```
   * The backend will connect to your local Windows PostgreSQL service (`localhost:5432`).
   * Since no containerized Chroma server is active on port 8000 on the host, the RAG service will automatically initialize a local persistent client fallback inside `backend/chroma_db_local`.

---

## Ingesting and Querying Lore

1. **Open the Dashboard**: Go to `http://localhost:3000` and navigate to the **Documents** tab.
2. **Upload Lore**: Drag and drop or browse to select a file (e.g. use `ember_siege.txt`). The file is processed synchronously (text extracted, split into overlapping chunks, vectorized via Gemini, and indexed into ChromaDB).
3. **Query Lore**: Go to the **Lore Query** tab, type a search phrase (e.g. *"Who ruled Frostpeak?"* or *"When did King Arven die?"*), and hit search to inspect matching chunks, similarity ratings, and citations.
