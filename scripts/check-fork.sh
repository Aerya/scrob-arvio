#!/usr/bin/env bash
set -euo pipefail
(cd backend && PYTHONPATH=. uv run --with pytest --with aiosqlite --with pytest-asyncio python -m pytest -q tests)
docker build -t scrob-fork-check .
docker build --target frontend-builder -t scrob-frontend-check .
docker run --rm --network none --entrypoint npm scrob-frontend-check test
bash scripts/check-migrations.sh
python3 security/emudhra/check-image.py scrob-fork-check --runtime python --python /app/backend/.venv/bin/python
python3 security/emudhra/check-image.py scrob-fork-check --runtime node
