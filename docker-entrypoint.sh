#!/bin/sh
set -e

# Run pending migrations before the app starts serving traffic — keeps
# schema upgrades out of the list of things SysOps has to remember as a
# manual deploy step.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
