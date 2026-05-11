#!/bin/bash

set -e

GHCR_OWNER=${GHCR_OWNER:-bihealth}
GHCR_IMAGE=${GHCR_IMAGE:-cbio-ingest}
GHCR_TAG=${GHCR_TAG:-latest}

IMAGE=ghcr.io/$GHCR_OWNER/$GHCR_IMAGE:$GHCR_TAG

echo "Logging in to GHCR ..."
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_OWNER" --password-stdin

echo "Building Docker image ..."
docker build \
  -f docker/Dockerfile \
  -t $IMAGE \
  .

echo "Pushing Docker image ..."
docker push $IMAGE

echo "Finished!"
