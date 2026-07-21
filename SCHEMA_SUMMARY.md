# Database Schema Summary

For DataOps review. This is a **draft schema for a local throwaway Postgres**
(via Docker Compose) that stands in for the eventual shared AI-dept database —
not a finished/immutable design. Everything here is namespaced under a
dedicated Postgres **schema** named `cig` (not a table-name prefix), so it
cannot collide with any other AI-dept module DataOps adds to a shared
instance later: `CREATE SCHEMA IF NOT EXISTS cig`, and every table below
lives at `cig.<table>`.

Managed via SQLAlchemy models (`app/db/models.py`) + Alembic migrations
(`alembic/versions/`). Verified against a live Postgres 16 instance — table
layouts below are copied from `\d cig.*` output, not hand-transcribed.

## Access needs (read this first)

- The app connects with one role (`cig` in this Compose file) that needs
  full DML on schema `cig` and `CREATE SCHEMA`/DDL rights for Alembic
  migrations to run at deploy time (see `docker-entrypoint.sh`).
- **`cig.generated_posts.storage_key` and `cig.translation_jobs.output_storage_key`
  / `source_image_storage_key` are pointers, not the asset.** The actual
  image bytes live wherever `StorageBackend` is configured (local disk in
  dev, S3 in prod — see `ENV_VARS.md`). DataOps needs DB access for the
  metadata tables; separate storage credentials are needed to read the
  actual images.
- `cig.audit_log` is intended to be append-only and read-mostly (compliance/
  audit trail). No code path updates or deletes rows in it.
- No table stores credentials, API keys, or secrets. `cig.users` exists
  purely as an FK anchor for attribution — there is no password column;
  identity is resolved externally (see `ENV_VARS.md`'s `AUTH_MODE`).

## Tables

### `cig.users`
FK anchor for attribution/audit and the "Signed in as X" UI element. Rows
are created lazily on first request (get-or-create by email) — there is no
separate signup flow.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | bigint (PK, identity) | no | |
| `email` | varchar(320) | no | unique |
| `display_name` | varchar(200) | yes | |
| `created_at` | timestamptz | no | |
| `last_seen_at` | timestamptz | yes | refreshed at most once per 5 min per request, to avoid a write on every request |

Referenced by every `created_by_user_id`/`user_id` column below.

### `cig.generations`
Content-generation records (long-form articles and social captions) —
superset of the original SQLite `generations` table.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | bigint (PK, identity) | no | |
| `created_at` | timestamptz | no | indexed |
| `created_by_user_id` | bigint (FK -> `users.id`) | yes | |
| `topic` | text | no | |
| `platform`, `page_promoted`, `content_type`, `audience`, `tone`, `keywords` | text | yes | form inputs, unchanged from the original schema |
| `social_meta` | jsonb | yes | platforms/post_type/goal for social-caption generations (was TEXT-encoded JSON in the original SQLite schema, now real JSONB) |
| `research_brief`, `writer_system`, `writer_human`, `final_content` | text | yes | pipeline stage outputs |
| `output_storage_key` | text | yes | pointer into `StorageBackend` for the markdown copy; **replaces** the original schema's local `filepath` column, which doesn't survive an ephemeral/multi-instance container |

### `cig.generated_posts`
Generated marketing images.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | bigint (PK, identity) | no | |
| `created_at` | timestamptz | no | indexed |
| `created_by_user_id` | bigint (FK -> `users.id`) | yes | |
| `sector`, `post_type`, `canvas_size`, `provider`, `quality`, `headline`, `image_prompt`, `system_prompt` | text | yes | unchanged from the original schema |
| `platforms` | jsonb | yes | was TEXT-encoded JSON originally, now real JSONB |
| `storage_key` | text | no | pointer into `StorageBackend` — **replaces the original schema's `image_data BLOB` column**, which stored raw image bytes directly in SQLite. This is the one genuine schema change the storage-backend requirement forced. |
| `byte_size` | integer | yes | convenience metadata so callers don't need to re-read the object to know its size |
| `content_type` | varchar(100) | no | default `image/png` |
| `generation_id` | bigint (FK -> `generations.id`, `ON DELETE SET NULL`) | yes | indexed; links an image back to the content generation that spawned it (unchanged relationship from the original schema) |

### `cig.translation_batches` / `cig.translation_jobs`
**New tables** — batch translation was not persisted anywhere in the
original app (only produced an in-memory ZIP download). A batch groups N
per-image-per-language translation jobs submitted together.

`cig.translation_batches`:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | uuid (PK) | no | also the grouping key for translation jobs and for storage key paths |
| `created_at` | timestamptz | no | indexed |
| `created_by_user_id` | bigint (FK -> `users.id`) | yes | |
| `total_jobs` | integer | no | |
| `completed_jobs` | integer | no | denormalized counter, incremented atomically per job so the SSE progress endpoint is one cheap row read instead of a `COUNT(*)` |
| `status` | varchar(20) | no | `running` \| `done` |

`cig.translation_jobs`:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | bigint (PK, identity) | no | |
| `created_at` | timestamptz | no | indexed |
| `created_by_user_id` | bigint (FK -> `users.id`) | yes | |
| `batch_id` | uuid (FK -> `translation_batches.id`, `ON DELETE CASCADE`) | no | indexed |
| `source_filename`, `source_image_storage_key` | text | yes | the uploaded source image |
| `target_language`, `provider`, `quality`, `canvas_size` | text | varies | job parameters |
| `output_storage_key` | text | yes | null until the job succeeds |
| `status` | varchar(20) | no | `queued` \| `success` \| `error` |
| `error_message` | text | yes | |
| `usage_json` | jsonb | yes | provider token/usage metadata |
| `elapsed_ms` | integer | yes | |

### `cig.generation_jobs`
**New table** — backs SSE progress for content generation (research → write
→ refine). One row per submitted generation request.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | uuid (PK) | no | |
| `created_at` / `updated_at` | timestamptz | no | `updated_at` bumped on every status change |
| `created_by_user_id` | bigint (FK -> `users.id`) | yes | |
| `job_type` | varchar(30) | no | `long_form` \| `social_captions` |
| `status` | varchar(20) | no | `queued` \| `researching` \| `writing` \| `refining` \| `done` \| `error` |
| `params_json` | jsonb | no | the form inputs needed to run the job |
| `result_generation_id` | bigint (FK -> `generations.id`) | yes | populated once the job reaches `done` |
| `error_message` | text | yes | |

### `cig.audit_log`
**New table** — append-only audit trail for every generation/deletion
action, attributable to a user.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | bigint (PK, identity) | no | |
| `created_at` | timestamptz | no | indexed |
| `user_id` | bigint (FK -> `users.id`) | yes | null for system actions |
| `action` | varchar(100) | no | e.g. `generation.create`, `post.delete` |
| `entity_type` | varchar(50) | yes | |
| `entity_id` | varchar(50) | yes | |
| `metadata` | jsonb | yes | never contains secrets/credentials — enforced by code review convention, not a runtime constraint |

## What did NOT get migrated as-is

The original app's SQLite `generations`/`generated_posts` tables are
migrated into `cig.generations`/`cig.generated_posts` via the one-off
`scripts/migrate_sqlite_to_postgres.py` script (idempotent, never modifies
the source file). The 90 real image BLOBs in the source data were pushed
through the configured `StorageBackend` during that migration and are now
referenced by `storage_key`, not stored inline.
