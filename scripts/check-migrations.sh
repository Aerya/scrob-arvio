#!/usr/bin/env bash
set -euo pipefail
name="scrob-migrations-$$"
trap 'docker rm -fv "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --network none -e POSTGRES_PASSWORD=test-only -e POSTGRES_DB=legacy postgres:17-alpine >/dev/null
for i in {1..30}; do
  if docker exec "$name" pg_isready -U postgres >/dev/null; then break; fi
  sleep 1
done
migrate() {
  docker run --rm --network "container:$name" -e SECRET_KEY=migration-check-only-not-production \
    -e "DATABASE_URL=postgresql+asyncpg://postgres:test-only@127.0.0.1/$1" \
    --entrypoint sh -w /app/backend scrob-fork-check -c "$2"
}
# Simulate the original fork's a1b2 head, missing upstream's Plex column.
migrate legacy '.venv/bin/python -m alembic upgrade a1b2c3d4e5f7'
docker exec "$name" psql -U postgres -d legacy -v ON_ERROR_STOP=1 -c 'ALTER TABLE media_server_connections DROP COLUMN plex_watchlist_synced_keys'
for pass in 1 2; do
  migrate legacy '.venv/bin/python -m migrations.legacy_arvio && .venv/bin/python -m alembic upgrade head'
done
test "$(docker exec "$name" psql -U postgres -d legacy -Atc "SELECT count(*) FROM information_schema.columns WHERE table_name='media_server_connections' AND column_name='plex_watchlist_synced_keys'")" = 1
docker exec "$name" createdb -U postgres fresh
migrate fresh '.venv/bin/python -m migrations.legacy_arvio && .venv/bin/python -m alembic upgrade head'
test "$(docker exec "$name" psql -U postgres -d fresh -Atc "SELECT count(*) FROM information_schema.columns WHERE table_name='user_settings' AND column_name='bingebase_auto_push_interval'")" = 1
