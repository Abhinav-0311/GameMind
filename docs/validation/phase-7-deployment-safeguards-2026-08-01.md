# Phase 7 Deployment Safeguards Validation

Date: 2026-08-01

## Scope

Phase 7 hardens the existing self-hosted Compose topology without selecting a
public cloud, adding a paid service, or pretending the private technical beta is
a public SaaS. The phase covers overload behavior, request correlation,
dependency readiness, container privilege, smoke verification, and real
PostgreSQL restore evidence.

Long-running NVIDIA graph execution still occurs in the initiating API request.
Moving hosted workflows behind a durable worker queue remains a separate
architecture phase because it changes execution and deployment semantics.

## Implemented safeguards

- Database pool timeout reduced from 30 seconds to five seconds.
- SQLAlchemy capacity failures return HTTP 503 with a stable error code and
  `Retry-After: 2` instead of appearing as an internal crash.
- `/health` and `/ready` include pool capacity, checked-out connections,
  availability, and saturation without exposing credentials.
- A saturated pool degrades readiness immediately instead of attempting another
  connection checkout.
- Every response receives a validated `X-Request-ID` and
  `X-Response-Time-Ms`; one JSON operational log records method, path, status,
  duration, and request ID without body or query-string data.
- Production backend and frontend images run as non-root users.
- The backend Docker context excludes local environments, caches, vector data,
  and test artifacts; production image names are isolated from development
  image tags.
- A standard-library smoke command validates `/health` and `/ready` with bounded
  startup retries.
- GitHub Actions runs the smoke command and validates the production Compose
  topology.
- The test database engine now uses the same pool settings as the application.
- A PowerShell restore verifier uses PostgreSQL's real `pg_dump` and
  `pg_restore`, restores only into `gamemind_restore_verify`, checks schema and
  migration evidence, and cleans up.

## Restore evidence

The local development database was dumped and restored successfully into the
dedicated temporary database:

```text
Public tables: 37
Alembic revision: a4c5d6e7f8b9
```

The verifier removed the temporary restore database and dump afterward. No
source data or Docker volumes were reset.

## Runtime evidence

The smoke checker passed on its first attempt against the running backend:

```text
/health: 200 healthy
/ready: 200 healthy
database pool: 0 checked out, 15 available
ChromaDB: healthy
```

The real-pool saturation integration test checks out the configured connection
budget, confirms a retryable 503 within the bounded timeout, releases every
connection in `finally`, and asserts zero remaining checkouts.

The supported load regression remained green after these changes:

| Workers | Completed | Errors | Timeouts | p95 |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 5 | 0 | 0 | 1.15 s |
| 10 | 10 | 0 | 0 | 1.66 s |
| 15 | 15 | 0 | 0 | 2.67 s |

## Operational boundary

These checks establish repeatable self-hosted deployment safeguards. Before a
public launch, GameMind still needs a chosen host, HTTPS/reverse-proxy policy,
SMTP credentials, external uptime/error monitoring, encrypted off-host backup
retention, and deployment-level capacity testing. Backend pytest sessions must
run serially unless each process receives a unique disposable database; two
sessions must never drop/create the same `gamemind_test` schema concurrently.

## Verification gates

```text
Backend: 220 passed, 1 load test deselected
Frontend lint: passed
Frontend production build: passed (Next.js 16.2.12)
Production Compose config: valid
Backend production image: built; uid=10001(gamemind)
Frontend production image: built; uid=1000(node)
Frontend production image smoke: HTTP 200
Production smoke: passed
PostgreSQL backup/restore: passed
git diff --check: passed
```

Next.js and PostCSS were patched from 16.2.9/8.5.10 to
16.2.12/8.5.18 after the production dependency audit. The latest stable
Next.js still declares Sharp `^0.34.5`, while the current Sharp security fix is
in the incompatible 0.35 major. GameMind does not force an unsupported
override. This upstream constraint must be re-audited and resolved before a
public launch.
