#!/usr/bin/env bash
# Create and push a version tag based on the repo-root VERSION file.
#
# Usage:
#   bash scripts/tag_release.sh
#   bash scripts/tag_release.sh --yes
#   bash scripts/tag_release.sh --yes --skip-existing
#
# The script:
# 1. Reads VERSION
# 2. Derives the release tag as v<VERSION>
# 3. Verifies the tag does not already exist locally or on origin
# 4. Creates an annotated tag
# 5. Pushes the tag to origin

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${REPO_ROOT}/VERSION"
AUTO_CONFIRM=0
SKIP_EXISTING=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes|-y)
      AUTO_CONFIRM=1
      ;;
    --skip-existing)
      SKIP_EXISTING=1
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      echo "Usage: bash scripts/tag_release.sh [--yes] [--skip-existing]" >&2
      exit 1
      ;;
  esac
  shift
done

if [ ! -f "$VERSION_FILE" ]; then
  echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [ -z "$VERSION" ]; then
  echo "ERROR: VERSION file is empty" >&2
  exit 1
fi

TAG="v${VERSION}"
TAG_MESSAGE="Release ${TAG}"
CURRENT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"

if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  echo "ERROR: Working tree is not clean. Commit or stash changes before tagging." >&2
  exit 1
fi

if git -C "$REPO_ROOT" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
  if [ "$SKIP_EXISTING" -eq 1 ]; then
    echo "Local tag ${TAG} already exists. Skipping."
    exit 0
  fi
  echo "ERROR: Local tag ${TAG} already exists" >&2
  exit 1
fi

if git -C "$REPO_ROOT" ls-remote --exit-code --tags origin "refs/tags/${TAG}" >/dev/null 2>&1; then
  if [ "$SKIP_EXISTING" -eq 1 ]; then
    echo "Remote tag ${TAG} already exists on origin. Skipping."
    exit 0
  fi
  echo "ERROR: Remote tag ${TAG} already exists on origin" >&2
  exit 1
fi

echo "VERSION: ${VERSION}"
echo "Branch: ${CURRENT_BRANCH}"
echo "Tag: ${TAG}"
echo "Commands:"
echo "  git tag -a ${TAG} -m \"${TAG_MESSAGE}\""
echo "  git push origin ${TAG}"

if [ "$AUTO_CONFIRM" -ne 1 ]; then
  read -r -p "Proceed? [y/N] " CONFIRM
  case "$CONFIRM" in
    y|Y|yes|YES)
      ;;
    *)
      echo "Aborted."
      exit 0
      ;;
  esac
fi

git -C "$REPO_ROOT" tag -a "$TAG" -m "$TAG_MESSAGE"
git -C "$REPO_ROOT" push origin "$TAG"

echo "Pushed ${TAG} to origin."
