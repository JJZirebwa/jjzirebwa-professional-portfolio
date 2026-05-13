#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RUN_DATE="${1:-$(date +%F)}"
RUN_DIR="$REPO_ROOT/private/regular_audits/runs/$RUN_DATE"

mkdir -p \
  "$REPO_ROOT/private/regular_audits" \
  "$REPO_ROOT/private/regular_audits/config" \
  "$RUN_DIR"

ensure_file() {
  local path="$1"
  local heading="$2"
  if [[ ! -f "$path" ]]; then
    printf '# %s\n' "$heading" > "$path"
  fi
}

ensure_file "$REPO_ROOT/private/regular_audits/AUDIT_INDEX.md" "Audit Index"
ensure_file "$REPO_ROOT/private/regular_audits/IMPLEMENTATION_LOG.md" "Implementation Log"
ensure_file "$RUN_DIR/RUN_SUMMARY.md" "Run Summary"
ensure_file "$RUN_DIR/QOL_RESEARCH.md" "QoL Research"
ensure_file "$RUN_DIR/ORION_CONTENT_AUDIT.md" "ORION Content Audit"
ensure_file "$RUN_DIR/CODE_SITE_AUDIT.md" "Code and Site Audit"
ensure_file "$RUN_DIR/PROPOSALS.md" "Proposals"
ensure_file "$RUN_DIR/sources.md" "Sources"

printf '%s\n' "$RUN_DIR"
