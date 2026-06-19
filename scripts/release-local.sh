#!/usr/bin/env bash
# release-local.sh — OpenJarvis founder-local packaging validation
#
# SCOPE: Founder-local packaged app only.
#        Not public distribution. Not Apple-notarized. Not production deploy.
#
# NO-GAP STATUS: Full no-gap Jarvis is HOLD until all required items pass:
#   ▶ Packaging / release sprint (this sprint — Sprint 2)
#   · Voice safety sprint (Sprint 3) — REQUIRED_FOR_NO_GAP_JARVIS
#   · 30-task no-gap certification suite (Sprint 4) — REQUIRED_FOR_NO_GAP_JARVIS
#   · Company org / manager-worker roster — REQUIRED_FOR_NO_GAP_JARVIS
#   (Sprint 1 UI polish: accepted and committed)
#
# VOICE: Voice safety sprint is a separate required sprint.
#        This script does NOT verify or certify voice readiness.
#
# BUILD COMMANDS — SEPARATED BY SCOPE:
#   Founder-local (exits 0, no updater signing required):
#     cd frontend && npm run build:tauri:local
#   Public/updater build (requires TAURI_SIGNING_PRIVATE_KEY):
#     cd frontend && npm run build:tauri:release
#   This script validates an EXISTING artifact. It does not run the tauri build.
#
# ARTIFACT VERSION GATE:
#   This script FAILS if the packaged artifact version does not match the
#   expected version derived from source-of-truth version files.
#   A stale artifact produces: STALE_OR_MISSING_PACKAGE_ARTIFACT
#
# /APPLICATIONS MODIFICATION POLICY:
#   /Applications/OpenJarvis.app is treated as READ-ONLY EVIDENCE by default.
#   Running `npm run build:tauri:local` may modify /Applications/OpenJarvis.app
#   as a side-effect of macOS codesigning.
#   This script records the pre-run state and fails with:
#     UNAUTHORIZED_APPLICATIONS_MODIFICATION
#   if /Applications changes during script execution without --allow-applications-update.
#   To explicitly authorize /Applications installation/update, use --install.
#
# Usage:
#   ./scripts/release-local.sh           — precheck + build check + artifact verify
#   ./scripts/release-local.sh --install — explicitly authorize ~/Applications/ install
#   ./scripts/release-local.sh --health  — also run health check against running server
#
# Requires:
#   Node 18+, npm, uv or pip (.venv), jarvis serve must be running for --health

set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[info]${NC}   $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}     $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}   $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}   $*"; exit 1; }
header(){ echo -e "\n${BOLD}$*${NC}"; }

DO_INSTALL=false
DO_HEALTH=false
for arg in "$@"; do
  case "$arg" in
    --install) DO_INSTALL=true ;;
    --health)  DO_HEALTH=true ;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
BUNDLE_DIR="$FRONTEND_DIR/src-tauri/target/release/bundle"
APP_IN_BUNDLE="$BUNDLE_DIR/macos/OpenJarvis.app"
APP_IN_APPLICATIONS="/Applications/OpenJarvis.app"
APP_IN_HOME_APPS="$HOME/Applications/OpenJarvis.app"

# ── Header ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}OpenJarvis — Founder-Local Release Validation${NC}"
echo -e "Scope: ${YELLOW}FOUNDER-LOCAL ONLY${NC} · Not public · Not notarized · Not production"
echo -e "No-gap: ${RED}HOLD${NC} · Remaining: packaging sprint ▶, voice safety, 30-task suite, company org roster"
echo ""

# ── STEP 0: Record /Applications pre-state ───────────────────────────────
# /Applications/OpenJarvis.app is treated as read-only evidence.
# We record its state now; if it changes during this script (without --install),
# we fail with UNAUTHORIZED_APPLICATIONS_MODIFICATION.
header "Step 0 — Pre-state snapshot (/Applications guard)"

APPS_PRE_VERSION="absent"
APPS_PRE_MTIME="0"

if [ -d "$APP_IN_APPLICATIONS" ]; then
  APPS_PRE_VERSION=$(plutil -extract CFBundleShortVersionString raw \
    "$APP_IN_APPLICATIONS/Contents/Info.plist" 2>/dev/null || echo "unreadable")
  APPS_PRE_MTIME=$(stat -f "%m" "$APP_IN_APPLICATIONS" 2>/dev/null || echo "0")
  info "/Applications/OpenJarvis.app pre-state: v$APPS_PRE_VERSION  mtime=$APPS_PRE_MTIME"
else
  info "/Applications/OpenJarvis.app pre-state: absent"
fi

# ── STEP 1: Git precheck ─────────────────────────────────────────────────
header "Step 1 — Git precheck"

cd "$REPO_ROOT"
GIT_STATUS=$(git status --short)
if [ -n "$GIT_STATUS" ]; then
  warn "Working tree is not clean:"
  echo "$GIT_STATUS"
  warn "Uncommitted changes present — proceeding, but commit before tagging a release."
else
  ok "git status: clean"
fi

git diff --check && ok "git diff --check: clean" || warn "git diff --check: whitespace issues found"

HEAD=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
ok "HEAD: $HEAD  branch: $BRANCH"

# ── STEP 2: Version alignment (source-of-truth gate) ────────────────────
header "Step 2 — Version alignment (source-of-truth gate)"

PYPROJECT_VER=$(grep -m1 '^version' "$REPO_ROOT/pyproject.toml" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
PKGJSON_VER=$(node -e "const p=require('$FRONTEND_DIR/package.json'); process.stdout.write(p.version);" 2>/dev/null || echo "unknown")
TAURI_VER=$(python3 -c "import json; d=json.load(open('$FRONTEND_DIR/src-tauri/tauri.conf.json')); print(d['version'], end='')" 2>/dev/null || echo "unknown")
CARGO_VER=$(grep -m1 '^version' "$FRONTEND_DIR/src-tauri/Cargo.toml" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

info "pyproject.toml:            $PYPROJECT_VER"
info "frontend/package.json:     $PKGJSON_VER"
info "src-tauri/tauri.conf.json: $TAURI_VER"
info "src-tauri/Cargo.toml:      $CARGO_VER"

if [ "$PYPROJECT_VER" != "$PKGJSON_VER" ] || [ "$PKGJSON_VER" != "$TAURI_VER" ] || [ "$TAURI_VER" != "$CARGO_VER" ]; then
  fail "VERSION_MISMATCH — version files do not agree. Run: ./scripts/bump-desktop-version.sh <version>"
fi

EXPECTED_VERSION="$PYPROJECT_VER"
ok "All four version files agree: $EXPECTED_VERSION"

# ── STEP 3: Confirm build commands ───────────────────────────────────────
header "Step 3 — Build command reference (this script does not run the build)"

echo ""
  echo -e "  ${BOLD}Founder-local build (exits 0, no updater signing, no DMG):${NC}"
  echo "    cd frontend && npm run build:tauri:local"
  echo "    → --bundles app: skips DMG (avoids stale temp image conflicts)"
  echo "    → disables updater artifact signing (no TAURI_SIGNING_PRIVATE_KEY needed)"
  echo "    → produces .app at: $BUNDLE_DIR/macos/"
echo ""
echo -e "  ${YELLOW}Public/updater build (requires TAURI_SIGNING_PRIVATE_KEY):${NC}"
echo "    cd frontend && npm run build:tauri:release"
echo "    Status: REQUIRED_FOR_PUBLIC_RELEASE"
echo "    Note: 'npm run tauri build' may also modify /Applications/OpenJarvis.app"
echo "          as a side-effect of macOS codesigning."
echo "          Run only with explicit Bryan authorization."
echo ""
info "This script validates an existing artifact. Run the build separately first."

# ── STEP 4: Frontend web build ───────────────────────────────────────────
header "Step 4 — Frontend web build (tsc + vite — does not affect /Applications)"

cd "$FRONTEND_DIR"
info "Running: npm run build"
npm run build 2>&1 | tail -5
ok "Frontend build: exit 0"

DIST_DIR="$FRONTEND_DIR/dist"
if [ -d "$DIST_DIR" ] && [ "$(ls -A "$DIST_DIR")" ]; then
  ok "frontend/dist/ exists and is non-empty"
else
  fail "frontend/dist/ missing or empty after build"
fi

# ── STEP 5: Packaged artifact version gate ───────────────────────────────
header "Step 5 — Packaged artifact version gate (expected: v$EXPECTED_VERSION)"

cd "$REPO_ROOT"

if [ -d "$APP_IN_BUNDLE" ]; then
  BUNDLE_VER=$(plutil -extract CFBundleShortVersionString raw \
    "$APP_IN_BUNDLE/Contents/Info.plist" 2>/dev/null || echo "unknown")
  if [ "$BUNDLE_VER" = "$EXPECTED_VERSION" ]; then
    ok "Bundle artifact: $APP_IN_BUNDLE"
    ok "Bundle version:  v$BUNDLE_VER ✓ matches expected"
  else
    echo -e "${RED}[FAIL]${NC}   STALE_OR_MISSING_PACKAGE_ARTIFACT"
    echo -e "         Bundle artifact version: ${RED}v$BUNDLE_VER${NC} — expected: ${GREEN}v$EXPECTED_VERSION${NC}"
    echo -e "         Run founder-local build: cd frontend && npm run build:tauri:local"
    exit 1
  fi
else
  echo -e "${RED}[FAIL]${NC}   STALE_OR_MISSING_PACKAGE_ARTIFACT"
  echo -e "         Bundle artifact not found: $APP_IN_BUNDLE"
  echo -e "         Run founder-local build: cd frontend && npm run build:tauri:local"
  exit 1
fi

# ── STEP 6: /Applications evidence (read-only) ──────────────────────────
header "Step 6 — /Applications/OpenJarvis.app (read-only evidence)"

if [ -d "$APP_IN_APPLICATIONS" ]; then
  APPS_CURRENT_VER=$(plutil -extract CFBundleShortVersionString raw \
    "$APP_IN_APPLICATIONS/Contents/Info.plist" 2>/dev/null || echo "unknown")
  APPS_CURRENT_MTIME=$(stat -f "%m" "$APP_IN_APPLICATIONS" 2>/dev/null || echo "0")

  if [ "$APPS_CURRENT_MTIME" != "$APPS_PRE_MTIME" ] && ! $DO_INSTALL; then
    echo -e "${RED}[FAIL]${NC}   UNAUTHORIZED_APPLICATIONS_MODIFICATION"
    echo -e "         /Applications/OpenJarvis.app was modified during this script run."
    echo -e "         Pre-state mtime: $APPS_PRE_MTIME  Current: $APPS_CURRENT_MTIME"
    echo -e "         If you intended to update /Applications, re-run with --install flag."
    echo -e "         /Applications must not be modified without explicit authorization."
    exit 1
  fi

  if [ "$APPS_CURRENT_VER" = "$EXPECTED_VERSION" ]; then
    ok "Installed: /Applications/OpenJarvis.app v$APPS_CURRENT_VER ✓ current"
  else
    warn "installed_stale: /Applications/OpenJarvis.app is v$APPS_CURRENT_VER — expected v$EXPECTED_VERSION"
    warn "Update requires explicit authorization: run with --install"
    warn "(Or copy directly: cp -r $APP_IN_BUNDLE ~/Applications/)"
  fi
else
  warn "No /Applications/OpenJarvis.app found."
  warn "Run: cp -r $APP_IN_BUNDLE ~/Applications/  (or use --install)"
fi

info "Signing identity (tauri.conf.json): $(python3 -c \
  "import json; d=json.load(open('$FRONTEND_DIR/src-tauri/tauri.conf.json')); \
  print(d['bundle']['macOS']['signingIdentity'], end='')" 2>/dev/null || echo "unknown")"
info "Ad-hoc signing is correct for founder-local use."
info "Gatekeeper: right-click → Open on first launch, or:"
info "  xattr -dr com.apple.quarantine /Applications/OpenJarvis.app"

# ── STEP 7: Optional install to ~/Applications/ ──────────────────────────
if $DO_INSTALL; then
  header "Step 7 — Install to ~/Applications/ (explicit authorization granted)"
  if [ -d "$APP_IN_BUNDLE" ] && [ "$BUNDLE_VER" = "$EXPECTED_VERSION" ]; then
    DEST="$HOME/Applications"
    mkdir -p "$DEST"
    rm -rf "$DEST/OpenJarvis.app"
    cp -r "$APP_IN_BUNDLE" "$DEST/"
    ok "Copied to $DEST/OpenJarvis.app (v$BUNDLE_VER)"
    info "Remove quarantine if needed: xattr -dr com.apple.quarantine '$DEST/OpenJarvis.app'"
  else
    warn "Bundle artifact at expected version not found — cannot install."
    warn "Run founder-local build first: cd frontend && npm run build:tauri:local"
  fi
else
  header "Step 7 — Install (skipped — no --install flag)"
  info "To install to ~/Applications/: run with --install (explicit authorization)"
  info "For /Applications/: copy from bundle (with Bryan authorization):"
  info "  cp -r $APP_IN_BUNDLE /Applications/  # only with explicit permission"
fi

# ── STEP 8: Backend / runtime requirement ───────────────────────────────
header "Step 8 — Backend runtime (required)"
echo ""
echo -e "  ${YELLOW}The packaged app requires the backend server to be running separately.${NC}"
echo "  The app connects to http://localhost:8000 by default."
echo ""
echo "  Start backend:  cd $REPO_ROOT && uv run jarvis serve"
echo "  Open app:       open /Applications/OpenJarvis.app"
echo "  Rollback:       See docs/ROLLBACK.md"
echo ""

# ── STEP 9: Health check ────────────────────────────────────────────────
header "Step 9 — Health / readiness check"

if $DO_HEALTH; then
  SERVER="http://localhost:8000"
  info "Checking $SERVER/v1/readiness ..."
  READINESS=$(curl -sf "$SERVER/v1/readiness" 2>/dev/null || echo "")
  if [ -z "$READINESS" ]; then
    fail "Server unreachable at $SERVER — start backend first: uv run jarvis serve"
  fi
  VERDICT=$(echo "$READINESS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('verdict','unknown'))" 2>/dev/null || echo "unknown")
  if [ "$VERDICT" = "ready" ] || [ "$VERDICT" = "warn" ]; then
    ok "Readiness: $VERDICT"
  else
    warn "Readiness verdict: $VERDICT — check server logs"
  fi
  VERSION=$(curl -sf "$SERVER/v1/version" 2>/dev/null || echo "")
  if [ -n "$VERSION" ]; then
    GIT_COM=$(echo "$VERSION" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('git_commit','unknown'))" 2>/dev/null || echo "unknown")
    APP_VER=$(echo "$VERSION" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('version','unknown'))" 2>/dev/null || echo "unknown")
    ok "Server version: $APP_VER  commit: $GIT_COM"
  fi
else
  info "Health check skipped — run with --health to verify against running server:"
  info "  curl -s http://localhost:8000/v1/readiness | python3 -m json.tool"
fi

# ── STEP 10: Known limitations (explicit status labels) ──────────────────
header "Step 10 — Known limitations (explicit — not hidden)"

echo ""
echo "  SIGNING (founder-local): Ad-hoc (signingIdentity='-'). Gatekeeper prompts."
echo "    Status: CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN (ad-hoc is correct for founder-local)"
echo "  SIGNING (public release): Apple Developer ID required."
echo "    Status: REQUIRED_FOR_PUBLIC_RELEASE"
echo "  NOTARIZATION:    NOT available. No Apple Developer Program account."
echo "    Status: REQUIRED_FOR_PUBLIC_RELEASE"
echo "  AUTO-UPDATE:     Endpoint configured; TAURI_SIGNING_PRIVATE_KEY not set."
echo "    Status: REQUIRED_FOR_PUBLIC_RELEASE"
echo "  VOICE:           Separate safety sprint required (Sprint 3)."
echo "    Status: REQUIRED_FOR_NO_GAP_JARVIS"
echo "  COMPANY ORG:     Manager-worker roster not yet built."
echo "    Status: REQUIRED_FOR_NO_GAP_JARVIS"
echo "  FULL NO-GAP:     HOLD — voice safety, 30-task suite, company org pending."
echo "  PUBLIC DISTRIB.: NOT ready. Founder-local use only."
echo "    Status: REQUIRED_FOR_PUBLIC_RELEASE"
echo ""

# ── STEP 11: Secret scan ─────────────────────────────────────────────────
header "Step 11 — Quick secret scan (frontend/dist)"

SECRET_HITS=$( { grep -rE \
  "sk-[a-zA-Z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}" \
  "$FRONTEND_DIR/dist/" 2>/dev/null; true; } | wc -l | tr -d ' ')

if [ "$SECRET_HITS" = "0" ]; then
  ok "Secret scan: CLEAN (0 hits in frontend/dist/)"
else
  fail "Secret scan: FOUND $SECRET_HITS potential secrets in frontend/dist/ — review before release"
fi

# ── STEP 12: /Applications post-state check ──────────────────────────────
header "Step 12 — /Applications post-state check"

if [ -d "$APP_IN_APPLICATIONS" ]; then
  APPS_POST_MTIME=$(stat -f "%m" "$APP_IN_APPLICATIONS" 2>/dev/null || echo "0")
  APPS_POST_VER=$(plutil -extract CFBundleShortVersionString raw \
    "$APP_IN_APPLICATIONS/Contents/Info.plist" 2>/dev/null || echo "unknown")
  if [ "$APPS_POST_MTIME" != "$APPS_PRE_MTIME" ] && ! $DO_INSTALL; then
    echo -e "${RED}[FAIL]${NC}   UNAUTHORIZED_APPLICATIONS_MODIFICATION"
    echo -e "         /Applications/OpenJarvis.app changed during this script run."
    echo -e "         Pre mtime=$APPS_PRE_MTIME  Post mtime=$APPS_POST_MTIME"
    echo -e "         Version: $APPS_PRE_VERSION → $APPS_POST_VER"
    echo -e "         To authorize update, re-run with --install."
    exit 1
  fi
  ok "/Applications/OpenJarvis.app post-state: v$APPS_POST_VER  mtime=$APPS_POST_MTIME (unchanged)"
else
  ok "/Applications/OpenJarvis.app post-state: absent (unchanged)"
fi

# ── Final summary ────────────────────────────────────────────────────────
header "Validation complete"

echo ""
echo -e "  Scope:               ${YELLOW}FOUNDER-LOCAL${NC}"
echo -e "  Build (web):         ${GREEN}PASS${NC}  (frontend/dist/ produced)"
echo -e "  Artifact version:    ${GREEN}v$EXPECTED_VERSION${NC}  (matches source)"
echo -e "  /Applications guard: ${GREEN}PASS${NC}  (no unauthorized modification)"
echo -e "  Signing (founder):   ${YELLOW}AD-HOC${NC}  — CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN"
echo -e "  Signing (public):    ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Notarization:        ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Auto-update:         ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Voice:               ${RED}REQUIRED_FOR_NO_GAP_JARVIS${NC}  (Sprint 3)"
echo -e "  Company org:         ${RED}REQUIRED_FOR_NO_GAP_JARVIS${NC}"
echo -e "  Full no-gap:         ${RED}HOLD${NC}"
echo ""
echo "  Next steps for Bryan:"
echo "    1. Review this output and authorize commit."
echo "    2. To rebuild: cd frontend && npm run build:tauri:local"
echo "    3. To launch: uv run jarvis serve && open /Applications/OpenJarvis.app"
echo "    4. Re-run with --health to verify runtime."
echo ""
