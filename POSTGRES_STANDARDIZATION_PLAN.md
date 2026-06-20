# PostgreSQL Database Standardization Plan

> Historical Document
> Superseded by runtime_environment_audit.md
> Retained for project history only.

This plan details the steps, configurations, and verification procedures required to standardize GameMind on the native Windows PostgreSQL service, resolving localhost port conflicts and database ambiguity.

## A. Current State

Currently, both PostgreSQL instances are running on the system:
1. **Windows PostgreSQL Service (`postgresql-x64-18`)**: Active, listening on both IPv4 (`0.0.0.0:5432`) and IPv6 (`[::]:5432`).
2. **Docker PostgreSQL Container (`gamemind_db`)**: Active, but unable to bind port 5432 on the host because the Windows service had already occupied it. It runs in an isolated container network namespace.

When GameMind or pytest connects to `localhost:5432`, the connection resolves to the IPv6 address `::1` and links directly to the **Windows PostgreSQL service**. The Docker container `db` is completely bypassed.

---

## B. Proposed Final State

Standardize the storage and vector tier by officially deprecating both Docker PostgreSQL and Docker ChromaDB containers:
* **Database**: Native Windows PostgreSQL 18.4 database (`gamemind`) accessed via `localhost:5432`.
* **Vector DB**: Local Chroma PersistentClient (`backend/chroma_db_local`) accessed via SQL loopback, eliminating Docker Desktop engine runtime dependencies for local development.

```mermaid
graph TD
    subgraph Host [Host Windows Machine]
        FastAPI[FastAPI Backend]
        NextJS[Next.js Frontend Client]
        WinPG[(Windows PostgreSQL 18.4 :5432)]
        LocalChroma[(Local ChromaDB SQLite :chroma_db_local)]
    end

    FastAPI -->|localhost:5432| WinPG
    FastAPI -->|sqlite local| LocalChroma
    NextJS -->|HTTP localhost:8000| FastAPI
```

---

## C. Files Requiring Modification

1. **[docker-compose.yml](file:///E:/College/Project/Bot/docker-compose.yml)** `[MODIFY]`: Remove the `db` service definition and its volume declarations.
2. **[backend/.env](file:///E:/College/Project/Bot/backend/.env)** `[DELETE]`: Delete this duplicate `.env` file to prevent configuration drift, leaving the root `.env` as the single source of truth.
3. **[README.md](file:///E:/College/Project/Bot/README.md)** `[MODIFY]`: Update the startup instructions to reflect that only ChromaDB needs to be started via Docker, while PostgreSQL runs as a host service.

---

## D. Docker Compose Changes Required

In `docker-compose.yml`, delete the `db` service block:

```diff
-  db:
-    image: postgres:15-alpine
-    container_name: gamemind_db
-    environment:
-      - POSTGRES_USER=postgres
-      - POSTGRES_PASSWORD=postgres
-      - POSTGRES_DB=gamemind
-    ports:
-      - "5432:5432"
-    volumes:
-      - postgres_data:/var/lib/postgresql/data
-    networks:
-      - gamemind-network
```

Also, remove `postgres_data` from the top-level `volumes` block:

```diff
 volumes:
-  postgres_data:
   chroma_data:
```

---

## E. Environment Variable Changes Required

Ensure the single canonical root `.env` contains:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gamemind
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

Delete `E:\College\Project\Bot\backend\.env` to guarantee that the backend only loads the root `.env`.

---

## F. Verification Procedure

1. **Stop and prune Docker containers**:
   We can stop and prune all containers, as no Docker containers are required for local development:
   ```powershell
   docker compose down -v
   ```

3. **Verify active database version**:
   Run the `db_check.py` audit script to confirm connection to MSVC PostgreSQL 18.4:
   ```powershell
   E:\Tools\Anaconda\python.exe C:\Users\Abhinav Jain\.gemini\antigravity\brain\08391982-afcb-4fcb-a68f-15e4d6f41cd9\scratch\db_check.py
   ```

4. **Run backend integration test suite**:
   ```powershell
   cd E:\College\Project\Bot\backend
   E:\Tools\Anaconda\python.exe -m pytest -v
   ```
   *All 17 tests must pass.*

---

## G. Rollback Procedure

To revert the standardization and go back to using containerized PostgreSQL:
1. Re-add the `db` service definition and the `postgres_data` volume to `docker-compose.yml`.
2. Stop the local Windows PostgreSQL service:
   ```powershell
   Stop-Service -Name postgresql-x64-18
   ```
3. Run `docker compose up -d` to rebuild and launch the containerized database.
