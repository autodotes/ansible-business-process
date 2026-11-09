#!/bin/bash
set -euo pipefail

SUFFIX="${1:?Usage: increment-tag.sh <suffix> <collection-path> <result-file>}"
COLLECTION_PATH="${2:?Usage: increment-tag.sh <suffix> <collection-path> <result-file>}"
RESULT_FILE="${3:?Usage: increment-tag.sh <suffix> <collection-path> <result-file>}"

git config user.email "${GITHUB_ACTOR}@users.noreply.github.com"
git config user.name "${GITHUB_ACTOR}"

write_result() {
  local action="$1"
  local version="${2:-}"
  {
    echo "action=${action}"
    if [ -n "${version}" ]; then
      echo "version=${version}"
    fi
  } > "${RESULT_FILE}"
}

version_from_tag() {
  local tag="$1"
  local ver="${tag#v}"
  echo "${ver%-"${SUFFIX}"}"
}

# Prefer a tag already on HEAD for this collection (republish after a failed Galaxy push).
HEAD_TAG=""
while IFS= read -r tag; do
  if [[ "${tag}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-${SUFFIX}$ ]]; then
    HEAD_TAG="${tag}"
  fi
done < <(git tag --points-at HEAD | sort -V)

if [ -n "${HEAD_TAG}" ]; then
  VERSION="$(version_from_tag "${HEAD_TAG}")"
  echo "HEAD already tagged ${HEAD_TAG}; republishing ${VERSION}"
  write_result publish "${VERSION}"
  exit 0
fi

LATEST_TAG="$(git tag -l "v*-${SUFFIX}" | sort -V | tail -n1 || true)"
if [ -z "${LATEST_TAG}" ]; then
  echo "No baseline tag ending in -${SUFFIX} found."
  echo "Create one first, e.g.:"
  echo "  git tag v1.0.0-${SUFFIX}"
  echo "  git push origin v1.0.0-${SUFFIX}"
  exit 1
fi

if git diff --quiet "${LATEST_TAG}" -- "${COLLECTION_PATH}"; then
  echo "No changes in ${COLLECTION_PATH} since ${LATEST_TAG}; skipping"
  write_result skip
  exit 0
fi

VERSION="$(version_from_tag "${LATEST_TAG}")"
IFS='.' read -r -a VERSION_BITS <<< "${VERSION}"
VNUM1="${VERSION_BITS[0]}"
VNUM2="${VERSION_BITS[1]}"
VNUM3="${VERSION_BITS[2]}"

MAJOR="$(git log --format=%B -n 1 HEAD | grep '#major' || true)"
MINOR="$(git log --format=%B -n 1 HEAD | grep '#minor' || true)"

if [ -n "${MAJOR}" ]; then
  echo "Update major version"
  VNUM1=$((VNUM1 + 1))
  VNUM2=0
  VNUM3=0
elif [ -n "${MINOR}" ]; then
  echo "Update minor version"
  VNUM2=$((VNUM2 + 1))
  VNUM3=0
else
  echo "Update patch version"
  VNUM3=$((VNUM3 + 1))
fi

NEW_VERSION="${VNUM1}.${VNUM2}.${VNUM3}"
NEW_TAG="v${NEW_VERSION}-${SUFFIX}"
echo "Updating ${LATEST_TAG} to ${NEW_TAG}"

git tag "${NEW_TAG}"
git push origin "${NEW_TAG}"

write_result publish "${NEW_VERSION}"
