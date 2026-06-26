"""WhatsApp Phase 1 — Twilio webhook -> VANTA.

Inbound WhatsApp messages (Twilio sandbox) are:
  1. Acknowledged within ~2s ("On it, boss…") via Twilio REST — never left on
     read.
  2. Processed asynchronously: voice notes are transcribed (Whisper/OpenAI),
     then the text is routed through the SAME tier classifier + lean
     orchestrator the desktop uses (real tools, real data), sharing the SAME
     memory backend for cross-channel continuity.
  3. The result is sent back via Twilio REST.

Group chats: only responds when the message tags @VANTA.

Phase 1 is text in / text out (+ voice-note transcription -> text reply).
ElevenLabs voice replies are Phase 2 (key not yet configured).

Env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, optional TWILIO_WHATSAPP_FROM
(defaults to the Twilio sandbox number), OPENAI_API_KEY (Whisper).
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Response

logger = logging.getLogger("openjarvis.whatsapp")
router = APIRouter()

_SANDBOX_FROM = "whatsapp:+14155238886"  # Twilio WhatsApp sandbox sender


def _twilio_send(to: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio REST. Best-effort; logs on failure."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    sender = os.environ.get("TWILIO_WHATSAPP_FROM", _SANDBOX_FROM)
    if not (sid and token):
        logger.error("Twilio not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN)")
        return False
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"From": sender, "To": to, "Body": body[:1550]},
            )
            if r.status_code >= 300:
                logger.error("Twilio send failed %s: %s", r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:
        logger.error("Twilio send error: %s", exc, exc_info=True)
        return False


def _transcribe_media(media_url: str) -> str:
    """Download a Twilio media URL (auth) and transcribe via Whisper/OpenAI."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    okey = os.environ.get("OPENAI_API_KEY", "")
    if not okey:
        return "(voice note received, but Whisper STT needs OPENAI_API_KEY)"
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as c:
            audio = c.get(media_url, auth=(sid, token)).content
            r = c.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {okey}"},
                files={"file": ("voice.ogg", audio, "audio/ogg")},
                data={"model": "whisper-1"},
            )
            r.raise_for_status()
            return r.json().get("text", "") or "(empty transcription)"
    except Exception as exc:
        logger.error("transcription failed: %s", exc, exc_info=True)
        return f"(could not transcribe voice note: {exc})"


def process_whatsapp_message(
    from_number: str, text: str, memory_backend=None
) -> str:
    """Route an inbound WhatsApp text through tier classification + orchestrator
    (shared memory). Returns the reply text. Used by the webhook + tests."""
    from openjarvis.core.env_loader import ensure_local_env_loaded
    ensure_local_env_loaded()

    # Cross-channel memory continuity: save the inbound turn.
    if memory_backend is not None:
        try:
            memory_backend.store(text, source="whatsapp",
                                 metadata={"role": "user", "channel": "whatsapp"})
        except Exception:
            logger.debug("whatsapp memory save failed", exc_info=True)

    from openjarvis.orchestrator.request_classifier import classify_request

    tier = classify_request(text).tier
    try:
        # Always route through the hierarchy so even "instant" questions use REAL
        # tools (e.g. current_time) — a pure-LLM direct answer would deflect on
        # time/date. The orchestrator self-recovers if no tool is needed.
        from openjarvis.orchestrator.lean import LeanOrchestrator
        orch = LeanOrchestrator(model="gpt-4o")
        res = (orch.run_complex(text) if tier == "complex"
               else orch.run_standard(text))
        answer = res.answer
    except Exception as exc:
        logger.error("whatsapp processing failed: %s", exc, exc_info=True)
        answer = ("I hit a snag handling that, boss — try again in a moment.")

    if memory_backend is not None and answer:
        try:
            memory_backend.store(answer, source="whatsapp",
                                 metadata={"role": "assistant", "channel": "whatsapp"})
        except Exception:
            logger.debug("whatsapp memory save (reply) failed", exc_info=True)
    return answer


@router.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Twilio WhatsApp inbound webhook. Acks fast, processes async."""
    form = await request.form()
    from_number = form.get("From", "")
    body = (form.get("Body", "") or "").strip()
    num_media = int(form.get("NumMedia", "0") or 0)
    media_url = form.get("MediaUrl0", "") if num_media > 0 else ""
    media_type = form.get("MediaContentType0", "") if num_media > 0 else ""
    # Group messages: Twilio sets a group-style From; only respond if tagged.
    is_group = "g.us" in from_number or form.get("NumGroupMembers")
    if is_group and "@vanta" not in body.lower():
        return Response(content="<Response></Response>", media_type="application/xml")

    memory_backend = getattr(request.app.state, "memory_backend", None)

    # 1. Immediate acknowledgement (< 2s) — never leave Bryan on read.
    _twilio_send(from_number, "On it, boss — give me a moment… 🟦")

    # 2. Process asynchronously and send the result.
    def _work() -> None:
        text = body
        if media_url and media_type.startswith("audio"):
            text = _transcribe_media(media_url)
        elif media_url:
            text = (body or "") + f"\n[received a {media_type or 'file'} — "
            "image/document analysis is Phase 2]"
        if not text.strip():
            text = "(empty message)"
        answer = process_whatsapp_message(from_number, text, memory_backend)
        _twilio_send(from_number, answer)

    background_tasks.add_task(_work)
    # Empty TwiML so Twilio doesn't also auto-reply.
    return Response(content="<Response></Response>", media_type="application/xml")
