"""Lean ASGI entrypoint for Railway (WhatsApp webhook).

Railway only needs a small, public HTTP service for the Twilio WhatsApp webhook —
NOT the full desktop app. This entrypoint builds a minimal FastAPI app with just
the webhook + briefing routes and a memory backend, deliberately avoiding the
full ``create_app()`` (which imports the voice pipeline / ``sounddevice`` and
needs the native PortAudio lib that isn't present on Railway).

Start command (see railway.toml / Procfile):
    uvicorn openjarvis.server.railway_app:app --host 0.0.0.0 --port $PORT

Required env vars on Railway (set the MINIMUM the webhook needs — do NOT dump
your entire .env onto a public server):
    OPENAI_API_KEY        (orchestrator planning/synthesis + Whisper STT)
    TWILIO_ACCOUNT_SID    (send WhatsApp replies)
    TWILIO_AUTH_TOKEN
    TWILIO_WHATSAPP_FROM  (optional; defaults to the Twilio sandbox number)
Add connector creds (GOOGLE_*, SLACK_BOT_TOKEN, …) ONLY if you want WhatsApp to
reach those — each one you add is a secret exposed to the cloud host.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger("openjarvis.railway")

app = FastAPI(title="VANTA Webhook", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "vanta-webhook"}


@app.on_event("startup")
async def _startup() -> None:
    # Load env (Railway injects vars into the process env; this also reads any
    # mounted .env) and attach a memory backend for cross-channel continuity.
    try:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
    except Exception:
        logger.debug("env load skipped", exc_info=True)
    try:
        from openjarvis.core.config import load_config
        from openjarvis.core.registry import MemoryRegistry
        import openjarvis.tools.storage  # noqa: F401 register sqlite backend

        cfg = load_config()
        app.state.memory_backend = MemoryRegistry.create(
            "sqlite", db_path=cfg.memory.db_path
        )
    except Exception as exc:
        logger.warning("memory backend unavailable on startup: %s", exc)
        app.state.memory_backend = None


# Mount routes (import lazily so a missing optional dep can't crash startup).
try:
    from openjarvis.server.whatsapp_routes import router as whatsapp_router

    app.include_router(whatsapp_router)
except Exception as exc:  # pragma: no cover
    logger.error("WhatsApp routes failed to mount: %s", exc, exc_info=True)

try:
    from openjarvis.server.briefing_routes import router as briefing_router

    app.include_router(briefing_router)
except Exception:  # pragma: no cover
    logger.debug("Briefing routes not mounted", exc_info=True)
