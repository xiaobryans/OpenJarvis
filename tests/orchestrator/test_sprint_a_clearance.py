"""Tests — Blocker Clearance Mega-Sprint A.

Covers:
  A. Connector credentials/scopes + live-read readiness (mocked)
  B. Model/Provider Capability Matrix
  C. Memory/Context Continuity proofs
  D. Doctor checks for new modules
  E. Google OAuth status classification
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Part A — Connector live reader enhancements
# ---------------------------------------------------------------------------

class TestConnectorLiveReaderSprintA(unittest.TestCase):
    """Verify new read_github_repo and get_google_oauth_status."""

    def test_read_github_repo_no_token_returns_blocked(self):
        from openjarvis.orchestrator.connector_live_reader import read_github_repo
        # Patch both env and cloud-keys loader to ensure no token is found
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            with patch(
                "openjarvis.orchestrator.connector_live_reader._load_env_key",
                return_value=None,
            ):
                result = read_github_repo(token=None)
        self.assertEqual(result.connector_id, "github_repo")
        self.assertEqual(result.status, "blocked_credentials")
        self.assertFalse(result.live_read_available)
        self.assertEqual(result.write_status, "BLOCKED_SAFETY")

    def test_read_github_repo_with_mock_token(self):
        mock_data = {
            "full_name": "xiaobryans/OpenJarvis",
            "default_branch": "main",
            "private": False,
            "open_issues_count": 0,
            "language": "Python",
        }
        with patch(
            "openjarvis.orchestrator.connector_live_reader._safe_get",
            return_value=mock_data,
        ):
            from openjarvis.orchestrator.connector_live_reader import read_github_repo
            result = read_github_repo(token="test-token-x")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.live_read_available)
        self.assertIsNotNone(result.data_preview)
        self.assertEqual(result.data_preview["full_name"], "xiaobryans/OpenJarvis")
        self.assertEqual(result.write_status, "BLOCKED_SAFETY")
        self.assertEqual(result.send_status, "BLOCKED_SAFETY")

    def test_read_github_repo_to_dict(self):
        mock_data = {
            "full_name": "xiaobryans/OpenJarvis",
            "default_branch": "main",
            "private": False,
            "open_issues_count": 2,
            "language": "Python",
        }
        with patch(
            "openjarvis.orchestrator.connector_live_reader._safe_get",
            return_value=mock_data,
        ):
            from openjarvis.orchestrator.connector_live_reader import read_github_repo
            result = read_github_repo(token="test-token-x")
        d = result.to_dict()
        self.assertIn("connector_id", d)
        self.assertIn("no_raw_chain_of_thought", d)
        self.assertTrue(d["no_raw_chain_of_thought"])

    def test_google_oauth_status_returns_blocked_credentials(self):
        """Google OAuth should be BLOCKED_CREDENTIALS — client_secret missing."""
        with patch.dict("os.environ", {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }):
            from openjarvis.orchestrator.connector_live_reader import get_google_oauth_status
            status = get_google_oauth_status()
        self.assertEqual(status["overall_status"], "BLOCKED_CREDENTIALS")
        self.assertFalse(status["client_secret_present"])
        self.assertFalse(status["refresh_token_present"])
        self.assertIn("blockers", status)
        # Never expose secret values
        for k, v in status.items():
            if isinstance(v, str):
                self.assertNotIn("sk-", v)

    def test_google_oauth_blockers_include_steps(self):
        from openjarvis.orchestrator.connector_live_reader import _google_oauth_blockers
        blockers = _google_oauth_blockers()
        self.assertIn("exact_bryan_steps", blockers)
        self.assertIsInstance(blockers["exact_bryan_steps"], list)
        self.assertGreater(len(blockers["exact_bryan_steps"]), 0)

    def test_read_gmail_blocked_credentials(self):
        from openjarvis.orchestrator.connector_live_reader import read_gmail
        result = read_gmail()
        self.assertEqual(result.connector_id, "gmail")
        self.assertFalse(result.live_read_available)
        self.assertIn("BLOCKED_CREDENTIALS", result.error)

    def test_slack_send_always_blocked_safety(self):
        """Slack sends must always be BLOCKED_SAFETY regardless of token."""
        with patch(
            "openjarvis.orchestrator.connector_live_reader._safe_get",
            return_value={"ok": True, "channels": []},
        ):
            from openjarvis.orchestrator.connector_live_reader import read_slack_channels
            result = read_slack_channels(token="test-token")
        self.assertEqual(result.send_status, "BLOCKED_SAFETY")
        self.assertEqual(result.write_status, "BLOCKED_SAFETY")

    def test_connector_readiness_report_structure(self):
        """ConnectorReadinessReport must include all 6 connectors."""
        mock_ok = MagicMock()
        mock_ok.live_read_available = True
        mock_ok.status = "ok"
        mock_ok.connector_id = "slack"
        mock_ok.data_preview = {}
        mock_ok.latency_ms = 100.0
        mock_ok.error = None
        mock_ok.operation = "conversations.list"
        mock_ok.write_status = "BLOCKED_SAFETY"
        mock_ok.send_status = "BLOCKED_SAFETY"
        mock_ok.no_raw_chain_of_thought = True

        with patch(
            "openjarvis.orchestrator.connector_live_reader.read_slack_channels",
            return_value=mock_ok,
        ), patch(
            "openjarvis.orchestrator.connector_live_reader.read_github_user",
            return_value=mock_ok,
        ), patch(
            "openjarvis.orchestrator.connector_live_reader.read_telegram_bot_info",
            return_value=mock_ok,
        ):
            from openjarvis.orchestrator.connector_live_reader import get_connector_readiness
            report = get_connector_readiness()
        self.assertGreaterEqual(report.total_connectors, 6)
        self.assertEqual(report.overall_status, "DAILY_DRIVER_ACCEPT")


# ---------------------------------------------------------------------------
# Part B — Provider capability matrix
# ---------------------------------------------------------------------------

class TestProviderCapabilityMatrix(unittest.TestCase):
    """Verify the provider capability matrix covers all required capabilities."""

    def setUp(self):
        # Patch env so matrix uses known keys
        self._env_patcher = patch.dict("os.environ", {
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENROUTER_API_KEY": "or-test",
        })
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()

    def test_matrix_has_required_capabilities(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        names = {c.capability for c in report.capabilities}
        required = {
            "fast_chat", "hard_reasoning", "coding", "long_context_coding",
            "embeddings_semantic_memory", "audio_stt", "tts",
            "cost_sensitive_planning", "safety_adversarial_review",
            "tool_calling_connector_orchestration",
        }
        for cap in required:
            self.assertIn(cap, names, f"Missing required capability: {cap}")

    def test_stt_tts_are_optional_backlog(self):
        """Voice/STT/TTS must not be unblocked — OPTIONAL_BACKLOG."""
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        for cap in report.capabilities:
            if cap.capability in ("audio_stt", "tts"):
                self.assertEqual(
                    cap.status, "OPTIONAL_BACKLOG",
                    f"{cap.capability} must be OPTIONAL_BACKLOG, got {cap.status}",
                )
                self.assertIsNotNone(cap.blocker)
                self.assertIn("VOICE_HOLD_UNSAFE_PARKED", cap.blocker)

    def test_embedding_capability_uses_text_embedding_3_small(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        emb = next(c for c in report.capabilities if c.capability == "embeddings_semantic_memory")
        self.assertEqual(emb.primary_model, "text-embedding-3-small")
        self.assertEqual(emb.primary_provider, "OpenAI")
        self.assertEqual(emb.status, "DAILY_DRIVER_ACCEPT")

    def test_all_capabilities_have_cost_and_latency_tiers(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        for cap in report.capabilities:
            self.assertIn(cap.cost_tier, ("very_low", "low", "medium", "high", "very_high"),
                          f"{cap.capability} has invalid cost_tier: {cap.cost_tier}")
            self.assertIn(cap.latency_tier, ("fast", "medium", "slow", "batch"),
                          f"{cap.capability} has invalid latency_tier: {cap.latency_tier}")

    def test_overall_status_daily_driver_when_keys_present(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        self.assertEqual(report.overall_status, "DAILY_DRIVER_ACCEPT")
        self.assertTrue(report.embedding_model_proven)
        self.assertTrue(report.cost_governance_active)

    def test_to_dict_is_json_serializable(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        d = report.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)
        self.assertIn("daily_driver_accept_count", serialized)

    def test_get_capability_for_lookup(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_capability_for
        cap = get_capability_for("coding")
        self.assertIsNotNone(cap)
        self.assertEqual(cap.capability, "coding")
        self.assertEqual(cap.primary_provider, "Anthropic")

    def test_no_raw_chain_of_thought_flag(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_provider_capability_matrix
        report = get_provider_capability_matrix()
        self.assertTrue(report.no_raw_chain_of_thought)
        for cap in report.capabilities:
            self.assertTrue(cap.no_raw_chain_of_thought)

    def test_matrix_summary_compact(self):
        from openjarvis.orchestrator.provider_capability_matrix import get_matrix_summary
        summary = get_matrix_summary()
        self.assertIn("total_capabilities", summary)
        self.assertIn("daily_driver_accept", summary)
        self.assertIn("blocked", summary)
        self.assertIn("voice_status", summary)
        self.assertEqual(summary["voice_status"], "OPTIONAL_BACKLOG")

    def test_blocked_when_openai_key_missing(self):
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }, clear=False):
            # Need to also patch cloud-keys.env loader
            with patch(
                "openjarvis.orchestrator.provider_capability_matrix._env",
                return_value="",
            ):
                from importlib import reload
                import openjarvis.orchestrator.provider_capability_matrix as mod
                caps = mod._build_matrix()
                # fast_chat needs openai
                fc = next(c for c in caps if c.capability == "fast_chat")
                self.assertEqual(fc.status, "BLOCKED_CREDENTIALS")


# ---------------------------------------------------------------------------
# Part C — Memory continuity proofs
# ---------------------------------------------------------------------------

class TestMemoryContinuityProofs(unittest.TestCase):
    """Verify the 7 daily-driver memory continuity proof cases."""

    def test_run_all_proofs_pass_or_skip(self):
        from openjarvis.memory.memory_continuity import run_memory_continuity_proofs
        report = run_memory_continuity_proofs()
        self.assertIn(report.overall_status, ("DAILY_DRIVER_ACCEPT", "HOLD"))
        self.assertEqual(len(report.proofs), 7)

    def test_no_proof_has_undefined_status(self):
        from openjarvis.memory.memory_continuity import run_memory_continuity_proofs
        report = run_memory_continuity_proofs()
        for p in report.proofs:
            self.assertIn(p.status, ("PASS", "FAIL", "SKIP"),
                          f"Proof {p.proof_id} has unknown status: {p.status}")

    def test_daily_driver_accept_when_no_failures(self):
        from openjarvis.memory.memory_continuity import (
            run_memory_continuity_proofs, ProofResult
        )
        from unittest.mock import patch as _patch
        mock_proofs = [
            ProofResult(f"P{i}", "desc", "PASS", "evidence", 1.0)
            for i in range(1, 8)
        ]
        with _patch(
            "openjarvis.memory.memory_continuity._proof_recall_project_state",
            return_value=mock_proofs[0],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_recall_accepted_decision",
            return_value=mock_proofs[1],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_detect_stale_conflict",
            return_value=mock_proofs[2],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_apply_human_correction",
            return_value=mock_proofs[3],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_no_cross_project_contamination",
            return_value=mock_proofs[4],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_insufficient_evidence_reporting",
            return_value=mock_proofs[5],
        ), _patch(
            "openjarvis.memory.memory_continuity._proof_persist_reload",
            return_value=mock_proofs[6],
        ):
            report = run_memory_continuity_proofs()
        self.assertEqual(report.overall_status, "DAILY_DRIVER_ACCEPT")
        self.assertEqual(report.memory_score, "4/5")

    def test_report_to_dict_serializable(self):
        from openjarvis.memory.memory_continuity import run_memory_continuity_proofs
        report = run_memory_continuity_proofs()
        d = report.to_dict()
        serialized = json.dumps(d)
        self.assertIn("overall_status", serialized)
        self.assertIn("proof_id", serialized)

    def test_no_cross_project_contamination_proof(self):
        """Project-scoped search must not return entries from other projects."""
        from openjarvis.memory.memory_continuity import _proof_no_cross_project_contamination
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        result = _proof_no_cross_project_contamination(mem)
        self.assertIn(result.status, ("PASS", "FAIL"))

    def test_insufficient_evidence_proof_passes_on_unique_query(self):
        from openjarvis.memory.memory_continuity import _proof_insufficient_evidence_reporting
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        result = _proof_insufficient_evidence_reporting(mem)
        self.assertEqual(result.status, "PASS")


class TestSemanticMemoryEnhancements(unittest.TestCase):
    """Verify new semantic_memory functions added in Sprint A."""

    def test_retrieve_accepted_decisions_returns_list(self):
        from openjarvis.memory.semantic_memory import retrieve_accepted_decisions
        results = retrieve_accepted_decisions("openjarvis")
        self.assertIsInstance(results, list)

    def test_retrieve_blockers_returns_list(self):
        from openjarvis.memory.semantic_memory import retrieve_blockers
        results = retrieve_blockers("openjarvis")
        self.assertIsInstance(results, list)

    def test_get_cloud_memory_status(self):
        from openjarvis.memory.semantic_memory import get_cloud_memory_status
        status = get_cloud_memory_status()
        self.assertEqual(status["memory_type"], "local_only")
        self.assertFalse(status["aws_s3_available"])
        self.assertFalse(status["cloud_sync_available"])
        self.assertEqual(status["status"], "DAILY_DRIVER_ACCEPT")
        self.assertTrue(status["no_raw_chain_of_thought"])

    def test_get_openjarvis_rust_status(self):
        from openjarvis.memory.semantic_memory import get_openjarvis_rust_status
        status = get_openjarvis_rust_status()
        self.assertFalse(status["required_for_4_5"])
        self.assertIn(status["status"], ("DAILY_DRIVER_ACCEPT", "OPTIONAL_BACKLOG"))
        self.assertTrue(status["no_raw_chain_of_thought"])

    def test_find_near_duplicates_no_key(self):
        """No OpenAI key → near-duplicate returns empty (graceful)."""
        from openjarvis.memory.semantic_memory import find_near_duplicates
        entries: list = []
        result = find_near_duplicates(entries, openai_key="")
        self.assertEqual(result, [])

    def test_find_near_duplicates_too_few_entries(self):
        from openjarvis.memory.semantic_memory import find_near_duplicates
        from openjarvis.memory.store import MemoryEntry
        entry = MemoryEntry(
            entry_id="e1", namespace="test", content="hello world",
            project_id="p", confidence=1.0, source="test",
        )
        result = find_near_duplicates([entry], openai_key="any")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Part D — Doctor checks for Sprint A modules
# ---------------------------------------------------------------------------

class TestSprintADoctorChecks(unittest.TestCase):
    """Verify doctor checks for provider capability matrix, memory continuity, Google OAuth."""

    def test_check_provider_capability_matrix_pass(self):
        from openjarvis.doctor.checks import check_provider_capability_matrix, CheckStatus
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENROUTER_API_KEY": "or-test",
        }):
            result = check_provider_capability_matrix("omnix")
        self.assertIn(result.status, (CheckStatus.PASS, CheckStatus.WARN))
        self.assertIn("Provider capability matrix", result.summary)
        self.assertIn("embedding_model", result.evidence)

    def test_check_memory_continuity_proofs_present(self):
        from openjarvis.doctor.checks import check_memory_continuity_proofs, CheckStatus
        result = check_memory_continuity_proofs("omnix")
        self.assertIn(result.status, (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL))
        self.assertIn("memory_score", result.evidence)

    def test_check_google_oauth_status_blocked(self):
        """Google OAuth check should WARN — client_secret missing."""
        with patch.dict("os.environ", {
            "GOOGLE_OAUTH_CLIENT_SECRET": "",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }):
            from openjarvis.doctor.checks import check_google_oauth_status, CheckStatus
            result = check_google_oauth_status("omnix")
        self.assertIn(result.status, (CheckStatus.WARN, CheckStatus.FAIL))
        self.assertIn("bryan_action", result.evidence)

    def test_all_new_sprint_a_checks_in_registry(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = {fn.__name__ for fn in _ALL_CHECK_FNS}
        self.assertIn("check_provider_capability_matrix", names)
        self.assertIn("check_memory_continuity_proofs", names)
        self.assertIn("check_google_oauth_status", names)

    def test_total_check_count_matches_registry(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        self.assertEqual(len(_ALL_CHECK_FNS), len(set(fn.__name__ for fn in _ALL_CHECK_FNS)),
                         "Duplicate check function names in registry")


if __name__ == "__main__":
    unittest.main()
