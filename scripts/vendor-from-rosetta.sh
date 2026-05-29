#!/usr/bin/env bash
# AI assistance: written with AI assistance; maintainer reviewed.
# Optional: refresh examples/*-app from a local parse-rosetta-rs checkout.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROSETTA="${ROSETTA:-$(cd "$ROOT/../parse-rosetta-rs" 2>/dev/null && pwd || true)}"

if [[ -z "$ROSETTA" || ! -d "$ROSETTA/examples" ]]; then
  echo "Set ROSETTA to parse-rosetta-rs root (examples/ not found at ../parse-rosetta-rs)" >&2
  exit 1
fi

for app in "$ROSETTA"/examples/*-app; do
  name="$(basename "$app")"
  rm -rf "$ROOT/examples/$name"
  cp -a "$app" "$ROOT/examples/$name"
  echo "Copied $name"
done

echo "Done. Update ATTRIBUTION.md commit hash manually."
