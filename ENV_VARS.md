# Environment Variables

For SysOps deployment. Every variable the app reads, in one place —
`app/config.py`'s `Settings` class is the single source of truth; this file
mirrors it exactly and `.env.example` gives runnable example values. Secrets
arrive as environment variables injected at deploy time — **the app never
fetches secrets from a vault/service itself.**

| Variable | Required | Purpose | Example |
|---|---|---|---|
| `ENV` | No (default `dev`) | Runtime environment: `dev` \| `staging` \| `prod`. Gates `AUTH_MODE=dev` — the app refuses to boot if `AUTH_MODE=dev` and `ENV` isn't `dev`. | `prod` |
| `DATABASE_URL` | Yes | SQLAlchemy connection string for Postgres. | `postgresql+psycopg2://cig:cig@postgres:5432/cig` |
| `AUTH_MODE` | No (default `dev`) | Identity resolution mechanism: `header` (reads an identity header set by an upstream reverse-proxy/SSO, e.g. oauth2-proxy or ALB+OIDC), `jwt` (reads `Authorization: Bearer <jwt>` and extracts an email claim), or `dev` (local development only, reads `DEV_USER_EMAIL`). See `app/auth.py`. | `header` |
| `AUTH_HEADER_NAME` | No (default `X-Auth-Request-Email`) | Header name to read the identity email from when `AUTH_MODE=header`. | `X-Auth-Request-Email` |
| `AUTH_JWT_SECRET` | Only if `AUTH_MODE=jwt` and no JWKS URL | HMAC secret for verifying JWTs. Mutually exclusive in practice with `AUTH_JWT_JWKS_URL` — one of the two is required when `AUTH_MODE=jwt`. | *(secret, no example)* |
| `AUTH_JWT_JWKS_URL` | Only if `AUTH_MODE=jwt` and no secret | JWKS endpoint URL for verifying RS256-signed JWTs from an OIDC provider. | `https://sso.alnafi.internal/.well-known/jwks.json` |
| `AUTH_JWT_EMAIL_CLAIM` | No (default `email`) | Which JWT claim holds the user's email. | `email` |
| `DEV_USER_EMAIL` | Only if `AUTH_MODE=dev` | The identity every request resolves to in dev mode. | `dev@alnafi.local` |
| `SESSION_SECRET_KEY` | Yes (change from default in any real deployment) | Signs the one-shot flash-message session cookie (not general app state — see `app/main.py`). | *(random 32+ char string)* |
| `STORAGE_BACKEND` | No (default `local`) | `local` (filesystem, served via the app's own `/media/{key}` route) or `s3` (S3-compatible object storage). | `s3` |
| `STORAGE_LOCAL_ROOT` | Only if `STORAGE_BACKEND=local` | Filesystem root for the local storage backend. | `./data/storage` |
| `S3_BUCKET` | Only if `STORAGE_BACKEND=s3` | Target S3 bucket name. | `alnafi-cig-prod` |
| `S3_REGION` | Only if `STORAGE_BACKEND=s3` | AWS region for the bucket. | `me-central-1` |
| `S3_ENDPOINT_URL` | No | Overrides the S3 endpoint — set this to point at MinIO or another S3-compatible target for local testing without real AWS credentials. Leave unset for real AWS S3. | `http://minio:9000` |
| `ANTHROPIC_API_KEY` | Yes | Claude API key for the content-writing LLM (research/write/refine stages). | *(secret, no example)* |
| `TAVILY_API_KEY` | Yes | Tavily web-search API key for the research stage. | *(secret, no example)* |
| `OPENAI_API_KEY` | Yes (for OpenAI image providers) | OpenAI API key for `gpt-image-1`/`gpt-image-2` image generation and translation. | *(secret, no example)* |
| `GEMINI_API_KEY` | Yes (for Gemini image provider) | Google Gemini API key for the Imagen-3 image provider. | *(secret, no example)* |
| `ALNAFI_DB_PATH` | No (default `./data/alnafi_pipeline.db`) | Path to the legacy SQLite DB — only read by the one-off `scripts/migrate_sqlite_to_postgres.py` migration script, not by the running app. | `./data/alnafi_pipeline.db` |
| `MIGRATION_FALLBACK_USER_EMAIL` | Only when running the migration script | The user every migrated row is attributed to (the original SQLite data has no per-row user). | `migration@alnafi.local` |

## Notes for SysOps

- **CSRF**: not explicitly handled by the app — deferred to whichever
  reverse-proxy/SSO mechanism is chosen for `AUTH_MODE`. Some setups (e.g.
  same-site cookies via oauth2-proxy) make explicit CSRF tokens redundant;
  others don't. Worth a decision once the auth vendor is picked.
- **No Kubernetes manifests or Helm charts are included** — this repo only
  ships app code, the `Dockerfile`, and `docker-compose.yml` (for local
  dev). Deployment manifests are SysOps' responsibility.
- The container's `docker-entrypoint.sh` runs `alembic upgrade head` before
  starting `uvicorn` — migrations are not a manual deploy step.
- Health check endpoint: `GET /healthz` (does a real `SELECT 1` against
  Postgres, not just a liveness ping).
