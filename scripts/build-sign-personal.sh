#!/usr/bin/env bash
# build-sign-personal.sh — Personal-use macOS Developer ID sign + optional notarize
#
# Scope: Bryan personal install on owned Mac(s) only.
#        Not App Store. Not public release. Updater disabled for this path.
#
# Secrets (never in repo):
#   ~/.jarvis/cloud-keys.env  or  ~/.openjarvis/cloud-keys.env
#   Required for sign:  APPLE_SIGNING_IDENTITY or APPLE_DEVELOPER_IDENTITY
#   Optional notarize:  APPLE_TEAM_ID, APPLE_ID + (APPLE_APP_SPECIFIC_PASSWORD or APPLE_API_KEY*)
#
# Usage:
#   ./scripts/build-sign-personal.sh --dry-run     # preflight only
#   ./scripts/build-sign-personal.sh               # build + sign
#   ./scripts/build-sign-personal.sh --install     # build + sign + copy to /Applications
#   ./scripts/build-sign-personal.sh --notarize    # also notarize+staple when creds + Xcode present
#
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

DRY_RUN=false
DO_INSTALL=false
DO_NOTARIZE=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=true ;;
    --install)   DO_INSTALL=true ;;
    --notarize)  DO_NOTARIZE=true ;;
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
IDENTIFIER="com.openjarvis.desktop"

load_apple_env() {
  local f line key val
  for f in "$HOME/.jarvis/cloud-keys.env" "$HOME/.openjarvis/cloud-keys.env"; do
    [ -f "$f" ] || continue
    info "Loading APPLE_* from $(basename "$(dirname "$f")")/$(basename "$f") (values not printed)"
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line%%#*}"
      line="${line#"${line%%[![:space:]]*}"}"
      [ -z "$line" ] || [[ "$line" != APPLE_*=* ]] && continue
      key="${line%%=*}"
      val="${line#*=}"
      val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
      export "$key=$val"
    done < "$f"
  done
}

identity_in_keychain() {
  local id="$1"
  security find-identity -v -p codesigning 2>/dev/null | grep -Fq "$id"
}

count_valid_identities() {
  security find-identity -v -p codesigning 2>/dev/null | grep -c "valid identities found" | head -1 || echo 0
}

has_notarytool() {
  command -v xcrun >/dev/null 2>&1 || return 1
  xcrun --find notarytool >/dev/null 2>&1
}

has_stapler() {
  command -v xcrun >/dev/null 2>&1 || return 1
  xcrun --find stapler >/dev/null 2>&1
}

xcode_is_full() {
  local p
  p="$(xcode-select -p 2>/dev/null || true)"
  [[ "$p" == *Xcode.app* ]]
}

header "OpenJarvis — Personal-use macOS sign pipeline"
echo -e "Scope: ${YELLOW}PERSONAL INSTALL ONLY${NC} · Plan 9 baseline preserved · Updater off"
echo ""

load_apple_env

SIGN_ID="${APPLE_SIGNING_IDENTITY:-${APPLE_DEVELOPER_IDENTITY:-}}"
TEAM_ID="${APPLE_TEAM_ID:-}"

header "Preflight — toolchain"
XCODE_PATH="$(xcode-select -p 2>/dev/null || echo missing)"
info "xcode-select: $XCODE_PATH"
if xcode_is_full; then ok "Full Xcode selected"; else warn "Full Xcode not selected (notarytool/stapler may be unavailable)"; fi
command -v codesign >/dev/null && ok "codesign present" || fail "codesign missing"
VALID_COUNT="$(security find-identity -v -p codesigning 2>/dev/null | awk '/valid identities found/ {print $1}' || echo 0)"
info "Keychain codesigning identities: ${VALID_COUNT} valid"

header "Preflight — signing config (presence only)"
if [ -n "$SIGN_ID" ]; then ok "APPLE_SIGNING_IDENTITY or APPLE_DEVELOPER_IDENTITY: configured"; else fail "No signing identity env var — set APPLE_SIGNING_IDENTITY in ~/.jarvis/cloud-keys.env"; fi
if [ -n "$TEAM_ID" ]; then ok "APPLE_TEAM_ID: configured"; else warn "APPLE_TEAM_ID: absent (may be required for notarization)"; fi

if ! identity_in_keychain "$SIGN_ID"; then
  fail "Signing identity not found in keychain. Import Developer ID Application certificate first."
fi
ok "Signing identity found in keychain (name matched, cert not printed)"

header "Preflight — notarization (optional)"
NOTARY_READY=true
if $DO_NOTARIZE; then
  if ! xcode_is_full; then warn "Full Xcode required for notarization"; NOTARY_READY=false; fi
  if ! has_notarytool; then warn "notarytool unavailable"; NOTARY_READY=false; fi
  if ! has_stapler; then warn "stapler unavailable"; NOTARY_READY=false; fi
  if [ -z "${APPLE_ID:-}" ] && [ -z "${APPLE_API_KEY:-}" ]; then warn "APPLE_ID or APPLE_API_KEY not configured"; NOTARY_READY=false; fi
  if [ -n "${APPLE_ID:-}" ] && [ -z "${APPLE_APP_SPECIFIC_PASSWORD:-}" ] && [ -z "${APPLE_API_KEY:-}" ]; then
    warn "APPLE_APP_SPECIFIC_PASSWORD or APPLE_API_KEY required with APPLE_ID"
    NOTARY_READY=false
  fi
  if $NOTARY_READY; then ok "Notarization preflight passed"; else fail "Notarization requested but prerequisites missing"; fi
else
  info "Notarization skipped (pass --notarize to enable)"
fi

if $DRY_RUN; then
  ok "Dry-run preflight complete"
  exit 0
fi

header "Build — Tauri app (updater artifacts off)"
cd "$FRONTEND_DIR"
TAURI_MACOS_JSON="$(SIGN_ID="$SIGN_ID" python3 - <<'PY'
import json, os
mac = {"signingIdentity": os.environ["SIGN_ID"]}
if os.environ.get("APPLE_PROVIDER_SHORT_NAME"):
    mac["providerShortName"] = os.environ["APPLE_PROVIDER_SHORT_NAME"]
print(json.dumps(mac))
PY
)"
TAURI_CFG="$(TAURI_MACOS_JSON="$TAURI_MACOS_JSON" python3 - <<'PY'
import json, os
mac = json.loads(os.environ["TAURI_MACOS_JSON"])
print(json.dumps({
    "bundle": {"createUpdaterArtifacts": False, "macOS": mac},
    "plugins": {"updater": {"active": False}},
}))
PY
)"
export TAURI_MACOS_JSON
npm run build:tauri
npx tauri build --bundles app --config "$TAURI_CFG"

[ -d "$BUNDLE_APP" ] || fail "Bundle not found at $BUNDLE_APP"

header "Verify — codesign"
codesign --verify --deep --strict --verbose=2 "$BUNDLE_APP" 2>&1 | grep -E 'valid on disk|satisfies|TeamIdentifier' || true
spctl -a -vv "$BUNDLE_APP" 2>&1 | grep -E 'accepted|rejected|Unnotarized|Notarized' || warn "spctl assessment incomplete (notarization may be required for clean Gatekeeper)"

if $DO_NOTARIZE && $NOTARY_READY; then
  header "Notarize + staple"
  ZIP_PATH="$REPO_ROOT/.apple-signing/OpenJarvis-notarize.zip"
  mkdir -p "$REPO_ROOT/.apple-signing"
  ditto -c -k --keepParent "$BUNDLE_APP" "$ZIP_PATH"
  if [ -n "${APPLE_API_KEY:-}" ] && [ -n "${APPLE_API_ISSUER:-}" ]; then
    KEY_PATH="${APPLE_API_KEY_PATH:-$HOME/.apple-signing/AuthKey.p8}"
    xcrun notarytool submit "$ZIP_PATH" --wait --key "$KEY_PATH" --key-id "$APPLE_API_KEY" --issuer "$APPLE_API_ISSUER"
  else
    xcrun notarytool submit "$ZIP_PATH" --wait --apple-id "$APPLE_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD" --team-id "$TEAM_ID"
  fi
  xcrun stapler staple "$BUNDLE_APP"
  ok "Notarization + staple complete"
fi

if $DO_INSTALL; then
  header "Install — /Applications/OpenJarvis.app"
  rm -rf "$SYS_APP"
  ditto "$BUNDLE_APP" "$SYS_APP"
  ok "Installed to $SYS_APP"
fi

header "Done"
ok "Personal signed build ready: $BUNDLE_APP"
echo "Manual verify: open app, confirm no Gatekeeper block, curl http://127.0.0.1:8000/health"
