"""Jarvis Wave 1–4 Platform Foundation.

Wave 1 — Foundation (this sprint: scaffolds only)
  Epic A: Skill Platform        — skill_platform.py (wraps skills/jarvis_registry)
  Epic B: Automation Platform   — automation_platform.py (trigger/automation registry scaffold)
  Epic C: Knowledge Platform    — knowledge_platform.py (knowledge source registry scaffold)
  Epic D: Research Platform     — research_platform.py (research provider registry scaffold)

Wave 2 — Professional Intelligence   (not implemented)
  Epic E: Optimization Platform
  Epic F: Professional Skill Packs

Wave 3 — Creation & Media            (not implemented)
  Epic G: Content & Media Studio

Wave 4 — Jarvis Expansion            (not implemented)
  Epic H: Autonomous Expansion

Truthfulness rule: any module that cannot prove readiness reports
status="scaffolded" or "not_implemented" — never "ready" without evidence.
"""

from openjarvis.wave.platform_registry import (
    WavePlatformRegistry,
    WavePlatformStatus,
    get_wave_platform_summary,
)

__all__ = [
    "WavePlatformRegistry",
    "WavePlatformStatus",
    "get_wave_platform_summary",
]
