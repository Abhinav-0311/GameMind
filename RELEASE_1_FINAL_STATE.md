# GameMind: Release 1 Final State Specification

This document serves as the frozen reference for the final state of **Release 1 (Foundation Platform)**. It locks in the directory layout, endpoints, database entities, environment configurations, frontend pages, known limits, and dependencies.

---

## 1. Final Folder Tree

```text
E:\College\Project\Bot/
├── docker-compose.yml
├── README.md
├── .env.example
├── .env
├── ember_siege.txt
├── ARCHITECTURE.md
├── RELEASE_1_RETROSPECTIVE.md
├── RELEASE_2_PLAN.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── test_main.py
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── schemas.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── documents.py
│       │       └── query.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── document.py
│       └── services/
│           ├── __init__.py
│           ├── gemini_service.py
│           └── rag_service.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── postcss.config.mjs
    ├── eslint.config.mjs
    ├── tailwind.config.js (or equivalent configured in globals.css)
    ├── public/
    │   ├── favicon.ico
    │   ├── file.svg
    │   ├── globe.svg
    │   ├── next.svg
    │   ├── vercel.svg
    │   └── window.svg
    └── src/
        ├── components/
        │   └── DashboardLayout.tsx
        ├── lib/
        │   └── api.ts
        └── app/
            ├── globals.css
            ├── layout.tsx
            ├── page.tsx
            ├── knowledge/
            │   └── page.tsx
            └── query/
                └── page.tsx
```

---

## 2. All Backend Endpoints

### Core Health Check
- **`GET /health`**
  - **Purpose:** Checks connectivity status of PostgreSQL, ChromaDB, and verifies if the `GEMINI_API_KEY` is loaded.
  - **Response:**
    ```json
    {
      "status": "healthy" | "degraded",
      "database": "healthy" | "unhealthy",
      "chromadb": "healthy" | "unhealthy",
      "gemini_api": "configured" | "not_configured"
    }
    ```

### Ingestion System (Knowledge Base)
- **`POST /api/v1/documents/upload`**
  - **Purpose:** Synchronously processes a text/markdown/PDF file. Extracts text, chunks content, commits metadata to PG, vectors content using Gemini API (`text-embedding-004`), and stores vectors in ChromaDB.
  - **Constraints:** Max file size 5 MB.
  - **Response:** `DocumentResponse`
- **`GET /api/v1/documents`**
  - **Purpose:** Retrieves a list of metadata for all ingested documents (with chunk counts).
  - **Response:** `List[DocumentResponse]`
- **`GET /api/v1/documents/{document_id}`**
  - **Purpose:** Retrieves detailed metadata and a complete array of generated chunks for a specific document.
  - **Response:** `DocumentDetailResponse`
- **`DELETE /api/v1/documents/{document_id}`**
  - **Purpose:** Cascade deletes document and chunks metadata from PostgreSQL, and deletes vector IDs from ChromaDB.
  - **Response:** HTTP 204 No Content

### Retrieval Sandbox (Query Studio)
- **`POST /api/v1/query`**
  - **Purpose:** Embeds a natural language search query using Gemini, executes a Cosine similarity search in ChromaDB, converts distances to percentages, maps confidence ratings, and returns citation cards.
  - **Response:** `QueryResponse`

---

## 3. Database Schema

### `documents` Table
* `id` (`UUID`, Primary Key, default `gen_random_uuid()`)
* `title` (`VARCHAR(255)`, Not Null)
* `content_type` (`VARCHAR(50)`, Not Null)
* `file_path` (`VARCHAR(512)`, Nullable)
* `created_at` (`TIMESTAMP WITH TIME ZONE`, default `CURRENT_TIMESTAMP`)
* `updated_at` (`TIMESTAMP WITH TIME ZONE`, default `CURRENT_TIMESTAMP`)

### `document_chunks` Table
* `id` (`UUID`, Primary Key, default `gen_random_uuid()`)
* `document_id` (`UUID`, Foreign Key referencing `documents.id` ON DELETE CASCADE)
* `chunk_index` (`INT`, Not Null)
* `content` (`TEXT`, Not Null)
* `metadata` (`JSONB`, Nullable)
* `created_at` (`TIMESTAMP WITH TIME ZONE`, default `CURRENT_TIMESTAMP`)

---

## 4. Environment Configurations (`.env`)

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/gamemind
CHROMA_HOST=chromadb
CHROMA_PORT=8000
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 5. Frontend Pages

- **Workspace Overview (`/`):** High-density project catalog list table (retrieving real chunk and token count values from the database), recent search logs, and a sidebar dashboard of active system configurations.
- **Knowledge Base (`/knowledge`):** Stripe-style file drag-and-drop ingestion interface (with size verification <5 MB), lists documents table, and a right-aligned Chunk Inspector panel linking document selection to the details API.
- **Query Studio (`/query`):** Command search box (`Ctrl + K` palette support), historical queries tag listing, and citation search result cards displaying similarity match ratings.

---

## 6. Known Limitations
- **Synchronous Upload Blocks:** Processing files takes 1-3 seconds per MB during chunking and vector embedding API roundtrips. The 5 MB limit keeps the thread from timing out.
- **Strict Key Requirement:** The query system will throw HTTP 503 errors if `GEMINI_API_KEY` is not loaded in `.env`.
- **Estimate Tokens:** Monospace token count columns are computed on the client side (`chunks_count * 250`) to keep the DB schema simple.

---

## 7. Third-Party Dependencies

### Backend dependencies (`backend/requirements.txt`)
- `fastapi==0.111.0` (REST Framework)
- `uvicorn==0.30.1` (ASGI Web Server)
- `sqlalchemy==2.0.31` (SQL ORM)
- `psycopg2-binary==2.9.9` (PostgreSQL Connector)
- `chromadb==0.5.0` (Vector Database SDK)
- `google-genai==0.1.1` (New Google Gemini SDK)
- `pypdf==4.2.0` (PDF Extraction Utility)
- `python-multipart==0.0.9` (Multi-part Upload Handler)
- `pydantic-settings==2.3.4` (Pydantic Configuration Manager)
- `python-dotenv==1.0.1` (Environment Variable Parser)
- `pytest==8.2.2` (Testing framework)
- `httpx==0.27.0` (Async HTTP client for test suites)

### Frontend dependencies (`frontend/package.json`)
- `next` (React Framework)
- `react` / `react-dom`
- `tailwindcss` (Styling utility)
- `typescript` (Static typing checker)
- `eslint` (Linting compiler checks)
