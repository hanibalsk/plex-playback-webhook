#!/bin/bash

# Ensure Docker Buildx is enabled
# Example run with registry: REGISTRY=registry.rlt.sk ./build.sh
docker buildx create --use || echo "Buildx already set up"

# Set default image name if not provided
REGISTRY=${REGISTRY:-}
if [ -z "$REGISTRY" ]; then
  IMAGE_NAME=${1:-plex-webhook-docker:latest}
else
  IMAGE_NAME=${1:-$REGISTRY/plex-webhook-docker:latest}
fi

# Build the Docker image for multiple platforms
BUILD_CMD="docker buildx build --platform linux/amd64,linux/arm64 -t $IMAGE_NAME . --push"

# Check if the last commit is tagged and append the tag to the image if it exists
LAST_TAG=$(git describe --tags --exact-match 2>/dev/null)
if [ -n "$LAST_TAG" ]; then
  TAGGED_IMAGE_NAME="${IMAGE_NAME%:*}:$LAST_TAG"
  BUILD_CMD="$BUILD_CMD -t $TAGGED_IMAGE_NAME"
fi

# Execute the build command
$BUILD_CMD

# Check if the last commit is tagged and append the tag to the image if it exists
LAST_TAG=$(git describe --tags --exact-match 2>/dev/null)
if [ -n "$LAST_TAG" ]; then
  TAGGED_IMAGE_NAME="${IMAGE_NAME%:*}:$LAST_TAG"
  docker buildx build --platform linux/amd64,linux/arm64 -t $TAGGED_IMAGE_NAME . --push
  echo "Multi-platform Docker image built and pushed with tag: $LAST_TAG"
fi

# Notify user of successful build
if [ -z "$REGISTRY" ]; then
  echo "Multi-platform Docker image built and pushed with image name: $IMAGE_NAME"
else
  echo "Multi-platform Docker image built and pushed to registry: $REGISTRY with image name: $IMAGE_NAME"
fi
