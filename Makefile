-include .env
export

.PHONY: install
install:
	uv sync

.PHONY: format
format:
	uv run ruff format .

.PHONY: check
check:
	uv run ruff check .
	uv run ruff format --check .

.PHONY: type
type:
	uv run pyrefly check

.PHONY: fix
fix:
	uv run ruff check . --fix

.PHONY: test
test:
	uv run pytest --cov=app --cov-report=html --cov-report=term-missing

.PHONY: token
token:
	uv run python utils/generate_token.py

.PHONY: serve
serve:
	uv run fastapi dev

.PHONY: redis
redis:
	uv run redis

.PHONY: worker
worker:
	uv run rq worker --with-scheduler

.PHONY: docker
docker:
	bash docker/build.sh

.PHONY: migrate
migrate:
	uv run alembic upgrade head

.PHONY: migration
migration:
	uv run alembic revision --autogenerate -m "$(msg)"
# usage: make migration msg="add foo column"

.PHONY: rollback
rollback:
	uv run alembic downgrade -1

.PHONY: history
history:
	uv run alembic history --verbose

.PHONY: current
current:
	uv run alembic current
