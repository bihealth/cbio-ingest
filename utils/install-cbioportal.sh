#!/bin/bash

set -e

INSTALL_DIR="${1}"
FORCE=false

if [[ "${2}" == "--force" ]]; then
  FORCE=true
fi

if [[ -z "${INSTALL_DIR}" ]]; then
  echo "Usage: $0 <install-dir> [--force]" >&2
  exit 1
fi

if [[ -d "${INSTALL_DIR}" ]] && [[ "${FORCE}" != true ]]; then
  echo "Error: directory ${INSTALL_DIR} already exists" >&2
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "Error: docker compose is not available." >&2
  exit 1
fi

set -x

git clone git@github.com:cbioportal/cbioportal-docker-compose.git $INSTALL_DIR

cd $INSTALL_DIR

bash init.sh
mkdir -p panel db

wget \
  -O docker-compose.override.yml \
  https://github.com/bihealth/cbio-ingest/raw/refs/heads/main/docker/docker-compose.override.yml
wget \
  -O .env.cbio-ingest \
  https://github.com/bihealth/cbio-ingest/raw/refs/heads/main/docker/env.example

docker compose pull
docker compose up -d

set +x

cat <<EOF

=== Everything set up & started! ===

# check if containers are healthy:

cd ${INSTALL_DIR}
docker compose ps
docker compose logs --follow

# note: for the next 10 minutes or so, the database initializes and you will see:
#
# cbioportal-container | Database not available yet (first time can take a few
#                        minutes to load seed database)... Attempting reconnect...

# navigate to:

http://localhost:8080 (cbioportal)
http://localhost:8000 (cbio-ingest)

# the api documentation is available at:

http://localhost:8000/docs

# you might want to install the cli for cbio-ingest:

https://github.com/bihealth/cbio-ingest-cli
EOF
