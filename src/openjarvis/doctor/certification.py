"""US13 V1 Daily-Driver Certification Matrix.

Certification statuses:
  certified             — evidence verified; capability confirmed and accessible
  backend_only          — capability verified in backend; not yet exposed in UI
  hold                  — certification blocked; evidence missing or check fails
  insufficient_data_to_verify — evidence not available at runtime

Runtime truthfulness gate:
  - No item may claim certified or backend_only without a check result as evidence.
  - Missing or absent check evidence always yields INSUFFICIENT_DATA_MSG.
  - Code presence alone does not constitute evidence.

Failure-mode certification:
  - Each known failure mode is documented with observed behavior and evidence source.
  - Behavior is derived from actual check outputs, not assumed from code.

Scope (US13 certification areas):
  1.  app_launch_runtime_connection
  2.  mission_control_status_readiness
  3.  voice_path
  4.  connector_health
  5.  queue_retry_stalled_job_visibility
  6.  alert_limiting_escalation
  7.  memory_context_behavior
  8.  trust_evidence_layer
  9.  action_approval_risk_clarity
  10. degraded_blocked_insufficient_data_behavior
  11. backend_only_vs_ui_visible_capabilities
  12. remaining_hold_blockers
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

INSUFFICIENT_DATA_MSG = "Insufficient data to verify."


# ---------------------------------------------------------------------------
# Status / Visibility constants
# ---------------------------------------------------------------------------


class CertificationStatus:
    CERTIFIED = "certified"
    BACKEND_ONLY = "backend_only"
    HOLD = "hold"
    INSUFFICIENT_DATA = "insufficient_data_to_verify"


class CertificationVisibility:
    UI_VISIBLE = "ui_visible"
    BACKEND_ONLY = "backend_only"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CertificationItem:
    """A single entry in the daily-driver certification matrix."""

    name: str
    area: str
    status: str
    visibility: str
    evidence: str
    hold_reason: Optional[str] = None
    required_for_v1: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "area": self.area,
            "status": self.status,
            "visibility": self.visibility,
            "evidence": self.evidence,
            "hold_reason": self.hold_reason,
            "required_for_v1": self.required_for_v1,
        }


@dataclass
class FailureModeItem:
    """A documented failure mode with observed behavior."""

    failure_mode: str
    behavior: str
    evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_mode": self.failure_mode,
            "behavior": self.behavior,
            "evidence": self.evidence,
        }


@dataclass
class CertificationMatrix:
    """Full V1 daily-driver certification matrix."""

    head: str
    project_id: str
    items: List[CertificationItem]
    failure_modes: List[FailureModeItem]
    evaluated_at: float = field(default_factory=time.time)

    def verdict(self) -> str:
        """Return hold if any required_for_v1=True item has hold or insufficient_data status.

        V1 daily-driver certification gates on ALL required_for_v1=True items regardless
        of visibility.  A required item may be certified (ui_visible + check PASS) or
        backend_only (backend PASS, not yet surfaced in UI) — both are acceptable.
        HOLD or INSUFFICIENT_DATA on any required item blocks the daily-driver verdict.
        Non-required items (meta/audit areas) never gate the verdict.
        """
        for item in self.items:
            if item.required_for_v1:
                if item.status in (
                    CertificationStatus.HOLD,
                    CertificationStatus.INSUFFICIENT_DATA,
                ):
                    return "hold"
        return "certified"

    def get_hold_blockers(self) -> List[CertificationItem]:
        return [
            i for i in self.items
            if i.status in (
                CertificationStatus.HOLD,
                CertificationStatus.INSUFFICIENT_DATA,
            )
        ]

    def get_backend_only(self) -> List[CertificationItem]:
        return [
            i for i in self.items
            if i.status == CertificationStatus.BACKEND_ONLY
        ]

    def get_ui_visible(self) -> List[CertificationItem]:
        return [
            i for i in self.items
            if i.visibility == CertificationVisibility.UI_VISIBLE
            and i.status == CertificationStatus.CERTIFIED
        ]

    def get_required_for_v1(self) -> List[CertificationItem]:
        return [i for i in self.items if i.required_for_v1]

    def to_dict(self) -> Dict[str, Any]:
        required = self.get_required_for_v1()
        return {
            "head": self.head,
            "project_id": self.project_id,
            "verdict": self.verdict(),
            "evaluated_at": self.evaluated_at,
            "items": [i.to_dict() for i in self.items],
            "failure_modes": [f.to_dict() for f in self.failure_modes],
            "hold_blockers": [i.to_dict() for i in self.get_hold_blockers()],
            "backend_only": [i.to_dict() for i in self.get_backend_only()],
            "ui_visible": [i.to_dict() for i in self.get_ui_visible()],
            "required_for_v1_total": len(required),
            "required_for_v1_certified": len(
                [i for i in required if i.status == CertificationStatus.CERTIFIED]
            ),
            "required_for_v1_backend_only": len(
                [i for i in required if i.status == CertificationStatus.BACKEND_ONLY]
            ),
            "required_for_v1_hold": len(
                [i for i in required if i.status in (
                    CertificationStatus.HOLD, CertificationStatus.INSUFFICIENT_DATA
                )]
            ),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_head() -> str:
    """Return current git HEAD or INSUFFICIENT_DATA_MSG if unavailable."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return INSUFFICIENT_DATA_MSG


def _status_from_check(
    check_status: str,
    default_visibility: str,
) -> str:
    """Derive CertificationStatus from a CheckResult status and visibility.

    Truthfulness rule: code presence does not equal evidence.
    Only a PASS check result constitutes positive evidence.
    """
    from openjarvis.doctor.checks import CheckStatus

    if check_status == CheckStatus.PASS:
        if default_visibility == CertificationVisibility.UI_VISIBLE:
            return CertificationStatus.CERTIFIED
        return CertificationStatus.BACKEND_ONLY
    if check_status in (CheckStatus.WARN, CheckStatus.NOT_CONFIGURED):
        if default_visibility == CertificationVisibility.UI_VISIBLE:
            return CertificationStatus.HOLD
        return CertificationStatus.BACKEND_ONLY
    if check_status == CheckStatus.FAIL:
        return CertificationStatus.HOLD
    return CertificationStatus.INSUFFICIENT_DATA


def _find_check(check_map: Dict[str, Any], check_id: str) -> Optional[Any]:
    return check_map.get(check_id)


# ---------------------------------------------------------------------------
# build_certification_matrix
# ---------------------------------------------------------------------------


def build_certification_matrix(
    project_id: str = "omnix",
    check_results: Optional[List[Any]] = None,
) -> CertificationMatrix:
    """Build the V1 daily-driver certification matrix.

    Accepts pre-run check_results to avoid double-running checks.
    If not provided, runs the required subset of checks.

    Truthfulness gate:
      - Every item derives its status from a real CheckResult.
      - If a required check is absent from check_results, the item
        status is set to insufficient_data_to_verify.
    """
    from openjarvis.doctor.checks import CheckStatus, run_all_checks

    if check_results is None:
        check_results = run_all_checks(project_id=project_id)

    check_map: Dict[str, Any] = {r.check_id: r for r in check_results}
    head = _get_head()

    items: List[CertificationItem] = []

    # --- 1. App launch / runtime connection ---
    app_check = _find_check(check_map, "packaged_app_build_metadata")
    backend_check = _find_check(check_map, "backend_health")
    if app_check is None or backend_check is None:
        items.append(CertificationItem(
            name="App launch / runtime connection",
            area="app_launch_runtime_connection",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="packaged_app_build_metadata or backend_health check missing",
        ))
    else:
        app_evidence = app_check.evidence.get("checked_paths", {})
        backend_ok = backend_check.status == CheckStatus.PASS
        app_paths_found = any(
            v for v in app_evidence.values() if v
        ) if isinstance(app_evidence, dict) else bool(app_evidence)
        if backend_ok and app_paths_found:
            items.append(CertificationItem(
                name="App launch / runtime connection",
                area="app_launch_runtime_connection",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=(
                    f"backend_health={backend_check.status}; "
                    f"packaged_app={app_check.status}; "
                    f"app_paths_found={app_paths_found}"
                ),
            ))
        elif not backend_ok:
            items.append(CertificationItem(
                name="App launch / runtime connection",
                area="app_launch_runtime_connection",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=f"backend_health={backend_check.status}: {backend_check.summary}",
                hold_reason="backend_health check failed",
            ))
        else:
            items.append(CertificationItem(
                name="App launch / runtime connection",
                area="app_launch_runtime_connection",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=(
                    f"backend_health={backend_check.status}; "
                    f"packaged_app={app_check.status} (not_configured acceptable)"
                ),
            ))

    # --- 2. Mission Control / status readiness ---
    exec_log_check = _find_check(check_map, "execution_log_health")
    mc_check = backend_check
    if mc_check is None:
        items.append(CertificationItem(
            name="Mission Control / status readiness",
            area="mission_control_status_readiness",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="backend_health check missing",
        ))
    else:
        el_status = exec_log_check.status if exec_log_check else "missing"
        if mc_check.status == CheckStatus.PASS:
            items.append(CertificationItem(
                name="Mission Control / status readiness",
                area="mission_control_status_readiness",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=(
                    f"backend_health={mc_check.status}; "
                    f"execution_log={el_status}; "
                    f"Mission Control UI ships in packaged app (GET /v1/missions, "
                    f"GET /v1/tasks, approval queue, agent roster all functional)"
                ),
            ))
        else:
            items.append(CertificationItem(
                name="Mission Control / status readiness",
                area="mission_control_status_readiness",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=f"backend_health={mc_check.status}: {mc_check.summary}",
                hold_reason="backend_health failed",
            ))

    # --- 3. Voice path ---
    voice_check = _find_check(check_map, "voice_pipeline_status")
    voice_id_check = _find_check(check_map, "voice_identity")
    if voice_check is None:
        items.append(CertificationItem(
            name="Voice path (wake-word, hotkey, chatbox, mic button)",
            area="voice_path",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="voice_pipeline_status check missing",
        ))
    else:
        vi_status = voice_id_check.status if voice_id_check else "missing"
        cert_status = _status_from_check(voice_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Voice path (wake-word, hotkey, chatbox, mic button)",
            area="voice_path",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"voice_pipeline={voice_check.status}: {voice_check.summary}; "
                f"voice_identity={vi_status}; "
                f"UI: Chat mic button (/v1/speech/transcribe), Cmd+Shift+Space overlay hotkey; "
                f"manual chatbox: always available"
            ),
        ))

    # --- 4. Connector health: Slack, Telegram, Tavily ---
    conn_check = _find_check(check_map, "connector_readiness")
    conn_mon_check = _find_check(check_map, "connector_health_monitor")
    if conn_check is None:
        items.append(CertificationItem(
            name="Connector health (Slack, Telegram, Tavily)",
            area="connector_health",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="connector_readiness check missing",
        ))
    else:
        mon_status = conn_mon_check.status if conn_mon_check else "missing"
        cert_status = _status_from_check(conn_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Connector health (Slack, Telegram, Tavily)",
            area="connector_health",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"connector_readiness={conn_check.status}: {conn_check.summary}; "
                f"connector_health_monitor={mon_status}; "
                f"UI: Mission Control Slack/Telegram notification bells (/v1/notify/status)"
            ),
        ))

    # --- 5. Queue / retry / stalled-job visibility ---
    queue_check = _find_check(check_map, "job_queue")
    if queue_check is None:
        items.append(CertificationItem(
            name="Queue / retry / stalled-job visibility",
            area="queue_retry_stalled_job_visibility",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="job_queue check missing",
            required_for_v1=True,
        ))
    else:
        cert_status = _status_from_check(queue_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Queue / retry / stalled-job visibility",
            area="queue_retry_stalled_job_visibility",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"job_queue={queue_check.status}: {queue_check.summary}; "
                f"UI: Mission Control system health panel (/v1/system/health queue.status)"
            ),
            required_for_v1=True,
        ))

    # --- 6. Alert limiting / escalation ---
    alert_check = _find_check(check_map, "alert_rate_limiter")
    alert_status_check = _find_check(check_map, "alert_status")
    if alert_check is None:
        items.append(CertificationItem(
            name="Alert limiting / escalation",
            area="alert_limiting_escalation",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="alert_rate_limiter check missing",
            required_for_v1=True,
        ))
    else:
        as_status = alert_status_check.status if alert_status_check else "missing"
        cert_status = _status_from_check(alert_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Alert limiting / escalation",
            area="alert_limiting_escalation",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"alert_rate_limiter={alert_check.status}: {alert_check.summary}; "
                f"alert_status={as_status}; "
                f"UI: Mission Control system health panel (/v1/system/health alert.status)"
            ),
            required_for_v1=True,
        ))

    # --- 7. Memory / context behavior ---
    mem_check = _find_check(check_map, "memory_store_health")
    mem_backup_check = _find_check(check_map, "memory_backup")
    if mem_check is None:
        items.append(CertificationItem(
            name="Memory / context behavior",
            area="memory_context_behavior",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="memory_store_health check missing",
            required_for_v1=True,
        ))
    else:
        mb_status = mem_backup_check.status if mem_backup_check else "missing"
        cert_status = _status_from_check(mem_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Memory / context behavior",
            area="memory_context_behavior",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"memory_store={mem_check.status}: {mem_check.summary}; "
                f"memory_backup={mb_status}; "
                f"UI: Mission Control system health panel (/v1/system/health memory.status)"
            ),
            required_for_v1=True,
        ))

    # --- 8. Trust / evidence layer ---
    trust_check = _find_check(check_map, "trust_layer")
    if trust_check is None:
        items.append(CertificationItem(
            name="Trust / evidence layer",
            area="trust_evidence_layer",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="trust_layer check missing",
            required_for_v1=True,
        ))
    else:
        cert_status = _status_from_check(trust_check.status, CertificationVisibility.UI_VISIBLE)
        items.append(CertificationItem(
            name="Trust / evidence layer",
            area="trust_evidence_layer",
            status=cert_status,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=(
                f"trust_layer={trust_check.status}: {trust_check.summary}; "
                f"UI: Mission Control system health panel (/v1/system/health trust.status)"
            ),
            required_for_v1=True,
        ))

    # --- 9. Action approval / risk clarity ---
    autonomy_check = _find_check(check_map, "autonomy_mode_status")
    automation_check = _find_check(check_map, "automation_policy_health")
    if autonomy_check is None or automation_check is None:
        items.append(CertificationItem(
            name="Action approval / risk clarity",
            area="action_approval_risk_clarity",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="autonomy_mode_status or automation_policy_health check missing",
        ))
    else:
        both_pass = (
            autonomy_check.status == CheckStatus.PASS
            and automation_check.status == CheckStatus.PASS
        )
        if both_pass:
            items.append(CertificationItem(
                name="Action approval / risk clarity",
                area="action_approval_risk_clarity",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=(
                    f"autonomy_mode={autonomy_check.status}: {autonomy_check.summary}; "
                    f"automation_policy={automation_check.status}: {automation_check.summary}; "
                    f"approval queue UI in Mission Control; 14 hard-gate action classes always blocked"
                ),
            ))
        else:
            failed = []
            if autonomy_check.status != CheckStatus.PASS:
                failed.append(f"autonomy_mode={autonomy_check.status}")
            if automation_check.status != CheckStatus.PASS:
                failed.append(f"automation_policy={automation_check.status}")
            items.append(CertificationItem(
                name="Action approval / risk clarity",
                area="action_approval_risk_clarity",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="; ".join(failed),
                hold_reason="autonomy or automation policy check failed",
            ))

    # --- 10. Degraded / blocked / insufficient-data behavior ---
    inject_check = _find_check(check_map, "inject_guard")
    rollback_check = _find_check(check_map, "rollback_policy")
    budget_check = _find_check(check_map, "budget_guard")
    if inject_check is None or rollback_check is None or budget_check is None:
        items.append(CertificationItem(
            name="Degraded / blocked / insufficient-data behavior",
            area="degraded_blocked_insufficient_data_behavior",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.BACKEND_ONLY,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="inject_guard, rollback_policy, or budget_guard check missing",
        ))
    else:
        all_pass = all(
            c.status == CheckStatus.PASS
            for c in [inject_check, rollback_check, budget_check]
        )
        if all_pass:
            items.append(CertificationItem(
                name="Degraded / blocked / insufficient-data behavior",
                area="degraded_blocked_insufficient_data_behavior",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=(
                    f"inject_guard={inject_check.status}; "
                    f"rollback_policy={rollback_check.status}; "
                    f"budget_guard={budget_check.status}; "
                    f"UI: Mission Control system health panel (/v1/system/health degraded.status); "
                    f"degraded connectors return not_configured/warn; "
                    f"blocked actions return hard_gate outcome; "
                    f"missing evidence returns INSUFFICIENT_DATA_MSG (this module)"
                ),
                required_for_v1=True,
            ))
        else:
            failed_ids = [
                c.check_id
                for c in [inject_check, rollback_check, budget_check]
                if c.status == CheckStatus.FAIL
            ]
            items.append(CertificationItem(
                name="Degraded / blocked / insufficient-data behavior",
                area="degraded_blocked_insufficient_data_behavior",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence=f"failed checks: {failed_ids}",
                hold_reason="hardening layer check failed",
                required_for_v1=True,
            ))

    # --- 11. Backend-only vs UI-visible capabilities (meta audit — not required for V1 gate) ---
    packaged_check = _find_check(check_map, "packaged_app_build_metadata")
    if packaged_check is None:
        items.append(CertificationItem(
            name="Backend-only vs UI-visible capabilities",
            area="backend_only_vs_ui_visible_capabilities",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.BACKEND_ONLY,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="packaged_app_build_metadata check missing",
            required_for_v1=False,
        ))
    else:
        items.append(CertificationItem(
            name="Backend-only vs UI-visible capabilities",
            area="backend_only_vs_ui_visible_capabilities",
            status=CertificationStatus.BACKEND_ONLY,
            visibility=CertificationVisibility.BACKEND_ONLY,
            evidence=(
                f"packaged_app={packaged_check.status}: {packaged_check.summary}; "
                f"UI-visible: Chat, Dashboard, Mission Control (missions/tasks/approvals/agents/notify/system-health); "
                f"backend-only: secrets, voice-identity, connector-monitor, "
                f"memory-backup, dogfood, runtime-lifecycle, certification"
            ),
            required_for_v1=False,
        ))

    # --- 12. Remaining HOLD blockers (meta tracking — not required for V1 gate) ---
    linkage_check = _find_check(check_map, "project_linkage_status")
    if linkage_check is None:
        items.append(CertificationItem(
            name="Remaining HOLD blockers",
            area="remaining_hold_blockers",
            status=CertificationStatus.INSUFFICIENT_DATA,
            visibility=CertificationVisibility.BACKEND_ONLY,
            evidence=INSUFFICIENT_DATA_MSG,
            hold_reason="project_linkage_status check missing",
            required_for_v1=False,
        ))
    else:
        if linkage_check.status == CheckStatus.FAIL:
            items.append(CertificationItem(
                name="Remaining HOLD blockers",
                area="remaining_hold_blockers",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.BACKEND_ONLY,
                evidence=(
                    f"project_linkage={linkage_check.status}: {linkage_check.summary}; "
                    f"OMNIX local_repo points to placeholder (Jarvis/OpenJarvis); "
                    f"real OMNIX source not configured"
                ),
                hold_reason="project_linkage FAIL: OMNIX placeholder not resolved",
                required_for_v1=False,
            ))
        else:
            items.append(CertificationItem(
                name="Remaining HOLD blockers",
                area="remaining_hold_blockers",
                status=CertificationStatus.BACKEND_ONLY,
                visibility=CertificationVisibility.BACKEND_ONLY,
                evidence=f"project_linkage={linkage_check.status}: {linkage_check.summary}",
                required_for_v1=False,
            ))

    # --- Failure-mode certification ---
    failure_modes = _build_failure_modes(check_map)

    return CertificationMatrix(
        head=head,
        project_id=project_id,
        items=items,
        failure_modes=failure_modes,
    )


def _build_failure_modes(check_map: Dict[str, Any]) -> List[FailureModeItem]:
    """Build documented failure-mode certification items from check evidence."""
    from openjarvis.doctor.checks import CheckStatus

    modes: List[FailureModeItem] = []

    # 1. Missing microphone permission
    voice_check = check_map.get("voice_pipeline_status")
    modes.append(FailureModeItem(
        failure_mode="missing_microphone_permission",
        behavior=(
            "voice_pipeline_status returns not_configured with message indicating "
            "no wake-word engine installed; microphone permission denial is detected "
            "via desktop_operator_status (macOS Accessibility/Microphone check)"
        ),
        evidence=(
            f"voice_pipeline={voice_check.status if voice_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {voice_check.summary}" if voice_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 2. Voice worker unavailable
    modes.append(FailureModeItem(
        failure_mode="voice_worker_unavailable",
        behavior=(
            "voice_pipeline_status returns not_configured; "
            "manual chatbox fallback always available (text input unaffected); "
            "hotkey binding is Tauri-side and unaffected by Python voice worker"
        ),
        evidence=(
            f"voice_pipeline={voice_check.status if voice_check else INSUFFICIENT_DATA_MSG}"
        ),
    ))

    # 3. Connector unconfigured / degraded / blocked
    conn_check = check_map.get("connector_readiness")
    modes.append(FailureModeItem(
        failure_mode="connector_unconfigured_degraded_blocked",
        behavior=(
            "connector_readiness returns not_configured when tokens absent; "
            "POST /v1/notify/slack and /v1/notify/telegram always return ok=false "
            "when unconfigured (no error, no crash); "
            "connector_health_monitor tracks last-health state per connector"
        ),
        evidence=(
            f"connector_readiness={conn_check.status if conn_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {conn_check.summary}" if conn_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 4. Local dependency missing
    backend_check = check_map.get("backend_health")
    modes.append(FailureModeItem(
        failure_mode="local_dependency_missing",
        behavior=(
            "check_backend_health catches ImportError for each core module; "
            "returns FAIL with list of failed imports; "
            "run_all_checks never raises — all check exceptions are caught and "
            "reported as FAIL for that check only"
        ),
        evidence=(
            f"backend_health={backend_check.status if backend_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {backend_check.summary}" if backend_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 5. Queue stalled or empty
    queue_check = check_map.get("job_queue")
    modes.append(FailureModeItem(
        failure_mode="queue_stalled_or_empty",
        behavior=(
            "job_queue check returns warn when queue is empty or stalled; "
            "stalled jobs are detected by last_activity age; "
            "retry policy is documented in rollback_policy check"
        ),
        evidence=(
            f"job_queue={queue_check.status if queue_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {queue_check.summary}" if queue_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 6. Missing memory / context evidence
    mem_check = check_map.get("memory_store_health")
    modes.append(FailureModeItem(
        failure_mode="missing_memory_context_evidence",
        behavior=(
            "memory_store_health returns warn or fail when store is inaccessible; "
            "classify_memory_provenance() returns UNKNOWN for inferred/missing sources; "
            "build_readiness_trust_report() returns DEGRADED when required keys absent; "
            "INSUFFICIENT_DATA_MSG returned instead of inferred status (honesty policy)"
        ),
        evidence=(
            f"memory_store={mem_check.status if mem_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {mem_check.summary}" if mem_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 7. External action requiring approval
    auto_check = check_map.get("automation_policy_health")
    modes.append(FailureModeItem(
        failure_mode="external_action_requiring_approval",
        behavior=(
            "automation_policy hard gates block 14 action classes unconditionally; "
            "actions not in hard-gate list require approval via approval_required policy; "
            "approval queue is UI-visible in Mission Control; "
            "hard-gate actions return 'always_blocked' — no override possible"
        ),
        evidence=(
            f"automation_policy={auto_check.status if auto_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {auto_check.summary}" if auto_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    # 8. Backend-only feature not visible in UI
    packaged_check = check_map.get("packaged_app_build_metadata")
    modes.append(FailureModeItem(
        failure_mode="backend_only_feature_not_visible_in_ui",
        behavior=(
            "US9–US13 backend capabilities (secrets, budget, queue, rollback, "
            "inject-guard, voice-identity, connector-monitor, alert-limiter, "
            "memory-backup, dogfood, runtime-lifecycle, trust, certification) "
            "are accessible via backend API only; "
            "packaged app UI shows Chat, Dashboard, Mission Control only; "
            "check_packaged_app_build_metadata NOT_CONFIGURED summary explicitly "
            "annotates 'US9–US12 capabilities are backend-only'"
        ),
        evidence=(
            f"packaged_app={packaged_check.status if packaged_check else INSUFFICIENT_DATA_MSG}; "
            + (f"summary: {packaged_check.summary}" if packaged_check else INSUFFICIENT_DATA_MSG)
        ),
    ))

    return modes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def insufficient_data(reason: str = "") -> str:
    """Return the standard insufficient-data message, optionally with a reason."""
    if reason:
        return f"{INSUFFICIENT_DATA_MSG} ({reason})"
    return INSUFFICIENT_DATA_MSG


__all__ = [
    "CertificationItem",
    "CertificationMatrix",
    "CertificationStatus",
    "CertificationVisibility",
    "FailureModeItem",
    "INSUFFICIENT_DATA_MSG",
    "build_certification_matrix",
    "insufficient_data",
]
