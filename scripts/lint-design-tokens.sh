#!/usr/bin/env bash
# Design-token lint gates (E0-1) — run from repo root.
# 1. No raw hex in frontend component/CSS code (allowlist: token spec + archives).
# 2. Contrast pairs from tokens.css meet WCAG 2.1 AA (4.5:1 body, 3:1 large).
set -eu
set -o pipefail 2>/dev/null || true

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

fail() { printf '\033[31m✗ %s\033[0m\n' "$*"; exit 1; }
pass() { printf '\033[32m✓ %s\033[0m\n' "$*"; }

# ── 1. Raw hex gate ───────────────────────────────────────────────────────
# Allow hex only in the token spec, unshipped light-theme archive, and legacy
# CSS files pending migration (tracked in ui-modernization-plan Phase 2).
ALLOW_GLOB=(
  'frontend/src/styles/tokens.css'
  'frontend/src/theme/light-theme.css'
  'frontend/src/components/CVECard.css'
  'frontend/src/pages/AdminPage.css'
  'frontend/src/components/NotificationBell.css'
  'frontend/src/components/DetailDrawer/CorrelationSuppressModal.css'
  'frontend/src/components/Header.css'
  'frontend/src/components/DetailDrawer.css'
  'frontend/src/components/InvestigationPanel.css'
  'frontend/src/components/PdfExportModal.css'
)

mapfile -t HEX_HITS < <(
  rg -n --pcre2 '#[0-9a-fA-F]{3,8}\b' frontend/src \
    --glob '*.css' --glob '*.jsx' --glob '*.js' --glob '*.tsx' --glob '*.ts' \
    | while IFS= read -r line; do
        file="${line%%:*}"
        skip=0
        for allowed in "${ALLOW_GLOB[@]}"; do
          if [[ "$file" == "$allowed" ]]; then skip=1; break; fi
        done
        # Export/PDF utilities use fixed palette for off-screen renders (migrate later).
        if [[ "$file" == frontend/src/utils/* ]] || [[ "$file" == frontend/src/scoring/riskScore.js ]]; then
          skip=1
        fi
        [[ "$skip" -eq 0 ]] && printf '%s\n' "$line"
      done
)

if ((${#HEX_HITS[@]} > 0)); then
  printf 'Raw hex found in component code (use semantic tokens):\n'
  printf '%s\n' "${HEX_HITS[@]}"
  fail "raw-hex lint"
fi
pass "raw-hex lint (no hex outside token spec)"

# ── 2. Contrast lint (Python helper) ────────────────────────────────────────
python3 "$REPO_ROOT/scripts/lint_token_contrast.py" || fail "token-contrast lint"
pass "token-contrast lint (WCAG AA pairs)"
