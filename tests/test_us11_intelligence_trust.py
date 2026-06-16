"""US11 Intelligence + Trust Layer — scoped tests.

Covers all US11 scope items:
  1. Trust/evidence layer          — TrustStatus, EvidenceRecord, ReadinessTrustReport
  2. Action confidence/approval    — ActionProfile, ActionAccessType, build_action_profile
  3. Planner/self-check trust      — PreExecutionSelfCheck, PostExecutionSelfCheck
  4. Memory/context provenance     — MemoryProvenance, MemorySource, classify_memory_provenance
  5. Tool/connector intelligence   — ConnectorTrustStatus, classify_connector_trust
  6. Readiness/status integration  — check_trust_layer, TRUST_LAYER category in readiness

Rules:
  - No real subprocesses started
  - No secrets used
  - No real external sends
  - All functions are pure / no I/O
"""

from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# 1. TrustStatus constants
# ---------------------------------------------------------------------------


class TestTrustStatus:
    def test_import(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus is not None

    def test_ready_constant(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus.READY == "ready"

    def test_degraded_constant(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus.DEGRADED == "degraded"

    def test_blocked_constant(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus.BLOCKED == "blocked"

    def test_unconfigured_constant(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus.UNCONFIGURED == "unconfigured"

    def test_unknown_constant(self):
        from openjarvis.intelligence.trust import TrustStatus
        assert TrustStatus.UNKNOWN == "unknown"

    def test_five_distinct_values(self):
        from openjarvis.intelligence.trust import TrustStatus
        vals = {
            TrustStatus.READY,
            TrustStatus.DEGRADED,
            TrustStatus.BLOCKED,
            TrustStatus.UNCONFIGURED,
            TrustStatus.UNKNOWN,
        }
        assert len(vals) == 5


# ---------------------------------------------------------------------------
# 2. insufficient_data + INSUFFICIENT_DATA_MSG
# ---------------------------------------------------------------------------


class TestInsufficientData:
    def test_no_context_returns_base_msg(self):
        from openjarvis.intelligence.trust import insufficient_data, INSUFFICIENT_DATA_MSG
        result = insufficient_data()
        assert INSUFFICIENT_DATA_MSG in result

    def test_with_context_includes_context(self):
        from openjarvis.intelligence.trust import insufficient_data
        result = insufficient_data("connector=slack")
        assert "connector=slack" in result
        assert "insufficient_data_to_verify" in result

    def test_constant_is_string(self):
        from openjarvis.intelligence.trust import INSUFFICIENT_DATA_MSG
        assert isinstance(INSUFFICIENT_DATA_MSG, str)
        assert len(INSUFFICIENT_DATA_MSG) > 0


# ---------------------------------------------------------------------------
# 3. EvidenceRecord
# ---------------------------------------------------------------------------


class TestEvidenceRecord:
    def test_import(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        assert EvidenceRecord is not None

    def test_creation_with_required_fields(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="test_source", reason="probe passed")
        assert er.source == "test_source"
        assert er.reason == "probe passed"

    def test_is_verified_true_when_source_reason_present(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="runtime", reason="import ok")
        assert er.is_verified() is True

    def test_is_verified_false_when_source_missing(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="", reason="probe passed")
        assert er.is_verified() is False

    def test_is_verified_false_when_reason_missing(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="runtime", reason="")
        assert er.is_verified() is False

    def test_is_verified_false_when_recency_not_ok(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="runtime", reason="stale", recency_ok=False)
        assert er.is_verified() is False

    def test_to_dict_has_required_fields(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="src", reason="rsn", value=42)
        d = er.to_dict()
        assert "source" in d
        assert "reason" in d
        assert "timestamp" in d
        assert "value" in d
        assert "recency_ok" in d
        assert "is_verified" in d

    def test_to_dict_value_correct(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="s", reason="r", value={"key": "val"})
        d = er.to_dict()
        assert d["value"] == {"key": "val"}

    def test_to_dict_binary_value_redacted(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="s", reason="r", value=b"secret_bytes")
        d = er.to_dict()
        assert d["value"] == "<binary>"

    def test_timestamp_defaults_to_recent(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        before = time.time()
        er = EvidenceRecord(source="s", reason="r")
        after = time.time()
        assert er.timestamp is not None
        assert before <= er.timestamp <= after

    def test_timestamp_can_be_none(self):
        from openjarvis.intelligence.trust import EvidenceRecord
        er = EvidenceRecord(source="s", reason="r", timestamp=None)
        assert er.timestamp is None


# ---------------------------------------------------------------------------
# 4. MemorySource + MemoryProvenance
# ---------------------------------------------------------------------------


class TestMemorySource:
    def test_constants_defined(self):
        from openjarvis.intelligence.trust import MemorySource
        assert MemorySource.DURABLE == "durable"
        assert MemorySource.SESSION == "session"
        assert MemorySource.RUNTIME == "runtime"
        assert MemorySource.FALLBACK == "fallback"
        assert MemorySource.MISSING == "missing"

    def test_five_distinct_values(self):
        from openjarvis.intelligence.trust import MemorySource
        vals = {
            MemorySource.DURABLE,
            MemorySource.SESSION,
            MemorySource.RUNTIME,
            MemorySource.FALLBACK,
            MemorySource.MISSING,
        }
        assert len(vals) == 5


class TestMemoryProvenance:
    def test_import(self):
        from openjarvis.intelligence.trust import MemoryProvenance
        assert MemoryProvenance is not None

    def test_creation(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.DURABLE,
            namespace="project:omnix",
            recency=time.time(),
            trust_status=TrustStatus.READY,
        )
        assert mp.source_type == "durable"
        assert mp.namespace == "project:omnix"
        assert mp.trust_status == TrustStatus.READY

    def test_is_trusted_true_durable_ready(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.DURABLE,
            namespace="ns",
            recency=time.time(),
            trust_status=TrustStatus.READY,
        )
        assert mp.is_trusted() is True

    def test_is_trusted_true_session_ready(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.SESSION,
            namespace="ns",
            recency=time.time(),
            trust_status=TrustStatus.READY,
        )
        assert mp.is_trusted() is True

    def test_is_trusted_false_missing_source(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.MISSING,
            namespace="ns",
            recency=None,
            trust_status=TrustStatus.BLOCKED,
        )
        assert mp.is_trusted() is False

    def test_is_trusted_false_degraded(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.DURABLE,
            namespace="ns",
            recency=None,
            trust_status=TrustStatus.DEGRADED,
        )
        assert mp.is_trusted() is False

    def test_to_dict_has_required_fields(self):
        from openjarvis.intelligence.trust import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.RUNTIME,
            namespace="ns",
            recency=None,
            trust_status=TrustStatus.UNKNOWN,
        )
        d = mp.to_dict()
        assert "source_type" in d
        assert "namespace" in d
        assert "recency" in d
        assert "trust_status" in d
        assert "detail" in d
        assert "is_trusted" in d


class TestClassifyMemoryProvenance:
    def test_missing_source_returns_blocked(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        mp = classify_memory_provenance("ns", MemorySource.MISSING)
        assert mp.trust_status == TrustStatus.BLOCKED

    def test_durable_recent_returns_ready(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        mp = classify_memory_provenance("ns", MemorySource.DURABLE, recency=time.time())
        assert mp.trust_status == TrustStatus.READY

    def test_durable_no_recency_returns_degraded(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        mp = classify_memory_provenance("ns", MemorySource.DURABLE, recency=None)
        assert mp.trust_status == TrustStatus.DEGRADED

    def test_durable_stale_returns_degraded(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        stale_time = time.time() - 7200
        mp = classify_memory_provenance("ns", MemorySource.DURABLE, recency=stale_time, max_age_seconds=3600)
        assert mp.trust_status == TrustStatus.DEGRADED

    def test_session_recent_returns_ready(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        mp = classify_memory_provenance("ns", MemorySource.SESSION, recency=time.time())
        assert mp.trust_status == TrustStatus.READY

    def test_fallback_returns_degraded(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource, TrustStatus
        mp = classify_memory_provenance("ns", MemorySource.FALLBACK)
        assert mp.trust_status == TrustStatus.DEGRADED

    def test_unknown_source_returns_unknown(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, TrustStatus
        mp = classify_memory_provenance("ns", "exotic_source_xyz")
        assert mp.trust_status == TrustStatus.UNKNOWN

    def test_missing_source_detail_contains_insufficient_data(self):
        from openjarvis.intelligence.trust import classify_memory_provenance, MemorySource
        mp = classify_memory_provenance("project:omnix", MemorySource.MISSING)
        assert "insufficient_data_to_verify" in mp.detail


# ---------------------------------------------------------------------------
# 5. ActionAccessType + ActionProfile
# ---------------------------------------------------------------------------


class TestActionAccessType:
    def test_constants_defined(self):
        from openjarvis.intelligence.trust import ActionAccessType
        assert ActionAccessType.READ_ONLY == "read_only"
        assert ActionAccessType.LOCAL_WRITE == "local_write"
        assert ActionAccessType.EXTERNAL_WRITE == "external_write"
        assert ActionAccessType.DESTRUCTIVE == "destructive"
        assert ActionAccessType.CREDENTIAL_SENSITIVE == "credential_sensitive"

    def test_five_distinct_values(self):
        from openjarvis.intelligence.trust import ActionAccessType
        vals = {
            ActionAccessType.READ_ONLY,
            ActionAccessType.LOCAL_WRITE,
            ActionAccessType.EXTERNAL_WRITE,
            ActionAccessType.DESTRUCTIVE,
            ActionAccessType.CREDENTIAL_SENSITIVE,
        }
        assert len(vals) == 5


class TestActionProfile:
    def test_import(self):
        from openjarvis.intelligence.trust import ActionProfile
        assert ActionProfile is not None

    def test_creation_minimal(self):
        from openjarvis.intelligence.trust import ActionProfile, ActionAccessType
        ap = ActionProfile(
            action_id="mission.list",
            access_type=ActionAccessType.READ_ONLY,
            risk_level="low",
            required_approval=False,
            expected_side_effect="reads mission list from store",
        )
        assert ap.action_id == "mission.list"
        assert ap.access_type == "read_only"
        assert ap.required_approval is False
        assert ap.touches_external() is False

    def test_creation_with_external_services(self):
        from openjarvis.intelligence.trust import ActionProfile, ActionAccessType
        ap = ActionProfile(
            action_id="notify.slack",
            access_type=ActionAccessType.EXTERNAL_WRITE,
            risk_level="high",
            required_approval=True,
            expected_side_effect="sends message to Slack channel",
            external_services=["slack"],
        )
        assert ap.touches_external() is True
        assert "slack" in ap.external_services

    def test_is_hard_gate_false_by_default(self):
        from openjarvis.intelligence.trust import ActionProfile, ActionAccessType
        ap = ActionProfile(
            action_id="read.logs",
            access_type=ActionAccessType.READ_ONLY,
            risk_level="low",
            required_approval=False,
            expected_side_effect="reads logs",
        )
        assert ap.is_hard_gate is False

    def test_to_dict_has_required_fields(self):
        from openjarvis.intelligence.trust import ActionProfile, ActionAccessType
        ap = ActionProfile(
            action_id="test.action",
            access_type=ActionAccessType.LOCAL_WRITE,
            risk_level="medium",
            required_approval=False,
            expected_side_effect="writes local file",
        )
        d = ap.to_dict()
        assert "action_id" in d
        assert "access_type" in d
        assert "risk_level" in d
        assert "required_approval" in d
        assert "expected_side_effect" in d
        assert "external_services" in d
        assert "is_hard_gate" in d
        assert "touches_external" in d
        assert "evidence" in d


class TestBuildActionProfile:
    def test_hard_gate_action_sets_required_approval(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "real_slack_send",
            ActionAccessType.EXTERNAL_WRITE,
            "high",
            "sends real message to Slack",
            external_services=["slack"],
        )
        assert ap.required_approval is True
        assert ap.is_hard_gate is True

    def test_read_only_low_risk_no_approval_needed(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "mission.list",
            ActionAccessType.READ_ONLY,
            "low",
            "lists missions from store",
        )
        assert ap.required_approval is False
        assert ap.is_hard_gate is False

    def test_high_risk_requires_approval(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "some_local_action",
            ActionAccessType.LOCAL_WRITE,
            "high",
            "writes critical config",
        )
        assert ap.required_approval is True

    def test_destructive_access_type_is_hard_gate(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "delete_data",
            ActionAccessType.DESTRUCTIVE,
            "critical",
            "deletes all user data",
        )
        assert ap.is_hard_gate is True
        assert ap.required_approval is True

    def test_external_write_requires_approval(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "webhook.send",
            ActionAccessType.EXTERNAL_WRITE,
            "medium",
            "sends data to external webhook",
            external_services=["webhook"],
        )
        assert ap.required_approval is True

    def test_credential_sensitive_requires_approval(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "key.rotate",
            ActionAccessType.CREDENTIAL_SENSITIVE,
            "medium",
            "rotates API key",
        )
        assert ap.required_approval is True

    def test_evidence_list_nonempty(self):
        from openjarvis.intelligence.trust import build_action_profile, ActionAccessType
        ap = build_action_profile(
            "mission.list",
            ActionAccessType.READ_ONLY,
            "low",
            "lists missions",
        )
        assert len(ap.evidence) >= 1
        assert ap.evidence[0].source != ""


# ---------------------------------------------------------------------------
# 6. ConnectorTrustStatus + classify_connector_trust
# ---------------------------------------------------------------------------


class TestConnectorTrustStatus:
    def test_import(self):
        from openjarvis.intelligence.trust import ConnectorTrustStatus
        assert ConnectorTrustStatus is not None

    def test_creation(self):
        from openjarvis.intelligence.trust import ConnectorTrustStatus, TrustStatus
        cts = ConnectorTrustStatus(
            connector_id="slack",
            trust_status=TrustStatus.READY,
            reason="health ok",
            safe_fallback="log_and_skip",
        )
        assert cts.connector_id == "slack"
        assert cts.is_usable() is True

    def test_is_usable_false_when_degraded(self):
        from openjarvis.intelligence.trust import ConnectorTrustStatus, TrustStatus
        cts = ConnectorTrustStatus(
            connector_id="slack",
            trust_status=TrustStatus.DEGRADED,
            reason="health probe failed",
            safe_fallback="log_and_skip",
        )
        assert cts.is_usable() is False

    def test_to_dict_has_required_fields(self):
        from openjarvis.intelligence.trust import ConnectorTrustStatus, TrustStatus
        cts = ConnectorTrustStatus(
            connector_id="telegram",
            trust_status=TrustStatus.UNCONFIGURED,
            reason="not configured",
            safe_fallback="skip",
        )
        d = cts.to_dict()
        assert "connector_id" in d
        assert "trust_status" in d
        assert "reason" in d
        assert "safe_fallback" in d
        assert "is_usable" in d
        assert "evidence" in d


class TestClassifyConnectorTrust:
    def test_not_configured_returns_unconfigured(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=False, last_health_ok=None)
        assert cts.trust_status == TrustStatus.UNCONFIGURED

    def test_not_configured_reason_contains_insufficient_data(self):
        from openjarvis.intelligence.trust import classify_connector_trust
        cts = classify_connector_trust("slack", configured=False, last_health_ok=None)
        assert "insufficient_data_to_verify" in cts.reason

    def test_configured_health_ok_returns_ready(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=True)
        assert cts.trust_status == TrustStatus.READY
        assert cts.is_usable() is True

    def test_configured_health_fail_returns_degraded(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=False, error_reason="timeout")
        assert cts.trust_status == TrustStatus.DEGRADED
        assert "timeout" in cts.reason

    def test_configured_no_health_probe_returns_unknown(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=None)
        assert cts.trust_status == TrustStatus.UNKNOWN

    def test_evidence_present_when_configured(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=True)
        assert cts.evidence is not None
        assert cts.evidence.source == "health_probe"

    def test_evidence_present_when_not_configured(self):
        from openjarvis.intelligence.trust import classify_connector_trust
        cts = classify_connector_trust("slack", configured=False, last_health_ok=None)
        assert cts.evidence is not None
        assert cts.evidence.source == "config_check"

    def test_evidence_none_when_unknown(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=None)
        assert cts.evidence is None

    def test_custom_safe_fallback(self):
        from openjarvis.intelligence.trust import classify_connector_trust
        cts = classify_connector_trust(
            "github", configured=False, last_health_ok=None, safe_fallback="use_local_cache"
        )
        assert cts.safe_fallback == "use_local_cache"

    def test_degraded_evidence_recency_not_ok(self):
        from openjarvis.intelligence.trust import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=False)
        assert cts.evidence is not None
        assert cts.evidence.recency_ok is False


# ---------------------------------------------------------------------------
# 7. ReadinessTrustReport
# ---------------------------------------------------------------------------


class TestReadinessTrustReport:
    def test_import(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport
        assert ReadinessTrustReport is not None

    def test_is_sufficient_true_when_ready_and_evidence_and_no_missing(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, EvidenceRecord, TrustStatus
        rtr = ReadinessTrustReport(
            subject="test",
            trust_status=TrustStatus.READY,
            evidence=[EvidenceRecord(source="s", reason="r")],
            missing_evidence=[],
        )
        assert rtr.is_sufficient is True

    def test_is_sufficient_false_when_missing_evidence(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, EvidenceRecord, TrustStatus
        rtr = ReadinessTrustReport(
            subject="test",
            trust_status=TrustStatus.READY,
            evidence=[EvidenceRecord(source="s", reason="r")],
            missing_evidence=["key_a"],
        )
        assert rtr.is_sufficient is False

    def test_is_sufficient_false_when_no_evidence(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, TrustStatus
        rtr = ReadinessTrustReport(
            subject="test",
            trust_status=TrustStatus.READY,
            evidence=[],
            missing_evidence=[],
        )
        assert rtr.is_sufficient is False

    def test_is_sufficient_false_when_degraded(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, EvidenceRecord, TrustStatus
        rtr = ReadinessTrustReport(
            subject="test",
            trust_status=TrustStatus.DEGRADED,
            evidence=[EvidenceRecord(source="s", reason="r")],
            missing_evidence=[],
        )
        assert rtr.is_sufficient is False

    def test_to_dict_has_required_fields(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, TrustStatus
        rtr = ReadinessTrustReport(
            subject="omnix_readiness",
            trust_status=TrustStatus.READY,
            evidence=[],
            missing_evidence=[],
        )
        d = rtr.to_dict()
        assert "subject" in d
        assert "trust_status" in d
        assert "evidence" in d
        assert "missing_evidence" in d
        assert "evaluated_at" in d
        assert "is_sufficient" in d

    def test_evaluated_at_is_recent(self):
        from openjarvis.intelligence.trust import ReadinessTrustReport, TrustStatus
        before = time.time()
        rtr = ReadinessTrustReport(
            subject="test", trust_status=TrustStatus.READY, evidence=[], missing_evidence=[]
        )
        after = time.time()
        assert before <= rtr.evaluated_at <= after


class TestBuildReadinessTrustReport:
    def test_all_required_keys_present_returns_ready(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report, TrustStatus
        rtr = build_readiness_trust_report(
            "my_subject",
            {"k1": "v1", "k2": True, "k3": 42},
            ["k1", "k2", "k3"],
        )
        assert rtr.trust_status == TrustStatus.READY
        assert rtr.is_sufficient is True
        assert rtr.missing_evidence == []

    def test_some_keys_missing_returns_degraded(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report, TrustStatus
        rtr = build_readiness_trust_report(
            "my_subject",
            {"k1": "v1"},
            ["k1", "k2"],
        )
        assert rtr.trust_status == TrustStatus.DEGRADED
        assert "k2" in rtr.missing_evidence
        assert rtr.is_sufficient is False

    def test_all_keys_missing_returns_blocked(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report, TrustStatus
        rtr = build_readiness_trust_report(
            "my_subject",
            {},
            ["k1", "k2"],
        )
        assert rtr.trust_status == TrustStatus.BLOCKED
        assert "k1" in rtr.missing_evidence
        assert "k2" in rtr.missing_evidence

    def test_empty_required_keys_returns_unknown(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report, TrustStatus
        rtr = build_readiness_trust_report("my_subject", {}, [])
        assert rtr.trust_status == TrustStatus.UNKNOWN

    def test_falsy_values_treated_as_missing(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report, TrustStatus
        rtr = build_readiness_trust_report(
            "my_subject",
            {"k1": "", "k2": None, "k3": False},
            ["k1", "k2", "k3"],
        )
        assert rtr.trust_status == TrustStatus.BLOCKED
        assert len(rtr.missing_evidence) == 3

    def test_evidence_list_has_one_entry_per_present_key(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report
        rtr = build_readiness_trust_report(
            "subj",
            {"k1": "v1", "k2": "v2"},
            ["k1", "k2"],
        )
        assert len(rtr.evidence) == 2

    def test_subject_propagated(self):
        from openjarvis.intelligence.trust import build_readiness_trust_report
        rtr = build_readiness_trust_report("runtime_check", {"x": 1}, ["x"])
        assert rtr.subject == "runtime_check"


# ---------------------------------------------------------------------------
# 8. PreExecutionSelfCheck
# ---------------------------------------------------------------------------


class TestPreExecutionSelfCheck:
    def test_import(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        assert PreExecutionSelfCheck is not None

    def test_all_keys_present_returns_ok_true(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(
            ["key_a", "key_b"],
            {"key_a": "value", "key_b": True},
        )
        assert result["ok"] is True
        assert result["verdict"] == "ACCEPT"
        assert result["missing"] == []

    def test_missing_key_returns_ok_false(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(
            ["key_a", "key_b"],
            {"key_a": "value"},
        )
        assert result["ok"] is False
        assert result["verdict"] == "HOLD"
        assert "key_b" in result["missing"]

    def test_falsy_value_counted_as_missing(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(
            ["key_a"],
            {"key_a": ""},
        )
        assert result["ok"] is False
        assert "key_a" in result["missing"]

    def test_none_value_counted_as_missing(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(
            ["key_a"],
            {"key_a": None},
        )
        assert result["ok"] is False

    def test_empty_required_keys_returns_ok_true(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check([], {})
        assert result["ok"] is True

    def test_reason_contains_insufficient_data_when_missing(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(["key_x"], {})
        assert "insufficient_data_to_verify" in result["reason"]

    def test_multiple_missing_keys_all_reported(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(
            ["a", "b", "c"],
            {"a": "present"},
        )
        assert "b" in result["missing"]
        assert "c" in result["missing"]


# ---------------------------------------------------------------------------
# 9. PostExecutionSelfCheck — anti-fake-completion
# ---------------------------------------------------------------------------


class TestPostExecutionSelfCheck:
    def test_import(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        assert PostExecutionSelfCheck is not None

    def test_none_output_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(None)
        assert result["ok"] is False

    def test_empty_string_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check("")
        assert result["ok"] is False

    def test_whitespace_string_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check("   \n\t  ")
        assert result["ok"] is False

    def test_real_string_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check("Mission completed successfully.")
        assert result["ok"] is True

    def test_empty_dict_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check({})
        assert result["ok"] is False

    def test_nonempty_dict_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check({"status": "done", "output": "data"})
        assert result["ok"] is True

    def test_dict_missing_required_fields_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(
            {"status": "done"},
            required_fields=["status", "output"],
        )
        assert result["ok"] is False
        assert "output" in result["reason"]

    def test_dict_with_all_required_fields_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(
            {"status": "done", "output": "data"},
            required_fields=["status", "output"],
        )
        assert result["ok"] is True

    def test_empty_list_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check([])
        assert result["ok"] is False

    def test_nonempty_list_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(["item1", "item2"])
        assert result["ok"] is True

    def test_empty_tuple_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(())
        assert result["ok"] is False

    def test_nonempty_tuple_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check((1, 2, 3))
        assert result["ok"] is True

    def test_falsy_int_rejected(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(0)
        assert result["ok"] is False

    def test_truthy_int_accepted(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(42)
        assert result["ok"] is True

    def test_reason_always_present(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        for output in [None, "", {}, [], "real"]:
            result = PostExecutionSelfCheck.check(output)
            assert "reason" in result
            assert isinstance(result["reason"], str)


# ---------------------------------------------------------------------------
# 10. Anti-overclaim integration
# ---------------------------------------------------------------------------


class TestAntiOverclaim:
    """Verify that pre+post checks together prevent fake completion claims."""

    def test_pre_check_blocks_when_no_evidence(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        required = ["tool_loaded", "auth_verified", "context_present"]
        available = {}
        result = PreExecutionSelfCheck.check(required, available)
        assert result["ok"] is False
        assert set(result["missing"]) == set(required)

    def test_post_check_blocks_empty_output(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        assert PostExecutionSelfCheck.check("")["ok"] is False
        assert PostExecutionSelfCheck.check(None)["ok"] is False
        assert PostExecutionSelfCheck.check({})["ok"] is False
        assert PostExecutionSelfCheck.check([])["ok"] is False

    def test_both_checks_pass_with_real_evidence_and_output(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck, PostExecutionSelfCheck
        pre = PreExecutionSelfCheck.check(
            ["tool_loaded", "context"],
            {"tool_loaded": True, "context": "session_123"},
        )
        assert pre["ok"] is True

        post = PostExecutionSelfCheck.check(
            {"status": "done", "result": "missions fetched"},
            required_fields=["status", "result"],
        )
        assert post["ok"] is True

    def test_governance_reason_in_rejection_message(self):
        from openjarvis.intelligence.trust import PostExecutionSelfCheck
        result = PostExecutionSelfCheck.check(None)
        assert "Governance policy" in result["reason"]

    def test_pre_check_hold_verdict_matches_governance_doc(self):
        from openjarvis.intelligence.trust import PreExecutionSelfCheck
        result = PreExecutionSelfCheck.check(["missing_key"], {})
        assert result["verdict"] == "HOLD"


# ---------------------------------------------------------------------------
# 11. check_trust_layer (doctor integration)
# ---------------------------------------------------------------------------


class TestCheckTrustLayer:
    def test_import(self):
        from openjarvis.doctor.checks import check_trust_layer
        assert check_trust_layer is not None

    def test_returns_check_result(self):
        from openjarvis.doctor.checks import check_trust_layer, CheckResult
        result = check_trust_layer("omnix")
        assert isinstance(result, CheckResult)

    def test_check_id_is_trust_layer(self):
        from openjarvis.doctor.checks import check_trust_layer
        result = check_trust_layer("omnix")
        assert result.check_id == "trust_layer"

    def test_status_is_pass(self):
        from openjarvis.doctor.checks import check_trust_layer, CheckStatus
        result = check_trust_layer("omnix")
        assert result.status == CheckStatus.PASS, (
            f"check_trust_layer failed: {result.summary}\nevidence: {result.evidence}"
        )

    def test_evidence_contains_trust_module_import(self):
        from openjarvis.doctor.checks import check_trust_layer
        result = check_trust_layer("omnix")
        assert "trust_module_import" in result.evidence
        assert result.evidence["trust_module_import"] == "ok"

    def test_evidence_contains_all_probes(self):
        from openjarvis.doctor.checks import check_trust_layer
        result = check_trust_layer("omnix")
        ev = result.evidence
        assert ev.get("trust_status_constants") == "ok"
        assert ev.get("evidence_record") == "ok"
        assert ev.get("memory_provenance") == "ok"
        assert ev.get("classify_connector_trust") == "ok"
        assert ev.get("pre_execution_self_check") == "ok"
        assert ev.get("post_execution_self_check") == "ok"
        assert ev.get("build_readiness_trust_report") == "ok"
        assert ev.get("insufficient_data_fn") == "ok"

    def test_project_id_propagated(self):
        from openjarvis.doctor.checks import check_trust_layer
        result = check_trust_layer("omnix")
        assert result.project_id == "omnix"

    def test_in_all_check_fns(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS, check_trust_layer
        assert check_trust_layer in _ALL_CHECK_FNS

    def test_in_run_all_checks_output(self):
        from openjarvis.doctor.checks import run_all_checks
        results = run_all_checks(project_id="omnix")
        ids = [r.check_id for r in results]
        assert "trust_layer" in ids


# ---------------------------------------------------------------------------
# 12. Readiness integration — TRUST_LAYER category
# ---------------------------------------------------------------------------


class TestReadinessTrustLayerCategory:
    @pytest.fixture(autouse=True)
    def reset_registries(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        from openjarvis.skills.jarvis_registry import SkillRegistry
        from openjarvis.autonomy.modes import AutonomyPolicy
        from openjarvis.projects.source_links import ProjectSourceRegistry

        ToolRegistry.clear()
        SkillRegistry.clear()
        AutonomyPolicy.clear()
        ProjectSourceRegistry.clear()
        yield
        ToolRegistry.clear()
        SkillRegistry.clear()
        AutonomyPolicy.clear()
        ProjectSourceRegistry.clear()

    def test_trust_layer_category_constant_exists(self):
        from openjarvis.doctor.readiness import ReadinessCategory
        assert ReadinessCategory.TRUST_LAYER == "trust_layer"

    def test_trust_layer_in_category_checks(self):
        from openjarvis.doctor.readiness import _CATEGORY_CHECKS, ReadinessCategory
        assert ReadinessCategory.TRUST_LAYER in _CATEGORY_CHECKS
        assert "trust_layer" in _CATEGORY_CHECKS[ReadinessCategory.TRUST_LAYER]

    def test_evaluate_readiness_has_28_categories(self, monkeypatch):
        monkeypatch.setenv("JARVIS_PROJECT_OMNIX_REPO_PATH", "/Users/user/OpenJarvis")
        from openjarvis.doctor.readiness import evaluate_readiness
        report = evaluate_readiness(project_id="omnix")
        assert len(report.categories) == 28

    def test_trust_layer_category_present_in_report(self, monkeypatch):
        monkeypatch.setenv("JARVIS_PROJECT_OMNIX_REPO_PATH", "/Users/user/OpenJarvis")
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        report = evaluate_readiness(project_id="omnix")
        cat_names = [c.category for c in report.categories]
        assert ReadinessCategory.TRUST_LAYER in cat_names

    def test_trust_layer_category_passes(self, monkeypatch):
        monkeypatch.setenv("JARVIS_PROJECT_OMNIX_REPO_PATH", "/Users/user/OpenJarvis")
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        from openjarvis.doctor.checks import CheckStatus
        report = evaluate_readiness(project_id="omnix")
        trust_cat = next(c for c in report.categories if c.category == ReadinessCategory.TRUST_LAYER)
        assert trust_cat.status == CheckStatus.PASS, (
            f"TRUST_LAYER category did not pass: {trust_cat.summary}"
        )

    def test_trust_layer_is_required_category(self):
        from openjarvis.doctor.readiness import _REQUIRED_CATEGORIES, ReadinessCategory
        assert ReadinessCategory.TRUST_LAYER in _REQUIRED_CATEGORIES

    def test_us11_checkpoint_in_accepted_checkpoints(self):
        from openjarvis.doctor.readiness import _ACCEPTED_CHECKPOINTS
        combined = "\n".join(_ACCEPTED_CHECKPOINTS)
        assert "Sprint 11" in combined
        assert "Trust Layer" in combined
        assert "ACCEPT" in combined

    def test_category_checks_has_28_entries(self):
        from openjarvis.doctor.readiness import _CATEGORY_CHECKS
        assert len(_CATEGORY_CHECKS) == 28


# ---------------------------------------------------------------------------
# 13. Intelligence __init__ exports
# ---------------------------------------------------------------------------


class TestIntelligenceInitExports:
    def test_trust_status_importable_from_intelligence(self):
        from openjarvis.intelligence import TrustStatus
        assert TrustStatus.READY == "ready"

    def test_evidence_record_importable_from_intelligence(self):
        from openjarvis.intelligence import EvidenceRecord
        er = EvidenceRecord(source="s", reason="r")
        assert er.is_verified() is True

    def test_memory_provenance_importable_from_intelligence(self):
        from openjarvis.intelligence import MemoryProvenance, MemorySource, TrustStatus
        mp = MemoryProvenance(
            source_type=MemorySource.DURABLE,
            namespace="ns",
            recency=None,
            trust_status=TrustStatus.DEGRADED,
        )
        assert mp.source_type == "durable"

    def test_pre_execution_self_check_importable(self):
        from openjarvis.intelligence import PreExecutionSelfCheck
        r = PreExecutionSelfCheck.check(["k"], {"k": "v"})
        assert r["ok"] is True

    def test_post_execution_self_check_importable(self):
        from openjarvis.intelligence import PostExecutionSelfCheck
        r = PostExecutionSelfCheck.check(None)
        assert r["ok"] is False

    def test_classify_connector_trust_importable(self):
        from openjarvis.intelligence import classify_connector_trust, TrustStatus
        cts = classify_connector_trust("slack", configured=True, last_health_ok=True)
        assert cts.trust_status == TrustStatus.READY

    def test_insufficient_data_importable(self):
        from openjarvis.intelligence import insufficient_data
        msg = insufficient_data("ctx")
        assert "insufficient_data_to_verify" in msg
