"""US15 validation runner profiles — local-first pytest targets for workbench."""

from __future__ import annotations

from typing import Any, Dict, List

VALIDATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "workbench_smoke": {
        "description": "Fast workbench smoke tests",
        "command": "python -m pytest tests/workbench/test_us14a_fixture.py -q --tb=short",
        "timeout": 60,
        "local_first": True,
    },
    "workbench_us15": {
        "description": "US15 foundation tests",
        "command": "python -m pytest tests/workbench/test_us15_foundation.py -q --tb=short",
        "timeout": 120,
        "local_first": True,
    },
    "workbench_full": {
        "description": "All workbench tests",
        "command": "python -m pytest tests/workbench/ -q --tb=short",
        "timeout": 300,
        "local_first": True,
    },
    "voice_us13_parked": {
        "description": "US13 voice tests (parked — not release gate)",
        "command": "python -m pytest tests/test_voice_cli.py tests/test_us13_voice_readiness.py -q --tb=short",
        "timeout": 180,
        "local_first": True,
        "release_gate": False,
        "note": "US13 voice HOLD — excluded from US15/US16 release readiness",
    },
    "changed_backend": {
        "description": "Backend pytest with fail-fast",
        "command": "python -m pytest tests/ -x -q --tb=short 2>&1 | head -120",
        "timeout": 300,
        "local_first": True,
    },
}


def list_validation_profiles() -> List[Dict[str, Any]]:
    return [
        {"profile_id": pid, **meta}
        for pid, meta in VALIDATION_PROFILES.items()
    ]


def get_validation_profile(profile_id: str) -> Dict[str, Any]:
    if profile_id not in VALIDATION_PROFILES:
        raise KeyError(f"Unknown validation profile: {profile_id}")
    return {"profile_id": profile_id, **VALIDATION_PROFILES[profile_id]}


__all__ = ["VALIDATION_PROFILES", "list_validation_profiles", "get_validation_profile"]
