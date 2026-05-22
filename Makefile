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
	uv run pyright

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

.PHONY: db-migrate
db-migrate:
	uv run alembic upgrade head

.PHONY: db-migration
db-migration:
	uv run alembic revision --autogenerate -m "$(msg)"
# usage: make db-migration msg="add foo column"

.PHONY: db-rollback
db-rollback:
	uv run alembic downgrade -1

.PHONY: db-history
db-history:
	uv run alembic history --verbose

.PHONY: db-current
db-current:
	uv run alembic current
