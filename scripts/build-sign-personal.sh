#!/usr/bin/env bash
# build-sign-personal.sh — Personal-use macOS Developer ID sign + optional notarize
#
# Scope: Bryan personal install on owned Mac(s) only.
#        Not App Store. Not public release. Updater disabled for this path.
#
# Secrets (never in repo):
#   ~/.jarvis/cloud-keys.env  or  ~/.openjarvis/cloud-keys.env
#   Required for sign:  APPLE_SIGNING_IDENTITY or APPLE_DEVELOPER_IDENTITY
#   Notarize Option A:  APPLE_NOTARY_KEYCHAIN_PROFILE or APPLE_KEYCHAIN_PROFILE (preferred)
#   Notarize Option B:  APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD or APPLE_PASSWORD
#   Notarize Option C:  APPLE_API_KEY, APPLE_API_ISSUER, APPLE_API_KEY_PATH (AuthKey .p8 file)
#
# Usage:
#   ./scripts/build-sign-personal.sh --dry-run              # preflight only
#   ./scripts/build-sign-personal.sh --install              # build + sign + install
#   ./scripts/build-sign-personal.sh --install --notarize   # build + sign + notarize + staple + install
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

has_notarytool() {
  command -v xcrun >/dev/null 2>&1 && xcrun --find notarytool >/dev/null 2>&1
}

has_stapler() {
  command -v xcrun >/dev/null 2>&1 && xcrun --find stapler >/dev/null 2>&1
}

notary_tools_ready() {
  has_notarytool && has_stapler
}

xcode_is_full() {
  local p
  p="$(xcode-select -p 2>/dev/null || true)"
  [[ "$p" == *Xcode.app* ]]
}

notary_password_present() {
  [ -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ] || [ -n "${APPLE_PASSWORD:-}" ]
}

notary_api_key_ready() {
  [ -n "${APPLE_API_KEY:-}" ] && [ -n "${APPLE_API_ISSUER:-}" ] || return 1
  local key_path="${APPLE_API_KEY_PATH:-$HOME/.apple-signing/AuthKey.p8}"
  [ -f "$key_path" ]
}

notary_keychain_profile() {
  echo "${APPLE_NOTARY_KEYCHAIN_PROFILE:-${APPLE_KEYCHAIN_PROFILE:-}}"
}

notary_keychain_profile_ready() {
  [ -n "$(notary_keychain_profile)" ]
}

notary_apple_id_ready() {
  [ -n "${APPLE_ID:-}" ] && notary_password_present && [ -n "${APPLE_TEAM_ID:-}" ]
}

notary_credentials_ready() {
  notary_keychain_profile_ready || notary_api_key_ready || notary_apple_id_ready
}

report_notary_credential_status() {
  local profile
  profile="$(notary_keychain_profile)"
  if notary_keychain_profile_ready; then
    ok "Notarization Keychain profile: ${profile}"
    return 0
  fi
  info "Notarization Keychain profile: absent (APPLE_NOTARY_KEYCHAIN_PROFILE / APPLE_KEYCHAIN_PROFILE)"
  if notary_api_key_ready; then
    ok "Notarization Option C: APPLE_API_KEY + APPLE_API_ISSUER + key file present"
    return 0
  fi
  if [ -n "${APPLE_API_KEY:-}" ] || [ -n "${APPLE_API_ISSUER:-}" ]; then
    warn "Notarization Option C: partial — need APPLE_API_KEY, APPLE_API_ISSUER, and readable APPLE_API_KEY_PATH"
  else
    info "Notarization Option C: APPLE_API_KEY not configured"
  fi
  if notary_apple_id_ready; then
    ok "Notarization Option B: APPLE_ID + APPLE_TEAM_ID + app-specific password present"
    return 0
  fi
  info "Notarization Option B status (presence only):"
  [ -n "${APPLE_ID:-}" ] && ok "  APPLE_ID: configured" || warn "  APPLE_ID: absent"
  [ -n "${APPLE_TEAM_ID:-}" ] && ok "  APPLE_TEAM_ID: configured" || warn "  APPLE_TEAM_ID: absent"
  if notary_password_present; then
    ok "  APPLE_APP_SPECIFIC_PASSWORD or APPLE_PASSWORD: configured"
  else
    warn "  APPLE_APP_SPECIFIC_PASSWORD or APPLE_PASSWORD: absent"
  fi
  return 1
}

credentials_hold_instructions() {
  cat <<'EOF'
VERDICT: APPLE_NOTARIZATION_CREDENTIALS_HOLD

Configure notarization credentials locally only (never commit, never paste in chat):

Option A — Keychain profile (preferred after store-credentials):
  Add to ~/.jarvis/cloud-keys.env:
    APPLE_NOTARY_KEYCHAIN_PROFILE=OpenJarvisNotary
  Create profile:
    xcrun notarytool store-credentials OpenJarvisNotary --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID

Option B — Apple ID + app-specific password:
  Add to ~/.jarvis/cloud-keys.env:
    APPLE_ID=your-apple-id@email.com
    APPLE_TEAM_ID=YOUR_TEAM_ID
    APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
  Create app-specific password at: https://appleid.apple.com → Sign-In and Security → App-Specific Passwords

Option C — App Store Connect API key:
  Add to ~/.jarvis/cloud-keys.env:
    APPLE_API_KEY=YOUR_KEY_ID
    APPLE_API_ISSUER=YOUR_ISSUER_UUID
    APPLE_API_KEY_PATH=/path/to/AuthKey_XXXX.p8
  Store the .p8 file outside the repo (e.g. ~/.apple-signing/AuthKey.p8).

Then rerun:
  ./scripts/build-sign-personal.sh --install --notarize
EOF
}

header "OpenJarvis — Personal-use macOS sign pipeline"
echo -e "Scope: ${YELLOW}PERSONAL INSTALL ONLY${NC} · Plan 9 baseline preserved · Updater off"
echo ""

load_apple_env

SIGN_ID="${APPLE_SIGNING_IDENTITY:-${APPLE_DEVELOPER_IDENTITY:-}}"
TEAM_ID="${APPLE_TEAM_ID:-}"
NOTARY_PASSWORD="${APPLE_APP_SPECIFIC_PASSWORD:-${APPLE_PASSWORD:-}}"
KEYCHAIN_PROFILE="$(notary_keychain_profile)"

header "Preflight — toolchain"
XCODE_PATH="$(xcode-select -p 2>/dev/null || echo missing)"
info "xcode-select: $XCODE_PATH"
if xcode_is_full; then
  ok "Full Xcode selected"
else
  warn "Full Xcode not installed/selected"
fi
command -v codesign >/dev/null && ok "codesign present" || fail "codesign missing"
if has_notarytool; then ok "notarytool: $(xcrun --find notarytool)"; else warn "notarytool unavailable"; fi
if has_stapler; then ok "stapler: $(xcrun --find stapler)"; else warn "stapler unavailable"; fi
VALID_COUNT="$(security find-identity -v -p codesigning 2>/dev/null | awk '/valid identities found/ {print $1}' || echo 0)"
info "Keychain codesigning identities: ${VALID_COUNT} valid"

header "Preflight — signing config (presence only)"
if [ -n "$SIGN_ID" ]; then ok "APPLE_SIGNING_IDENTITY or APPLE_DEVELOPER_IDENTITY: configured"; else fail "No signing identity env var — set APPLE_SIGNING_IDENTITY in ~/.jarvis/cloud-keys.env"; fi
if [ -n "$TEAM_ID" ]; then ok "APPLE_TEAM_ID: configured"; else warn "APPLE_TEAM_ID: absent (required for notarization Option A)"; fi
if ! identity_in_keychain "$SIGN_ID"; then
  fail "Signing identity not found in keychain. Import Developer ID Application certificate first."
fi
ok "Signing identity found in keychain — name matched; cert not printed"

header "Preflight — notarization"
NOTARY_READY=true
if $DO_NOTARIZE; then
  if ! notary_tools_ready; then
    warn "notarytool/stapler required — install/update Command Line Tools or select full Xcode"
    NOTARY_READY=false
  else
    ok "Notarization tools ready via xcrun (full Xcode not required)"
  fi
  if ! report_notary_credential_status; then
    NOTARY_READY=false
  fi
  if $NOTARY_READY; then
    ok "Notarization preflight passed"
  else
    credentials_hold_instructions
    exit 3
  fi
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

header "Verify — codesign (bundle)"
codesign --verify --deep --strict --verbose=2 "$BUNDLE_APP"

if $DO_NOTARIZE && $NOTARY_READY; then
  header "Notarize + staple"
  ZIP_PATH="$REPO_ROOT/.apple-signing/OpenJarvis-notarize.zip"
  mkdir -p "$REPO_ROOT/.apple-signing"
  ditto -c -k --keepParent "$BUNDLE_APP" "$ZIP_PATH"
  if notary_keychain_profile_ready; then
    info "Submitting with Keychain profile: ${KEYCHAIN_PROFILE}"
    xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$KEYCHAIN_PROFILE" --wait
  elif notary_api_key_ready; then
    KEY_PATH="${APPLE_API_KEY_PATH:-$HOME/.apple-signing/AuthKey.p8}"
    info "Submitting with App Store Connect API key (credentials not printed)"
    xcrun notarytool submit "$ZIP_PATH" --wait --key "$KEY_PATH" --key-id "$APPLE_API_KEY" --issuer "$APPLE_API_ISSUER"
  else
    info "Submitting with Apple ID (credentials not printed)"
    xcrun notarytool submit "$ZIP_PATH" --wait --apple-id "$APPLE_ID" --password "$NOTARY_PASSWORD" --team-id "$TEAM_ID"
  fi
  xcrun stapler staple "$BUNDLE_APP"
  ok "Notarization + staple complete (bundle)"
fi

if $DO_INSTALL; then
  header "Install — /Applications/OpenJarvis.app"
  rm -rf "$SYS_APP"
  ditto "$BUNDLE_APP" "$SYS_APP"
  ok "Installed to $SYS_APP"
  TARGET_APP="$SYS_APP"
else
  TARGET_APP="$BUNDLE_APP"
fi

if $DO_NOTARIZE && $DO_INSTALL && $NOTARY_READY; then
  header "Staple — installed copy"
  xcrun stapler staple "$SYS_APP" 2>/dev/null || true
fi

header "Verify — installed/bundle app"
codesign --verify --deep --strict --verbose=2 "$TARGET_APP"
info "spctl assessment:"
spctl --assess --type execute --verbose=4 "$TARGET_APP" 2>&1 | grep -E 'accepted|rejected|Unnotarized|Notarized|source=' || true

header "Done"
ok "Personal signed build ready: $TARGET_APP"
echo "Manual verify: open app, confirm no Gatekeeper block, curl http://127.0.0.1:8000/health"
