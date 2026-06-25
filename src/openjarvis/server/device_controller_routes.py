"""Device Controller REST Routes (B20).

Routes:
  GET  /v1/device-controller/status          — device controller availability (simulator only)
  POST /v1/device-controller/commands/plan   — dry-run command plan (never executes)
  GET  /v1/device-controller/safety-matrix   — safety rules enforced by device controller

Design:
  - fake_data: False, fake_live: False in all responses
  - Simulator/dry-run only — no physical device control under any circumstances
  - All commands require Tier 4 approval before any future integration
  - Physical world execution is always blocked
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for device_controller routes")

logger = logging.getLogger(__name__)
router = APIRouter(tags=["device-controller"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# GET /v1/device-controller/status
# ---------------------------------------------------------------------------


@router.get("/v1/device-controller/status")
async def device_controller_status() -> Dict[str, Any]:
    """Return device controller status. Simulator/dry-run only; no physical device control."""
    return {
        "robotics_available": False,
        "device_control_live": False,
        "simulator_mode": True,  # Only mode available
        "supported_device_types": [
            {
                "type": "Smart Home (lights, thermostat)",
                "live": False,
                "gate": "Home automation library + Tier 4 approval required",
            },
            {
                "type": "IoT sensors",
                "live": False,
                "gate": "IoT SDK + Tier 4 approval required",
            },
            {
                "type": "Robotic actuators",
                "live": False,
                "gate": "Robot SDK + Tier 4 approval + physical safety review",
            },
            {
                "type": "Mobile device control",
                "live": False,
                "gate": "ADB/MDM integration + Tier 4 approval required",
            },
        ],
        "physical_world_execution": False,
        "fake_live": False,
        "fake_data": False,
        "safety": {
            "approval_required": True,
            "physical_actions_blocked": True,
            "dry_run_only": True,
            "authority_tier": "tier4_minimum",
        },
        "note": (
            "Device controller is simulator/dry-run only. "
            "No physical device control. All commands require Tier 4 approval."
        ),
    }


# ---------------------------------------------------------------------------
# POST /v1/device-controller/commands/plan
# ---------------------------------------------------------------------------


class DeviceCommandPlanRequest(BaseModel):
    device_type: str = Field(..., description="Target device type (e.g. 'smart_home')")
    command: str = Field(..., description="Command to plan (e.g. 'turn_on')")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Command parameters"
    )
    reason: str = Field("", description="Reason/justification for the command")


@router.post("/v1/device-controller/commands/plan")
async def plan_device_command(body: DeviceCommandPlanRequest) -> Dict[str, Any]:
    """Dry-run device command plan — produces a step plan, never executes anything.

    device_type and command must be non-empty strings; returns 422 otherwise.
    Tier 4 approval is required before any future device integration can proceed.
    """
    try:
        device_type = (body.device_type or "").strip()
        command = (body.command or "").strip()

        if not device_type:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_device_type",
                    "message": "device_type must be a non-empty string",
                },
            )
        if not command:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_command",
                    "message": "command must be a non-empty string",
                },
            )

        return {
            "dry_run": True,
            "device_type": device_type,
            "command": command,
            "plan": [
                {
                    "step": 1,
                    "description": (
                        f"Validate device type and command safety for: "
                        f"{device_type}/{command}"
                    ),
                },
                {
                    "step": 2,
                    "description": "Request Tier 4 approval for device command",
                },
                {
                    "step": 3,
                    "description": (
                        f"Execute: {command} on {device_type} "
                        f"(requires device integration — external gate)"
                    ),
                },
            ],
            "executed": False,
            "physical_action": False,
            "approval_required": True,
            "authority_tier": "tier4_minimum",
            "device_live": False,
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_device_command: unexpected error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "plan_failed", "message": "Could not generate command plan"},
        ) from exc


# ---------------------------------------------------------------------------
# GET /v1/device-controller/safety-matrix
# ---------------------------------------------------------------------------


@router.get("/v1/device-controller/safety-matrix")
async def safety_matrix() -> Dict[str, Any]:
    """Return the enforced safety rules for the device controller."""
    return {
        "safety_rules": [
            {
                "rule_id": "no_physical_execution",
                "description": (
                    "No commands may cause physical device actuation without "
                    "Tier 4 approval and safety review"
                ),
                "enforced": True,
            },
            {
                "rule_id": "dry_run_first",
                "description": (
                    "All device commands must be simulated in dry-run mode "
                    "before any live execution"
                ),
                "enforced": True,
            },
            {
                "rule_id": "human_in_loop",
                "description": (
                    "Human must review and approve every device action — "
                    "no autonomous device control"
                ),
                "enforced": True,
            },
            {
                "rule_id": "no_irreversible_actions",
                "description": (
                    "Irreversible physical actions (hardware state changes, "
                    "actuator movements) require explicit confirmation"
                ),
                "enforced": True,
            },
            {
                "rule_id": "sandboxed_simulation",
                "description": (
                    "Simulation environment must be isolated from live "
                    "device bus/network"
                ),
                "enforced": True,
            },
            {
                "rule_id": "emergency_stop",
                "description": (
                    "Emergency stop must be reachable within 1 hop from any "
                    "device control interface"
                ),
                "enforced": True,
            },
        ],
        "physical_world_execution": False,
        "fake_live": False,
        "fake_data": False,
    }
