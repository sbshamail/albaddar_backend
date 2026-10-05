SHELL := /bin/bash

run:
	uv run -- uvicorn src.main:app --reload --reload-dir src

runip:
	uv run -- uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --reload-dir src



generate:
	alembic revision --autogenerate -m "auto"

downgrade:
	alembic downgrade -1"

head:
	alembic upgrade head

reset:
	rm -rf .venv
	uv venv .venv
	source .venv/bin/activate && uv pip install -r pyproject.toml && uv pip install psycopg2-binary

gitpush:
	git add . && git commit -m "auto" && git push



