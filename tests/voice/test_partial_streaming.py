"""Regression tests for Deepgram partial-streaming live transcript + endpoint.

Covers the root-cause bugs found in PLAN_2R_LIVE_TRANSCRIPT_ENDPOINTING:

  1. utterance_end_ms must be >= 1000 — Deepgram rejects < 1000 with HTTP 400,
     which silently disabled all live partials (start() returned False).
  2. interim_results must be enabled — required for live partial transcripts.
  3. _DGStreamPartial degrades gracefully (start() -> False, no exception)
     when the API key is invalid / connection fails.
  4. VoiceTurnEngine.status() exposes partial_diag (sprint-required
     diagnostics surface).
  5. The DG energy-VAD backstop constant exists and is well above the normal
     short silence window so Deepgram drives endpointing when connected.
"""

from __future__ import annotations

import re

from openjarvis.autonomy.voice_turn_engine import (
    _DG_VAD_BACKSTOP_MS,
    _DGStreamPartial,
    VoiceTurnEngine,
)


def _parse_query(url: str) -> dict:
    query = url.split("?", 1)[1]
    out: dict = {}
    for pair in query.split("&"):
        k, _, v = pair.partition("=")
        out[k] = v
    return out


def test_utterance_end_ms_at_least_1000() -> None:
    """Deepgram returns HTTP 400 for utterance_end_ms < 1000 (the original bug)."""
    q = _parse_query(_DGStreamPartial._DG_WSS)
    assert "utterance_end_ms" in q
    assert int(q["utterance_end_ms"]) >= 1000, (
        "utterance_end_ms < 1000 is rejected by Deepgram with HTTP 400 and "
        "silently disables live partials"
    )


def test_interim_results_enabled() -> None:
    """Live partial transcripts require interim_results=true."""
    q = _parse_query(_DGStreamPartial._DG_WSS)
    assert q.get("interim_results") == "true"


def test_linear16_16k_mono_declared() -> None:
    """Audio format sent matches the int16 16k mono PCM from the VAD recorder."""
    url = _DGStreamPartial._DG_WSS.format(sample_rate=16000, endpointing_ms=700)
    q = _parse_query(url)
    assert q.get("encoding") == "linear16"
    assert q.get("sample_rate") == "16000"
    assert q.get("channels") == "1"


def test_start_degrades_gracefully_on_bad_key() -> None:
    """Invalid key -> start() returns False, records last_error, no exception."""
    dg = _DGStreamPartial(
        api_key="invalid-key-for-test",
        sample_rate=16000,
        on_partial=lambda _t: None,
    )
    ok = dg.start()
    assert ok is False
    assert dg.connected is False
    assert dg.last_error is not None  # error surfaced, not swallowed


def test_status_exposes_partial_diag() -> None:
    """Engine status() surfaces the partial diagnostics dict."""
    engine = VoiceTurnEngine()
    status = engine.status()
    assert "partial_diag" in status


def test_dg_vad_backstop_above_short_window() -> None:
    """When Deepgram drives endpointing, energy VAD backstop is kept high."""
    assert _DG_VAD_BACKSTOP_MS >= 2000.0
