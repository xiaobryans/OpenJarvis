#!/usr/bin/env bash
# mobile-serve.sh — Serve OpenJarvis on LAN for mobile/PWA access proof
#
# Usage:
#   ./scripts/mobile-serve.sh              — start backend + Vite with LAN access
#   ./scripts/mobile-serve.sh --backend-only — only start backend (LAN-accessible)
#   ./scripts/mobile-serve.sh --frontend-only — only start Vite with host binding
#
# Access paths for Bryan's mobile proof:
#   1. Installed desktop app → resize window narrow → see mobile layout (no URL needed)
#   2. LAN dev server → http://<your-mac-ip>:5173 from phone on same WiFi
#   3. Tailscale → http://100.x.x.x:8000 if Tailscale is running (backend only)
#
# Getting your Mac's LAN IP:
#   ipconfig getifaddr en0     (WiFi)
#   ipconfig getifaddr en1     (Ethernet)
#
# Notes:
#   - Backend runs on 0.0.0.0:8000 (accessible on LAN by default)
#   - Frontend Vite dev server is bound to 0.0.0.0:5173 via --host flag
#   - PWA manifest is active — browser will offer "Add to Home Screen"
#   - This is for local/personal access only. No credentials served over LAN.
#   - Do not expose to public internet without auth hardening.
#
set -euo pipefail

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${BLUE}[info]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}   $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }

BACKEND_ONLY=false
FRONTEND_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
  esac
done

# Discover LAN IP
LAN_IP=""
for iface in en0 en1 en2; do
  candidate=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  if [[ -n "$candidate" ]]; then
    LAN_IP="$candidate"
    break
  fi
done

if [[ -n "$LAN_IP" ]]; then
  ok "Mac LAN IP detected: $LAN_IP"
else
  warn "Could not detect LAN IP. Try: ipconfig getifaddr en0"
fi

# Start backend
if [[ "$FRONTEND_ONLY" == "false" ]]; then
  info "Starting backend on 0.0.0.0:8000 …"
  uv run jarvis serve --port 8000 --host 0.0.0.0 &>/tmp/jarvis-backend.log &
  BACKEND_PID=$!
  sleep 2
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "Backend running: http://localhost:8000"
    [[ -n "$LAN_IP" ]] && ok "Backend LAN:    http://${LAN_IP}:8000"
  else
    warn "Backend may still be starting. Check: tail -f /tmp/jarvis-backend.log"
  fi
fi

# Start frontend
if [[ "$BACKEND_ONLY" == "false" ]]; then
  info "Starting Vite frontend with LAN host binding …"
  cd frontend
  VITE_API_URL="http://localhost:8000" npx vite --host 0.0.0.0 --port 5173 &
  FRONTEND_PID=$!
  cd ..
  sleep 3
  ok "Frontend dev server started"
  echo ""
  echo "────────────────────────────────────────────────"
  echo "  Mobile / PWA access paths:"
  echo ""
  echo "  Desktop narrow:  Resize /Applications/OpenJarvis.app window to <768px"
  echo "  Local browser:   http://localhost:5173"
  [[ -n "$LAN_IP" ]] && echo "  LAN (phone):     http://${LAN_IP}:5173"
  echo "  Tailscale:       http://\$(tailscale ip -4 2>/dev/null || echo '[tailscale-ip]'):8000"
  echo ""
  echo "  PWA install: Open LAN URL in Safari/Chrome → Add to Home Screen"
  echo "────────────────────────────────────────────────"
fi

# Keep alive
echo "Press Ctrl+C to stop all servers."
wait
