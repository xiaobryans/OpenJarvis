#!/usr/bin/env bash
# build-local.sh — Safe founder-local build wrapper for OpenJarvis
#
# SCOPE: Founder-local packaged app only.
#        Not public distribution. Not Apple-notarized. Not production deploy.
#
# PURPOSE:
#   Wraps `npm run build:tauri:local` with a strict /Applications/OpenJarvis.app
#   integrity guard. Records pre/post content checksums of /Applications and fails
#   with UNAUTHORIZED_APPLICATIONS_MODIFICATION if /Applications content changes
#   without an explicit authorization flag.
#
# ROOT CAUSE DOCUMENTED:
#   When `npm run build:tauri:local` compiles a NEW binary and codesigns the
#   bundle artifact (.../target/release/bundle/macos/OpenJarvis.app), macOS's
#   security infrastructure (syspolicyd/LaunchServices) may rescan the installed
#   copy (/Applications/OpenJarvis.app) that shares the same bundle ID
#   (com.openjarvis.desktop), updating its mtime as a side effect.
#   This script detects CONTENT changes (binary SHA256 + Info.plist SHA256),
#   not merely mtime changes, to distinguish real mutation from OS metadata touch.
#
# Usage:
#   ./scripts/build-local.sh                        # safe build — fails if /Applications content changes
#   ./scripts/build-local.sh --allow-applications-update  # build + allow /Applications content change
#   ./scripts/build-local.sh --install              # build + explicitly install to ~/Applications/
#   ./scripts/build-local.sh --dry-run              # print pre-state and command; do not build
#
# Contract:
#   Exit 0  → build succeeded AND /Applications was not mutated (or was authorized)
#   Exit 1  → UNAUTHORIZED_APPLICATIONS_MODIFICATION or build failure

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

ALLOW_APPS=false
DO_INSTALL=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --allow-applications-update) ALLOW_APPS=true ;;
    --install)                   DO_INSTALL=true; ALLOW_APPS=true ;;
    --dry-run)                   DRY_RUN=true ;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
BUNDLE_APP="$FRONTEND_DIR/src-tauri/target/release/bundle/macos/OpenJarvis.app"
SYS_APP="/Applications/OpenJarvis.app"
SYS_BINARY="$SYS_APP/Contents/MacOS/openjarvis-desktop"
SYS_PLIST="$SYS_APP/Contents/Info.plist"

# ── Helpers ──────────────────────────────────────────────────────────────

app_state() {
  local label="$1"
  local app="$2"
  local binary="$app/Contents/MacOS/openjarvis-desktop"
  local plist="$app/Contents/Info.plist"

  echo "--- /Applications state: $label ---"
  if [ ! -d "$app" ]; then
    echo "  exists=false"
    echo "exists=false"
    return
  fi
  local mtime bin_sha plist_sha xattrs
  mtime=$(stat -f "%m" "$app" 2>/dev/null || echo "0")
  bin_sha=$(shasum -a256 "$binary" 2>/dev/null | awk '{print $1}' || echo "absent")
  plist_sha=$(shasum -a256 "$plist" 2>/dev/null | awk '{print $1}' || echo "absent")
  xattrs=$(xattr "$app" 2>/dev/null | sort | tr '\n' '|' || echo "")
  echo "  exists=true"
  echo "  mtime=$mtime"
  echo "  version=$(plutil -extract CFBundleShortVersionString raw "$plist" 2>/dev/null || echo 'unreadable')"
  echo "  binary_sha256=$bin_sha"
  echo "  plist_sha256=$plist_sha"
  echo "  xattrs=$xattrs"
  # Export for comparison
  echo "exists=true"
  echo "bin_sha=$bin_sha"
  echo "plist_sha=$plist_sha"
  echo "xattrs=$xattrs"
}

# ── Header ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}OpenJarvis — Safe Founder-Local Build Wrapper${NC}"
echo -e "Scope: ${YELLOW}FOUNDER-LOCAL ONLY${NC} · Not public · Not notarized · Not production"
if $ALLOW_APPS; then
  echo -e "/Applications: ${YELLOW}AUTHORIZED UPDATE${NC} (--allow-applications-update or --install passed)"
else
  echo -e "/Applications: ${BOLD}READ-ONLY GUARD ACTIVE${NC} (fail with UNAUTHORIZED_APPLICATIONS_MODIFICATION if mutated)"
fi
echo ""

# ── Step 1: Record /Applications pre-state ──────────────────────────────
header "Step 1 — /Applications pre-state (content checksums)"

PRE_BIN_SHA="absent"
PRE_PLIST_SHA="absent"
PRE_XATTRS=""
SYS_APP_EXISTS=false

if [ -d "$SYS_APP" ]; then
  SYS_APP_EXISTS=true
  PRE_BIN_SHA=$(shasum -a256 "$SYS_BINARY" 2>/dev/null | awk '{print $1}' || echo "absent")
  PRE_PLIST_SHA=$(shasum -a256 "$SYS_PLIST" 2>/dev/null | awk '{print $1}' || echo "absent")
  PRE_XATTRS=$(xattr "$SYS_APP" 2>/dev/null | sort | tr '\n' '|' || echo "")
  PRE_MTIME=$(stat -f "%m" "$SYS_APP" 2>/dev/null || echo "0")
  PRE_VERSION=$(plutil -extract CFBundleShortVersionString raw "$SYS_PLIST" 2>/dev/null || echo "unreadable")
  info "Exists:           yes"
  info "Version:          $PRE_VERSION"
  info "mtime:            $PRE_MTIME"
  info "binary_sha256:    $PRE_BIN_SHA"
  info "plist_sha256:     $PRE_PLIST_SHA"
  info "xattrs:           $PRE_XATTRS"
else
  info "Exists:           no — /Applications/OpenJarvis.app absent"
  PRE_MTIME="0"
  PRE_VERSION="absent"
fi

# ── Step 2: Version alignment precheck ──────────────────────────────────
header "Step 2 — Version alignment precheck"

PYPROJECT_VER=$(grep -m1 '^version' "$REPO_ROOT/pyproject.toml" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
PKGJSON_VER=$(node -e "const p=require('$FRONTEND_DIR/package.json'); process.stdout.write(p.version);" 2>/dev/null || echo "unknown")
TAURI_VER=$(python3 -c "import json; d=json.load(open('$FRONTEND_DIR/src-tauri/tauri.conf.json')); print(d['version'], end='')" 2>/dev/null || echo "unknown")
CARGO_VER=$(grep -m1 '^version' "$FRONTEND_DIR/src-tauri/Cargo.toml" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

if [ "$PYPROJECT_VER" != "$PKGJSON_VER" ] || [ "$PKGJSON_VER" != "$TAURI_VER" ] || [ "$TAURI_VER" != "$CARGO_VER" ]; then
  fail "VERSION_MISMATCH — source files do not agree: pyproject=$PYPROJECT_VER pkg=$PKGJSON_VER tauri=$TAURI_VER cargo=$CARGO_VER"
fi
EXPECTED_VERSION="$PYPROJECT_VER"
ok "All four version files agree: v$EXPECTED_VERSION"

# ── Step 3: Dry-run exit ─────────────────────────────────────────────────
if $DRY_RUN; then
  echo ""
  warn "DRY-RUN mode — build command NOT executed."
  echo "  Would run: cd frontend && npm run build:tauri:local"
  echo "  Expected artifact: $BUNDLE_APP"
  exit 0
fi

# ── Step 4: Run founder-local build ─────────────────────────────────────
header "Step 4 — Rust extension (openjarvis_rust) for local desktop memory"

if command -v uv >/dev/null 2>&1 && command -v rustc >/dev/null 2>&1; then
  info "Building openjarvis_rust into project venv (maturin develop)..."
  if (cd "$REPO_ROOT" && uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml); then
    ok "openjarvis_rust installed into .venv"
  else
    warn "maturin develop failed — desktop memory will run degraded (SQLite fallback)"
  fi
else
  warn "uv or rustc missing — skipping openjarvis_rust build (desktop memory degraded)"
fi

header "Step 5 — Run founder-local build (npm run build:tauri:local)"

echo "  Command: cd frontend && npm run build:tauri:local"
echo "  (--bundles app, createUpdaterArtifacts=false, updater.active=false)"
echo ""

cd "$FRONTEND_DIR"
BUILD_START=$(date +%s)
npm run build:tauri:local
BUILD_EXIT=$?
BUILD_END=$(date +%s)
BUILD_ELAPSED=$(( BUILD_END - BUILD_START ))

echo ""
ok "Build completed in ${BUILD_ELAPSED}s with exit code $BUILD_EXIT"

# ── Step 6: Record /Applications post-state ─────────────────────────────
header "Step 6 — /Applications post-state (content checksums)"

POST_BIN_SHA="absent"
POST_PLIST_SHA="absent"
POST_XATTRS=""
POST_MTIME="0"
POST_VERSION="absent"

if [ -d "$SYS_APP" ]; then
  POST_BIN_SHA=$(shasum -a256 "$SYS_BINARY" 2>/dev/null | awk '{print $1}' || echo "absent")
  POST_PLIST_SHA=$(shasum -a256 "$SYS_PLIST" 2>/dev/null | awk '{print $1}' || echo "absent")
  POST_XATTRS=$(xattr "$SYS_APP" 2>/dev/null | sort | tr '\n' '|' || echo "")
  POST_MTIME=$(stat -f "%m" "$SYS_APP" 2>/dev/null || echo "0")
  POST_VERSION=$(plutil -extract CFBundleShortVersionString raw "$SYS_PLIST" 2>/dev/null || echo "unreadable")
  info "Exists:           yes"
  info "Version:          $POST_VERSION"
  info "mtime:            $POST_MTIME (pre: $PRE_MTIME)"
  info "binary_sha256:    $POST_BIN_SHA"
  info "plist_sha256:     $POST_PLIST_SHA"
  info "xattrs:           $POST_XATTRS"
else
  info "Exists:           no — /Applications/OpenJarvis.app absent"
fi

# ── Step 6: /Applications mutation check ────────────────────────────────
header "Step 7 — /Applications mutation detection"

ANY_CHANGE=false
CONTENT_CHANGED=false
MTIME_CHANGED=false
CHANGE_DETAILS=""

if [ "$PRE_BIN_SHA" != "$POST_BIN_SHA" ]; then
  ANY_CHANGE=true
  CONTENT_CHANGED=true
  CHANGE_DETAILS="$CHANGE_DETAILS\n  binary_sha256: $PRE_BIN_SHA → $POST_BIN_SHA  [CONTENT CHANGE]"
fi
if [ "$PRE_PLIST_SHA" != "$POST_PLIST_SHA" ]; then
  ANY_CHANGE=true
  CONTENT_CHANGED=true
  CHANGE_DETAILS="$CHANGE_DETAILS\n  plist_sha256:  $PRE_PLIST_SHA → $POST_PLIST_SHA  [CONTENT CHANGE]"
fi
if [ "$PRE_VERSION" != "$POST_VERSION" ]; then
  ANY_CHANGE=true
  CONTENT_CHANGED=true
  CHANGE_DETAILS="$CHANGE_DETAILS\n  version: $PRE_VERSION → $POST_VERSION  [CONTENT CHANGE]"
fi
if [ "$PRE_MTIME" != "$POST_MTIME" ]; then
  ANY_CHANGE=true
  MTIME_CHANGED=true
  CHANGE_DETAILS="$CHANGE_DETAILS\n  mtime: $PRE_MTIME → $POST_MTIME  [METADATA TOUCH]"
fi

if $ANY_CHANGE; then
  if $ALLOW_APPS; then
    warn "/Applications changed — authorized via --allow-applications-update"
    echo -e "$CHANGE_DETAILS"
    ok "Authorized: /Applications change accepted with explicit flag"
  else
    echo ""
    if $CONTENT_CHANGED; then
      echo -e "${RED}[FAIL]${NC}   UNAUTHORIZED_APPLICATIONS_MODIFICATION"
      echo ""
      echo -e "  /Applications/OpenJarvis.app content changed during the founder-local build."
    else
      echo -e "${RED}[FAIL]${NC}   UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH"
      echo ""
      echo -e "  /Applications/OpenJarvis.app mtime changed during the founder-local build."
      echo -e "  Content (binary, plist, version) is unchanged, but a filesystem metadata touch"
      echo -e "  occurred. This is a macOS security infrastructure side-effect (syspolicyd/"
      echo -e "  LaunchServices rescan) of codesigning a new binary with the same bundle ID."
    fi
    echo ""
    echo -e "  Changes detected:$CHANGE_DETAILS"
    echo ""
    echo -e "  /Applications must not be touched without explicit Bryan authorization."
    echo -e "  Any change — content or mtime — to /Applications requires the allow flag."
    echo ""
    echo -e "  To authorize, re-run with:"
    echo -e "    ${BOLD}./scripts/build-local.sh --allow-applications-update${NC}"
    echo ""
    echo -e "  To install to ~/Applications/ (does not modify /Applications):"
    echo -e "    ${BOLD}./scripts/build-local.sh --install${NC}"
    echo ""
    exit 1
  fi
else
  ok "/Applications UNCHANGED — binary SHA, plist SHA, version, and mtime all match pre-state"
fi

# ── Step 7: Verify artifact ──────────────────────────────────────────────
header "Step 8 — Artifact verification"

cd "$REPO_ROOT"
if [ -d "$BUNDLE_APP" ]; then
  BUNDLE_VER=$(plutil -extract CFBundleShortVersionString raw \
    "$BUNDLE_APP/Contents/Info.plist" 2>/dev/null || echo "unknown")
  if [ "$BUNDLE_VER" = "$EXPECTED_VERSION" ]; then
    ok "Artifact: $BUNDLE_APP"
    ok "Version:  v$BUNDLE_VER ✓ matches expected (v$EXPECTED_VERSION)"
  else
    fail "STALE_OR_MISSING_PACKAGE_ARTIFACT — artifact v$BUNDLE_VER ≠ expected v$EXPECTED_VERSION"
  fi
else
  fail "STALE_OR_MISSING_PACKAGE_ARTIFACT — artifact not found: $BUNDLE_APP"
fi

# ── Step 8: Optional install to ~/Applications/ ─────────────────────────
if $DO_INSTALL; then
  header "Step 9 — Install to ~/Applications/ (explicit authorization)"
  DEST="$HOME/Applications"
  mkdir -p "$DEST"
  rm -rf "$DEST/OpenJarvis.app"
  cp -r "$BUNDLE_APP" "$DEST/"
  ok "Installed to $DEST/OpenJarvis.app (v$BUNDLE_VER)"
  info "Remove quarantine if needed: xattr -dr com.apple.quarantine '$DEST/OpenJarvis.app'"
else
  header "Step 9 — Install (skipped — no --install flag)"
  info "To install to ~/Applications/: ./scripts/build-local.sh --install"
  info "To install to /Applications/: copy manually with Bryan authorization only"
fi

# ── Summary ──────────────────────────────────────────────────────────────
header "Build complete"

echo ""
echo -e "  Scope:                ${YELLOW}FOUNDER-LOCAL${NC}"
echo -e "  Build exit code:      ${GREEN}$BUILD_EXIT${NC}"
echo -e "  Artifact version:     ${GREEN}v$BUNDLE_VER${NC}"
  echo -e "  /Applications changed: $( $ANY_CHANGE && echo "${YELLOW}YES (authorized — see changes above)${NC}" || echo "${GREEN}NO (binary, plist, version, mtime all unchanged)${NC}" )"
echo -e "  Signing (founder):    ${YELLOW}AD-HOC${NC} — CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN"
echo -e "  Signing (public):     ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Notarization:         ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Auto-update:          ${RED}REQUIRED_FOR_PUBLIC_RELEASE${NC}"
echo -e "  Voice:                ${RED}REQUIRED_FOR_NO_GAP_JARVIS${NC} (Sprint 3)"
echo -e "  Company org:          ${RED}REQUIRED_FOR_NO_GAP_JARVIS${NC}"
echo -e "  Full no-gap:          ${RED}HOLD${NC}"
echo ""
echo "  Next: run ./scripts/release-local.sh to validate the artifact."
echo ""
