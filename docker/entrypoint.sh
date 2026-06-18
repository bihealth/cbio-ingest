#!/bin/bash
set -euo pipefail

if [[ "$1" == "serve" ]]; then
  echo "Running database migrations ..."
  alembic upgrade head
  exec uvicorn app.main:app --host "0.0.0.0" --port "8000"

elif [[ "$1" == "worker" ]]; then
  exec rq worker --with-scheduler

else
  exec "$@"
fi
