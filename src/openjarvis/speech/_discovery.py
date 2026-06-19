"""Auto-discover available speech-to-text backends.

Priority (Voice Safety Sprint):
  Deepgram is the primary/default STT provider.
  JARVIS_STT_PROVIDER env var overrides discovery order.
  Existing providers (faster-whisper, openai) remain as fallback.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from openjarvis.core.config import JarvisConfig
    from openjarvis.speech._stubs import SpeechBackend

# Default priority: deepgram primary, local as fallback
_DEFAULT_DISCOVERY_ORDER: List[str] = [
    "deepgram",
    "faster-whisper",
    "openai",
]

# Legacy alias kept for import compatibility
DISCOVERY_ORDER = _DEFAULT_DISCOVERY_ORDER


def _get_discovery_order() -> List[str]:
    """Return STT discovery order, respecting JARVIS_STT_PROVIDER override."""
    stt_provider = os.environ.get("JARVIS_STT_PROVIDER", "").strip().lower()
    if not stt_provider or stt_provider == "deepgram":
        # Deepgram first (default)
        return _DEFAULT_DISCOVERY_ORDER
    # Explicit override: put the requested provider first, then default order
    order = [stt_provider]
    for p in _DEFAULT_DISCOVERY_ORDER:
        if p != stt_provider:
            order.append(p)
    return order


def _create_backend(
    key: str,
    config: "JarvisConfig",
) -> Optional["SpeechBackend"]:
    """Try to instantiate a speech backend by registry key."""
    from openjarvis.core.registry import SpeechRegistry

    if not SpeechRegistry.contains(key):
        return None

    try:
        backend_cls = SpeechRegistry.get(key)

        if key == "faster-whisper":
            return backend_cls(
                model_size=config.speech.model,
                device=config.speech.device,
                compute_type=config.speech.compute_type,
            )
        elif key == "openai":
            try:
                from openjarvis.projects.source_links import _load_openjarvis_env
                _load_openjarvis_env()
            except Exception:
                pass
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return None
            return backend_cls(api_key=api_key)
        elif key == "deepgram":
            try:
                from openjarvis.projects.source_links import _load_openjarvis_env
                _load_openjarvis_env()
            except Exception:
                pass
            api_key = os.environ.get("DEEPGRAM_API_KEY", "")
            if not api_key:
                return None
            return backend_cls(api_key=api_key)
        else:
            return backend_cls()
    except Exception:
        return None


def get_speech_backend(config: "JarvisConfig") -> Optional["SpeechBackend"]:
    """Resolve the speech backend from config.

    If ``config.speech.backend`` is ``"auto"``, tries backends in
    priority order (deepgram first by default) and returns the first healthy one.
    Override with JARVIS_STT_PROVIDER env var.
    """
    # Trigger registration of built-in backends
    import openjarvis.speech  # noqa: F401

    backend_key = config.speech.backend

    if backend_key != "auto":
        return _create_backend(backend_key, config)

    # Auto-discovery: deepgram first unless JARVIS_STT_PROVIDER overrides
    for key in _get_discovery_order():
        backend = _create_backend(key, config)
        if backend is not None and backend.health():
            return backend

    return None
