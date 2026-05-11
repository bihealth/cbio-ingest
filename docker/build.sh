#!/bin/bash

set -e

IMAGE=localhost:5000/cbio-ingest:dev

echo "Building Docker image ..."
docker build \
  -f docker/Dockerfile \
  -t $IMAGE \
  .

echo "Pushing Docker image ..."
docker push $IMAGE

echo "Finished!"
