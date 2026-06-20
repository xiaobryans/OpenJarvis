"""Deepgram live (WebSocket) streaming STT — nova-2 with interim results.

Usage::

    from openjarvis.speech.deepgram_live import DeepgramLiveSession

    def on_partial(text: str) -> None:
        # called for each interim result while user speaks
        ...

    def on_final(text: str) -> None:
        # called once with the full committed transcript
        ...

    with DeepgramLiveSession(api_key, on_partial=on_partial, on_final=on_final) as session:
        for audio_chunk in mic_stream:          # raw PCM16 mono 16 kHz bytes
            session.send_chunk(audio_chunk)
        final_text = session.finish()           # signal end of audio, returns transcript

Error handling:
    All Deepgram errors are caught internally. ``session.ok`` is False if the
    WebSocket could not be established. ``finish()`` returns ``None`` on failure.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from contextlib import contextmanager
from typing import Callable, Generator, Optional

logger = logging.getLogger(__name__)

_DEEPGRAM_LIVE_AVAILABLE: bool = False
try:
    from deepgram import DeepgramClient  # noqa: F401
    from deepgram.listen.v1.raw_client import RawV1Client  # noqa: F401
    from deepgram.listen.v1.socket_client import (
        ListenV1Results,
        V1SocketClient,
    )
    _DEEPGRAM_LIVE_AVAILABLE = True
except ImportError:
    DeepgramClient = None  # type: ignore[assignment, misc]
    ListenV1Results = None  # type: ignore[assignment, misc]
    V1SocketClient = None   # type: ignore[assignment, misc]


class DeepgramLiveSession:
    """Thin wrapper around the Deepgram v1 WebSocket live STT client.

    Thread-safe. Collects interim results in order; exposes the latest
    partial transcript via ``current_partial`` and returns the final
    committed text from ``finish()``.
    """

    def __init__(
        self,
        api_key: str,
        *,
        language: str = "en",
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        sample_rate: int = 16000,
    ) -> None:
        self._api_key = api_key
        self._language = language
        self._on_partial = on_partial
        self._on_final = on_final
        self._sample_rate = sample_rate

        self.ok: bool = False
        self.current_partial: str = ""
        self._finals: list[str] = []
        self._lock = threading.Lock()
        self._done = threading.Event()

        self._conn_ctx = None  # RawV1Client context manager
        self._ws: Optional[V1SocketClient] = None  # type: ignore[type-arg]
        self._listener_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Open WebSocket connection and start background listener thread."""
        if not _DEEPGRAM_LIVE_AVAILABLE:
            logger.warning("deepgram_live: SDK not available — live STT disabled")
            return False

        api_key = self._api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            logger.warning("deepgram_live: DEEPGRAM_API_KEY not set")
            return False

        try:
            from deepgram import DeepgramClient as _DGC
            dg = _DGC(api_key=api_key)
            # Access the live endpoint through the raw v1 client
            raw = dg.listen.v1.raw_client

            self._conn_ctx = raw.connect(
                model="nova-2",
                language=self._language,
                encoding="linear16",
                sample_rate=str(self._sample_rate),
                interim_results="true",
                smart_format="true",
                endpointing="300",        # 300 ms utterance end (Deepgram-side)
                utterance_end_ms="500",   # emit UtteranceEnd after 500 ms silence
            )
            self._ws = self._conn_ctx.__enter__()

            # Register event handler
            def _on_message(msg: ListenV1Results) -> None:  # type: ignore[type-arg]
                try:
                    if msg is None:
                        return
                    ch = getattr(msg, "channel", None)
                    if ch is None:
                        return
                    alts = getattr(ch, "alternatives", [])
                    if not alts:
                        return
                    text = (alts[0].transcript or "").strip()
                    if not text:
                        return
                    is_final = bool(getattr(msg, "is_final", False))
                    with self._lock:
                        if is_final:
                            self._finals.append(text)
                            self.current_partial = ""
                            if self._on_final:
                                self._on_final(text)
                        else:
                            self.current_partial = text
                            if self._on_partial:
                                self._on_partial(text)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("deepgram_live _on_message error: %s", exc)

            self._ws.on("Results", _on_message)

            # Start the blocking listener in a daemon thread
            def _listen():
                try:
                    self._ws.start_listening()  # type: ignore[union-attr]
                except Exception as exc:  # noqa: BLE001
                    logger.debug("deepgram_live listener error: %s", exc)
                finally:
                    self._done.set()

            self._listener_thread = threading.Thread(target=_listen, daemon=True, name="dg-live-listener")
            self._listener_thread.start()
            self.ok = True
            logger.debug("deepgram_live: WebSocket open (lang=%s sr=%d)", self._language, self._sample_rate)
            return True

        except Exception as exc:  # noqa: BLE001
            logger.warning("deepgram_live: failed to open WebSocket: %s", exc)
            self.ok = False
            return False

    def send_chunk(self, audio_bytes: bytes) -> None:
        """Send a PCM16 audio chunk. Safe to call if session is not ok."""
        if not self.ok or self._ws is None:
            return
        try:
            self._ws.send_media(audio_bytes)
        except Exception as exc:  # noqa: BLE001
            logger.debug("deepgram_live send_media error: %s", exc)
            self.ok = False

    def finish(self, timeout: float = 5.0) -> Optional[str]:
        """Signal end of audio and return the full committed transcript.

        Waits up to *timeout* seconds for Deepgram to flush remaining
        transcripts. Returns ``None`` if the session was not ok.
        """
        if not self.ok or self._ws is None:
            return None
        try:
            self._ws.send_close_stream()
            # Wait for listener thread to finish processing remaining results
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and self._listener_thread and self._listener_thread.is_alive():
                self._done.wait(timeout=0.1)
        except Exception as exc:  # noqa: BLE001
            logger.debug("deepgram_live finish error: %s", exc)
        finally:
            self._close_conn()

        with self._lock:
            # Combine all final segments into one transcript
            result = " ".join(self._finals).strip()
            # Also include any remaining partial that didn't get finalized
            if not result and self.current_partial:
                result = self.current_partial
            return result or None

    def _close_conn(self) -> None:
        if self._conn_ctx is not None:
            try:
                self._conn_ctx.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._conn_ctx = None

    def close(self) -> None:
        """Forcibly close the connection without waiting for transcript."""
        self.ok = False
        try:
            if self._ws is not None:
                self._ws.send_close_stream()
        except Exception:  # noqa: BLE001
            pass
        self._close_conn()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "DeepgramLiveSession":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@contextmanager
def deepgram_live_session(
    api_key: str = "",
    *,
    language: str = "en",
    on_partial: Optional[Callable[[str], None]] = None,
    on_final: Optional[Callable[[str], None]] = None,
    sample_rate: int = 16000,
) -> Generator[DeepgramLiveSession, None, None]:
    """Convenience context manager — creates, starts, and closes a session."""
    session = DeepgramLiveSession(
        api_key or os.environ.get("DEEPGRAM_API_KEY", ""),
        language=language,
        on_partial=on_partial,
        on_final=on_final,
        sample_rate=sample_rate,
    )
    session.start()
    try:
        yield session
    finally:
        session.close()
