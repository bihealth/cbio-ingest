#!/bin/bash

set -e

echo "Building Docker image ..."

docker build \
  -f docker/Dockerfile \
  -t $IMAGE \
  .

echo "Finished!"
