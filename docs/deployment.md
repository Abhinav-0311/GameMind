# Production Deployment

GameMind's local Compose file is for development. Use the separate production definition so application code is immutable, hot reload is disabled, and database migrations run once before the API starts.

## Prerequisites

- Docker Engine with Docker Compose v2.
- A domain or reverse proxy that terminates HTTPS in front of the frontend and backend.
- A private server or reverse proxy that terminates HTTPS. GameMind includes session authentication and project roles, but it is not yet a self-service public SaaS.

## First deployment

1. Copy `.env.production.example` to `.env.production` and replace every placeholder. Keep that file outside Git.
2. Set `CORS_ORIGINS` to the exact dashboard URL and `NEXT_PUBLIC_API_URL` to the public backend URL.
   Production startup rejects a development JWT secret, non-HTTPS CORS origins, or `AUTH_REQUIRED=false`.
3. Build and start the stack:

   ```bash
   docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
   ```

4. Check readiness only after migrations complete:

   ```bash
   curl -f http://localhost:8000/ready
   ```

5. Put HTTPS and your chosen domains in a reverse proxy. The database and Chroma services intentionally have no public ports in the production Compose file.

## Enabling accounts on an existing workspace

1. Deploy with `AUTH_REQUIRED=false` once, then register the first owner through `/login`.
2. Set `BOOTSTRAP_ADMIN_EMAIL` to that exact email and run:

   ```bash
   docker compose --env-file .env.production -f docker-compose.production.yml exec backend \
     python -m app.scripts.bootstrap_owner
   ```

3. Confirm the command reports the expected number of unowned workspaces, then set `AUTH_REQUIRED=true` and redeploy.

The command is idempotent: it assigns only workspaces without any membership and never replaces an existing owner.

## Account lifecycle email

Production account verification, password recovery, and workspace invitations use SMTP. Set `PUBLIC_APP_URL`, `EMAIL_FROM_ADDRESS`, and the `SMTP_*` values in `.env.production`. Startup rejects the example SMTP values while email verification is required.

In local development, `EMAIL_DELIVERY_MODE=disabled` logs the one-time link only. This keeps development free, but it is not email delivery and must never be used for public accounts.

Password reset advances the account session version, so every prior signed-in browser session is invalidated. Invitations are one-time, expire after seven days, and can only be accepted by the invited email address.

## Login abuse protection

The backend applies a process-local sliding-window limit to registration and failed sign-in attempts in production. The default is five attempts in fifteen minutes, configured through `AUTH_RATE_LIMIT_MAX_ATTEMPTS` and `AUTH_RATE_LIMIT_WINDOW_SECONDS`.

This is appropriate for the current single-backend Compose deployment. For multiple backend replicas, enforce the equivalent rule at the reverse proxy or use a shared Redis-backed limiter before scaling out.

## Database connection capacity

The backend uses an explicit, pre-pinged SQLAlchemy connection pool. The
production defaults are five persistent connections and up to ten temporary
overflow connections:

```env
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=1800
```

Keep the total possible application connections within PostgreSQL's connection
budget. For one Uvicorn process, the upper bound is `pool size + max overflow`.
If backend processes are added later, multiply that value by the process count
and leave capacity for migrations, backups, and administration. Do not increase
the pool merely to make a load test pass; measure database wait time and query
latency first.

Run the bounded local regression benchmark from the backend container:

```bash
docker exec gamemind_backend pytest -q -m load test_load_phase10.py -s --disable-warnings
```

This benchmark detects deadlocks, request failures, severe latency regressions,
and retained-memory growth in the single-process Compose topology. It is not a
substitute for a deployment-level test through the production reverse proxy.

## Release procedure

1. Pull a reviewed Git commit.
2. Back up PostgreSQL before schema changes.
3. Run the Compose command above. The `migrate` service runs `alembic upgrade head` once; the backend starts only after it succeeds.
4. Verify `/ready`, then verify the dashboard and one GDD upload in a private workspace.
5. If an application release must be reverted, deploy the earlier application image. Do not downgrade database migrations casually; first confirm that the migration has a safe downgrade path.

## Backup and recovery

Create a PostgreSQL backup before every release and retain copies outside the host:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > gamemind-$(date +%F).sql
```

Restore only into a stopped, isolated environment:

```bash
cat gamemind-backup.sql | docker compose --env-file .env.production -f docker-compose.production.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Chroma's Docker volume contains the retrieval index. Preserve it with the PostgreSQL backup cycle; PostgreSQL document chunks remain the authoritative source and can rebuild the local vector collection.

## Current boundary

This phase establishes repeatable deployment mechanics and baseline account security, not full public-SaaS operations. Email verification, password recovery, workspace invitations, object storage, distributed rate limiting, and managed backup automation remain required before public multi-user deployment.
