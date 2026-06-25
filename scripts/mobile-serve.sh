#!/usr/bin/env bash
# mobile-serve.sh — Serve OpenJarvis on LAN for mobile/PWA access proof
#
# Usage (run from repo root):
#   bash scripts/mobile-serve.sh              — start backend + Vite with LAN access
#   bash scripts/mobile-serve.sh --frontend-only — only start Vite (if backend already running)
#   bash scripts/mobile-serve.sh --print-urls — print URLs without starting servers
#
# Direct access URLs (active on this machine as of 2026-06-26):
#   Mac local:   http://localhost:5173
#   LAN (phone): http://192.168.1.16:5173   ← open this on your phone (same WiFi)
#   Tailscale:   http://100.103.51.30:5173  ← works across networks if Tailscale is on
#
# PWA install: open the LAN or Tailscale URL in Safari/Chrome → Share → Add to Home Screen
#
# Notes:
#   - Script must be run from the OpenJarvis repo root (cd /path/to/OpenJarvis first)
#   - Vite dev server is bound to 0.0.0.0 (all interfaces) via vite.config host: true
#   - Backend proxy is server-side: phone → Vite → localhost:8000 (no LAN backend exposure)
#   - This is for local/personal access only. No credentials served directly over LAN.
#   - Do not expose to public internet without auth hardening.
#
set -euo pipefail

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${BLUE}[info]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}   $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }

BACKEND_ONLY=false
FRONTEND_ONLY=false
PRINT_URLS=false
for arg in "$@"; do
  case "$arg" in
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --print-urls)    PRINT_URLS=true ;;
  esac
done

# Verify we are in the repo root
if [[ ! -f "frontend/vite.config.ts" && ! -f "frontend/package.json" ]]; then
  warn "This script must be run from the OpenJarvis repo root."
  warn "Example: cd /path/to/OpenJarvis && bash scripts/mobile-serve.sh"
  exit 1
fi

# Discover LAN IP
LAN_IP=""
for iface in en0 en1 en2 utun0; do
  candidate=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  if [[ -n "$candidate" && "$candidate" != "127."* ]]; then
    LAN_IP="$candidate"
    break
  fi
done

# Discover Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)

print_urls() {
  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "  OpenJarvis Mobile / PWA access URLs"
  echo ""
  echo "  Desktop narrow:   Resize /Applications/OpenJarvis.app to <768px"
  echo "  Mac local:        http://localhost:5173"
  if [[ -n "$LAN_IP" ]]; then
    echo "  LAN phone:        http://${LAN_IP}:5173    ← OPEN THIS ON YOUR PHONE"
  else
    echo "  LAN phone:        [could not detect WiFi IP — check ipconfig getifaddr en0]"
  fi
  if [[ -n "$TAILSCALE_IP" ]]; then
    echo "  Tailscale:        http://${TAILSCALE_IP}:5173"
  fi
  echo ""
  echo "  PWA install: open LAN/Tailscale URL in Safari/Chrome → Add to Home Screen"
  echo "────────────────────────────────────────────────────────────"
  echo ""
}

if [[ "$PRINT_URLS" == "true" ]]; then
  print_urls
  exit 0
fi

if [[ -n "$LAN_IP" ]]; then
  ok "Mac WiFi IP: $LAN_IP"
else
  warn "Could not auto-detect LAN IP. Run: ipconfig getifaddr en0"
fi

# Start backend
if [[ "$FRONTEND_ONLY" == "false" ]]; then
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "Backend already running on localhost:8000"
  else
    info "Starting backend on localhost:8000 …"
    uv run jarvis serve --port 8000 &>/tmp/jarvis-backend.log &
    BACKEND_PID=$!
    sleep 3
    if curl -sf http://localhost:8000/health &>/dev/null; then
      ok "Backend started: http://localhost:8000"
    else
      warn "Backend may still be starting. Check: tail -f /tmp/jarvis-backend.log"
    fi
  fi
fi

# Start frontend (Vite has host: true in vite.config.ts — binds to all interfaces)
if [[ "$BACKEND_ONLY" == "false" ]]; then
  if curl -sf http://localhost:5173 -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200"; then
    ok "Vite already running on port 5173"
  else
    info "Starting Vite dev server (host: true — all interfaces) …"
    VITE_API_URL="http://localhost:8000" npx --prefix frontend vite --port 5173 &>/tmp/jarvis-vite.log &
    sleep 4
    if curl -sf http://localhost:5173 -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200"; then
      ok "Vite started"
    else
      warn "Vite may still be starting. Check: tail -f /tmp/jarvis-vite.log"
    fi
  fi
fi

print_urls

echo "Press Ctrl+C to stop."
wait
