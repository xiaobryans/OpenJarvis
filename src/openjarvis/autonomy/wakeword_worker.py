"""Jarvis Wake-Word Worker — openwakeword listener process.

Runs in the isolated .wake_worker_venv (Python 3.12 + onnxruntime) as a
subprocess. Listens for "hey jarvis" via microphone and sends a trigger
to the main Jarvis process via Unix socket or localhost TCP.

Bridge protocol: newline-delimited JSON over Unix socket (default) or
localhost TCP (fallback). Each trigger message:
  {"event": "wake_word", "model": "hey_jarvis_v0.1", "score": <float>, "ts": <float>}

Safety rules:
  - Only localhost/Unix socket — no public endpoints.
  - No Tailscale Funnel.
  - No audio data sent over socket — only trigger event.
  - Score threshold configurable via JARVIS_WAKEWORD_THRESHOLD (default 0.5).
  - Main process receives trigger only; audio capture happens only in this worker.

Environment variables (read by worker process):
  JARVIS_WAKEWORD_SOCKET   Unix socket path (default: /tmp/jarvis_wakeword.sock)
  JARVIS_WAKEWORD_PORT     localhost TCP port if no Unix socket (default: 19876)
  JARVIS_WAKEWORD_THRESHOLD score threshold 0-1 (default: 0.5)
  JARVIS_WAKEWORD_MODEL    model name (default: hey_jarvis_v0.1)

This file is run directly by the wake-word worker launcher — it should NOT
be imported into the main Jarvis venv (it requires openwakeword + onnxruntime).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [wake-worker] %(levelname)s %(message)s",
)
logger = logging.getLogger("jarvis.wakeword_worker")

_SOCKET_PATH = os.environ.get("JARVIS_WAKEWORD_SOCKET", "/tmp/jarvis_wakeword.sock")
_TCP_PORT = int(os.environ.get("JARVIS_WAKEWORD_PORT", "19876"))
_THRESHOLD = float(os.environ.get("JARVIS_WAKEWORD_THRESHOLD", "0.3"))  # was 0.5; 0.3 is more sensitive
_MODEL = os.environ.get("JARVIS_WAKEWORD_MODEL", "hey_jarvis_v0.1")
_CHUNK_SIZE = 1280  # 80 ms at 16 kHz
_DEBUG = os.environ.get("JARVIS_WAKEWORD_DEBUG", "0") == "1"


def _send_msg(sock_conn: socket.socket, payload: dict) -> None:
    msg = json.dumps(payload)
    try:
        sock_conn.sendall((msg + "\n").encode("utf-8"))
    except OSError as exc:
        logger.warning("Socket send failed: %s", exc)


def _send_trigger(sock_conn: socket.socket, model: str, score: float) -> None:
    _send_msg(sock_conn, {"event": "wake_word", "model": model, "score": round(score, 4), "ts": time.time()})


def _open_socket() -> tuple[socket.socket, str]:
    """Open Unix socket or localhost TCP socket. Returns (socket, description)."""
    # Try Unix socket first
    try:
        import os as _os
        if _os.path.exists(_SOCKET_PATH):
            _os.unlink(_SOCKET_PATH)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(_SOCKET_PATH)
        srv.listen(1)
        srv.settimeout(0.1)
        return srv, f"unix:{_SOCKET_PATH}"
    except (OSError, AttributeError):
        pass

    # Fall back to localhost TCP
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", _TCP_PORT))
    srv.listen(1)
    srv.settimeout(0.1)
    return srv, f"tcp://127.0.0.1:{_TCP_PORT}"


def run_worker() -> None:
    """Main wake-word detection loop. Blocks until interrupted."""
    try:
        import numpy as np
        import sounddevice as sd
        from openwakeword.model import Model
    except ImportError as exc:
        logger.error("Missing dependency: %s — run in .wake_worker_venv", exc)
        sys.exit(1)

    logger.info("Loading model: %s (threshold=%.2f, debug=%s)", _MODEL, _THRESHOLD, _DEBUG)
    sys.stdout.flush()
    model = Model(wakeword_models=[_MODEL], inference_framework="onnx")
    loaded_keys = list(model.models.keys())
    logger.info("Model loaded: %s", loaded_keys)
    sys.stdout.flush()

    srv_sock, sock_desc = _open_socket()
    logger.info("Listening on %s", sock_desc)

    client_conn: socket.socket | None = None
    _frame_count = [0]  # mutable for nonlocal access in callback

    def _audio_callback(indata: "np.ndarray", frames: int, time_info, status) -> None:
        nonlocal client_conn
        if status:
            logger.warning("audio status: %s", status)
            sys.stdout.flush()
        # Convert to 16kHz mono int16
        audio_chunk = (indata[:, 0] * 32767).astype("int16")
        scores = model.predict(audio_chunk)
        _frame_count[0] += 1
        # Log first frame to confirm audio is flowing
        if _frame_count[0] == 1:
            logger.info("First audio frame received (audio stream is live)")
            sys.stdout.flush()
        for mdl_name, score in scores.items():
            if _DEBUG:
                logger.debug("score: model=%s score=%.4f threshold=%.2f", mdl_name, float(score), _THRESHOLD)
                sys.stdout.flush()
            if float(score) >= _THRESHOLD:
                logger.info("Wake word detected! model=%s score=%.3f", mdl_name, float(score))
                sys.stdout.flush()
                if client_conn is None:
                    logger.warning("No client connected — trigger dropped (bridge reconnect pending)")
                    return
                _send_trigger(client_conn, mdl_name, float(score))

    # Accept client connections (non-blocking poll)
    logger.info("Starting microphone stream (16kHz, chunk=%d samples)", _CHUNK_SIZE)

    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="float32",
        blocksize=_CHUNK_SIZE,
        callback=_audio_callback,
    ):
        logger.info("Worker ready — waiting for wake word 'hey jarvis' (threshold=%.2f)", _THRESHOLD)
        sys.stdout.flush()
        while True:
            # Poll for new client connection
            try:
                conn, _ = srv_sock.accept()
                if client_conn is not None:
                    try:
                        client_conn.close()
                    except OSError:
                        pass
                client_conn = conn
                logger.info("Client connected")
                sys.stdout.flush()
                # Send ready event so bridge knows worker is fully live
                _send_msg(client_conn, {
                    "event": "ready",
                    "model": _MODEL,
                    "threshold": _THRESHOLD,
                    "loaded_models": loaded_keys,
                    "ts": time.time(),
                })
            except socket.timeout:
                pass
            except KeyboardInterrupt:
                logger.info("Worker stopped by keyboard interrupt")
                sys.stdout.flush()
                break

    srv_sock.close()
    if client_conn:
        client_conn.close()


if __name__ == "__main__":
    run_worker()
