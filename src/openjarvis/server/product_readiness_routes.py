"""Product / Multi-User Readiness REST Routes (Phase C4).

Routes:
  GET /v1/product-readiness/matrix           — readiness dimensions matrix
  GET /v1/product-readiness/multi-user-status — multi-user live status
  GET /v1/product-readiness/data-isolation   — per-user data isolation checklist

Design:
  - fake_data: False in all responses
  - production_multi_user_ready: False — never claim multi-user production support
  - inviting_real_users: False — always
  - changing_auth_security: False — always
  - exposing_user_data: False — always
  - All responses are planning/dry-run mode
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["product-readiness"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# GET /v1/product-readiness/matrix
# ---------------------------------------------------------------------------

@router.get("/v1/product-readiness/matrix")
async def get_readiness_matrix() -> Dict[str, Any]:
    """Return multi-dimensional product readiness matrix."""
    return {
        "readiness_dimensions": [
            {
                "dimension_id": "single_user_core",
                "name": "Single-User Core",
                "status": "ready",
                "description": (
                    "Chat, tasks, goals, routines, memory — complete for single user"
                ),
                "production_multi_user": False,
            },
            {
                "dimension_id": "auth_rbac",
                "name": "Authentication & RBAC",
                "status": "not_ready",
                "description": (
                    "Multi-user auth, role-based access control not yet implemented"
                ),
                "production_multi_user": False,
                "gap": "Requires production auth system (external gate)",
            },
            {
                "dimension_id": "data_isolation",
                "name": "User Data Isolation",
                "status": "not_ready",
                "description": (
                    "Per-user data isolation requires multi-tenant storage"
                ),
                "production_multi_user": False,
                "gap": "Requires tenant-scoped storage (external gate)",
            },
            {
                "dimension_id": "admin_controls",
                "name": "Admin Controls",
                "status": "partial",
                "description": (
                    "Admin authority/approval routes exist. "
                    "Full admin dashboard partial."
                ),
                "production_multi_user": False,
            },
            {
                "dimension_id": "self_service_onboarding",
                "name": "Self-Service Onboarding",
                "status": "not_ready",
                "description": (
                    "Onboarding flow not yet productized for external users"
                ),
                "production_multi_user": False,
                "gap": "Requires multi-user auth + invite flow (external gate)",
            },
            {
                "dimension_id": "compliance_audit",
                "name": "Compliance & Audit",
                "status": "partial",
                "description": (
                    "Internal audit log exists. External compliance certification "
                    "requires legal review."
                ),
                "production_multi_user": False,
            },
        ],
        "production_multi_user_ready": False,  # ALWAYS False — never claim
        "claiming_production_support": False,
        "fake_data": False,
        "note": (
            "Product readiness matrix. Single-user core ready. "
            "Multi-user requires external auth/RBAC gates."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/product-readiness/multi-user-status
# ---------------------------------------------------------------------------

@router.get("/v1/product-readiness/multi-user-status")
async def get_multi_user_status() -> Dict[str, Any]:
    """Return current multi-user live status and role/tenancy model."""
    return {
        "multi_user_live": False,
        "local_dry_run_model": True,
        "role_model": {
            "planned_roles": ["owner", "admin", "member", "viewer"],
            "implemented": False,
            "auth_backend": None,  # not yet set up
        },
        "tenancy_model": {
            "implemented": False,
            "storage_isolation": False,
            "session_isolation": False,
        },
        "admin_approval_required": True,
        "inviting_real_users": False,  # ALWAYS False
        "changing_auth_security": False,  # ALWAYS False
        "exposing_user_data": False,  # ALWAYS False
        "fake_data": False,
        "note": (
            "Multi-user is not live. Dry-run/planning mode only. "
            "No real users can be invited."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/product-readiness/data-isolation
# ---------------------------------------------------------------------------

@router.get("/v1/product-readiness/data-isolation")
async def get_data_isolation_status() -> Dict[str, Any]:
    """Return per-user data isolation checklist."""
    return {
        "isolation_checklist": [
            {
                "item": "per_user_storage_namespace",
                "implemented": False,
                "required_for": "multi-user",
            },
            {
                "item": "session_scoped_auth_tokens",
                "implemented": False,
                "required_for": "multi-user",
            },
            {
                "item": "api_key_per_user",
                "implemented": False,
                "required_for": "multi-user",
            },
            {
                "item": "audit_log_per_user",
                "implemented": False,
                "required_for": "multi-user",
            },
            {
                "item": "memory_namespace_isolation",
                "implemented": False,
                "required_for": "multi-user",
            },
            {
                "item": "local_single_user_storage",
                "implemented": True,
                "required_for": "single-user",
            },
        ],
        "single_user_isolation": True,  # current single-user mode is isolated
        "multi_user_isolation": False,
        "production_multi_user_ready": False,
        "fake_data": False,
    }
