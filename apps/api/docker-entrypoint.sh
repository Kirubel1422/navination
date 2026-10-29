#!/bin/sh
# Migrate, import the reviewed seed (idempotent), remove expired guest sessions, then serve.
set -e
python -m alembic upgrade head
python -m app.cli seed
python -m app.cli cleanup-sessions
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
