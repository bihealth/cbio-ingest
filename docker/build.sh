#!/bin/bash

set -e

echo "Building Docker image ..."

IMAGE=cbio-ingest:dev

docker build \
  --build-arg HTTP_PROXY=$http_proxy \
  --build-arg HTTPS_PROXY=$https_proxy \
  --build-arg NO_PROXY=$no_proxy \
  -f docker/Dockerfile \
  -t $IMAGE \
  .

if docker ps | grep registry | grep "5000->5000"; then
  docker push localhost:5000/$IMAGE
else
  echo Local registry not running, not pushing.
fi

echo "Finished!"
