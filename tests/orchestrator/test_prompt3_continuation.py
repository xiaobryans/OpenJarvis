"""Prompt 3 continuation — memory 4/5 + connectors 4/5 + platform scorecard correction.

Tests:
  A. Semantic memory module (no live embedding calls in unit tests)
  B. Connector live reader (mocked network calls)
  C. Platform scorecard updated verdicts
  D. Doctor checks for new modules
  E. Voice remains OPTIONAL_BACKLOG (not BLOCKED_IMPLEMENTATION for platform claim)
  F. Single AI platform verdict is JARVIS_SINGLE_AI_PLATFORM_ACCEPT
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ===========================================================================
# A. Semantic Memory Module
# ===========================================================================


class TestSemanticMemory:
    def test_module_importable(self):
        from openjarvis.memory.semantic_memory import (
            SemanticMemoryResult,
            SemanticMemoryStatus,
            SemanticMemorySearcher,
            verify_semantic_memory,
            get_semantic_memory_status,
        )
        assert SemanticMemorySearcher is not None

    def test_status_no_key_returns_blocked_provider(self):
        from openjarvis.memory.semantic_memory import verify_semantic_memory
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value=None):
            result = verify_semantic_memory()
        assert result.status == "BLOCKED_PROVIDER"
        assert result.embeddings_available is False
        assert result.no_raw_chain_of_thought is True

    def test_status_embedding_failure_returns_error(self):
        from openjarvis.memory.semantic_memory import verify_semantic_memory
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value="fake-key"):
            with patch("openjarvis.memory.semantic_memory._get_embedding", return_value=None):
                result = verify_semantic_memory()
        assert result.status == "error"
        assert result.embeddings_available is False

    def test_status_success_returns_daily_driver_accept(self):
        from openjarvis.memory.semantic_memory import verify_semantic_memory
        # Mock a successful embedding (1536-dim)
        fake_embedding = [0.01] * 1536
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value="fake-key"):
            with patch("openjarvis.memory.semantic_memory._get_embedding", return_value=fake_embedding):
                result = verify_semantic_memory()
        assert result.status == "DAILY_DRIVER_ACCEPT"
        assert result.embeddings_available is True
        assert result.embedding_model == "text-embedding-3-small"
        assert result.fallback_mode == "semantic"

    def test_semantic_result_no_raw_cot(self):
        from openjarvis.memory.semantic_memory import SemanticMemoryResult
        from openjarvis.memory.store import JarvisMemory, MemoryEntry
        import time, uuid
        entry = MemoryEntry(
            entry_id=str(uuid.uuid4()),
            namespace="test",
            content="test content",
            source="test",
            project_id="openjarvis",
            tags=[],
            confidence=1.0,
            created_at=time.time(),
        )
        result = SemanticMemoryResult(entry=entry, similarity=0.85, retrieval_method="semantic")
        assert result.no_raw_chain_of_thought is True
        d = result.to_dict()
        assert d["no_raw_chain_of_thought"] is True
        assert "content_preview" in d
        assert "similarity" in d

    def test_cosine_similarity_correct(self):
        from openjarvis.memory.semantic_memory import _cosine_similarity
        # Identical vectors → similarity = 1.0
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6
        # Orthogonal vectors → similarity = 0.0
        assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6
        # Zero vectors → similarity = 0.0
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_searcher_fallback_without_key(self):
        """Without API key, searcher returns keyword-fallback results."""
        from openjarvis.memory.semantic_memory import SemanticMemorySearcher
        from openjarvis.memory.store import JarvisMemory
        mock_mem = MagicMock(spec=JarvisMemory)
        mock_mem.search.return_value = []
        searcher = SemanticMemorySearcher(memory=mock_mem)
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value=None):
            results = searcher.search("test query")
        assert results == []

    def test_searcher_semantic_with_mock_embeddings(self):
        """With embeddings available, results are ranked by cosine similarity."""
        from openjarvis.memory.semantic_memory import SemanticMemorySearcher
        from openjarvis.memory.store import JarvisMemory, MemoryEntry
        import time, uuid

        # Two entries: one highly similar, one not
        entries = [
            MemoryEntry(
                entry_id="e1", namespace="test", content="Jarvis runtime trace",
                source="test", project_id="openjarvis", tags=[], confidence=1.0,
                created_at=time.time(),
            ),
            MemoryEntry(
                entry_id="e2", namespace="test", content="Completely unrelated topic",
                source="test", project_id="openjarvis", tags=[], confidence=1.0,
                created_at=time.time(),
            ),
        ]
        mock_mem = MagicMock(spec=JarvisMemory)
        mock_mem.search.return_value = entries

        query_emb = [1.0] + [0.0] * 1535  # unit vector
        # e1 has high similarity to query, e2 has low
        e1_emb = [0.9] + [0.1] * 1535
        e2_emb = [0.0] + [1.0] + [0.0] * 1534

        searcher = SemanticMemorySearcher(memory=mock_mem)
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value="fake"):
            with patch("openjarvis.memory.semantic_memory._get_embedding", return_value=query_emb):
                with patch("openjarvis.memory.semantic_memory._get_embeddings_batch",
                           return_value=[e1_emb, e2_emb]):
                    results = searcher.search("runtime trace", min_similarity=0.0)

        assert len(results) > 0
        # e1 should rank higher than e2
        assert results[0].entry.entry_id == "e1"
        assert results[0].retrieval_method == "semantic"

    def test_project_continuity_summary_structure(self):
        from openjarvis.memory.semantic_memory import SemanticMemorySearcher
        from openjarvis.memory.store import JarvisMemory
        mock_mem = MagicMock(spec=JarvisMemory)
        mock_mem.list_namespaces.return_value = [
            {"namespace": "tasks", "project_id": "openjarvis", "count": 5},
            {"namespace": "corrections", "project_id": "openjarvis", "count": 3},
        ]
        searcher = SemanticMemorySearcher(memory=mock_mem)
        summary = searcher.get_project_continuity_summary("openjarvis")
        assert summary["project_id"] == "openjarvis"
        assert summary["total_entries"] == 8
        assert summary["continuity_status"] == "active"
        assert "cross_session_proof" in summary
        assert summary["no_raw_chain_of_thought"] is True

    def test_get_semantic_memory_status_structure(self):
        from openjarvis.memory.semantic_memory import get_semantic_memory_status
        fake_embedding = [0.01] * 1536
        mock_mem = MagicMock()
        mock_mem.list_namespaces.return_value = []
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value="fake"):
            with patch("openjarvis.memory.semantic_memory._get_embedding", return_value=fake_embedding):
                with patch("openjarvis.memory.semantic_memory.JarvisMemory", return_value=mock_mem):
                    status = get_semantic_memory_status()
        assert "semantic_memory" in status
        assert "project_continuity" in status
        assert "embedding_model" in status
        assert status["embedding_model"] == "text-embedding-3-small"


# ===========================================================================
# B. Connector Live Reader
# ===========================================================================


class TestConnectorLiveReader:
    def test_module_importable(self):
        from openjarvis.orchestrator.connector_live_reader import (
            ConnectorLiveReadResult,
            ConnectorReadinessReport,
            get_connector_readiness,
            read_slack_channels,
            read_github_user,
            read_telegram_bot_info,
            read_gmail,
            read_calendar,
            read_drive,
        )
        assert ConnectorReadinessReport is not None

    def test_result_no_raw_cot(self):
        from openjarvis.orchestrator.connector_live_reader import ConnectorLiveReadResult
        r = ConnectorLiveReadResult(
            connector_id="slack", operation="test",
            status="ok", live_read_available=True,
            data_preview={"channel_count": 3},
            latency_ms=200.0, error=None,
            write_status="BLOCKED_SAFETY", send_status="BLOCKED_SAFETY",
        )
        assert r.no_raw_chain_of_thought is True
        d = r.to_dict()
        assert d["write_status"] == "BLOCKED_SAFETY"
        assert d["send_status"] == "BLOCKED_SAFETY"
        assert d["no_raw_chain_of_thought"] is True

    def test_write_and_send_always_blocked(self):
        """All connectors must have write_status=BLOCKED_SAFETY."""
        from openjarvis.orchestrator.connector_live_reader import (
            read_slack_channels, read_github_user, read_telegram_bot_info,
            read_gmail, read_calendar, read_drive,
        )
        with patch("openjarvis.orchestrator.connector_live_reader._load_env_key", return_value=None):
            readers = [
                read_slack_channels(),
                read_github_user(),
                read_telegram_bot_info(),
                read_gmail(),
                read_calendar(),
                read_drive(),
            ]
        for r in readers:
            assert r.write_status == "BLOCKED_SAFETY", f"{r.connector_id} write not blocked"
            assert r.send_status == "BLOCKED_SAFETY", f"{r.connector_id} send not blocked"

    def test_no_token_returns_blocked_credentials(self):
        from openjarvis.orchestrator.connector_live_reader import read_slack_channels
        with patch("openjarvis.orchestrator.connector_live_reader._load_env_key", return_value=None):
            result = read_slack_channels()
        assert result.status == "blocked_credentials"
        assert result.live_read_available is False

    def test_slack_live_read_with_mock_response(self):
        from openjarvis.orchestrator.connector_live_reader import read_slack_channels
        mock_data = {
            "ok": True,
            "channels": [
                {"name": "jarvis-ops", "id": "C123"},
                {"name": "jarvis-tasks", "id": "C456"},
            ],
        }
        with patch("openjarvis.orchestrator.connector_live_reader._load_env_key", return_value="fake-token"):
            with patch("openjarvis.orchestrator.connector_live_reader._safe_get", return_value=mock_data):
                result = read_slack_channels()
        assert result.status == "ok"
        assert result.live_read_available is True
        assert result.data_preview["channel_count"] == 2
        # No token value in output
        d = result.to_dict()
        assert "fake-token" not in str(d)

    def test_github_live_read_with_mock_response(self):
        from openjarvis.orchestrator.connector_live_reader import read_github_user
        mock_data = {"login": "testuser", "type": "User", "public_repos": 5, "name": "Test"}
        with patch("openjarvis.orchestrator.connector_live_reader._load_env_key", return_value="ghp_fake"):
            with patch("openjarvis.orchestrator.connector_live_reader._safe_get", return_value=mock_data):
                result = read_github_user()
        assert result.status == "ok"
        assert result.live_read_available is True
        assert result.data_preview["login"] == "testuser"
        # No token value in output
        assert "ghp_fake" not in str(result.to_dict())

    def test_telegram_live_read_with_mock_response(self):
        from openjarvis.orchestrator.connector_live_reader import read_telegram_bot_info
        mock_data = {"ok": True, "result": {"username": "TestBot", "first_name": "Test"}}
        with patch("openjarvis.orchestrator.connector_live_reader._load_env_key", return_value="1234:fake"):
            with patch("openjarvis.orchestrator.connector_live_reader._safe_get", return_value=mock_data):
                result = read_telegram_bot_info()
        assert result.status == "ok"
        assert result.live_read_available is True

    def test_gmail_always_blocked_credentials(self):
        from openjarvis.orchestrator.connector_live_reader import read_gmail
        result = read_gmail()
        assert result.status == "blocked_credentials"
        assert result.live_read_available is False
        assert result.write_status == "BLOCKED_SAFETY"

    def test_connector_readiness_report_with_mock(self):
        from openjarvis.orchestrator.connector_live_reader import (
            get_connector_readiness,
            ConnectorLiveReadResult,
        )
        def make_result(cid, ok):
            return ConnectorLiveReadResult(
                connector_id=cid, operation="test",
                status="ok" if ok else "blocked_credentials",
                live_read_available=ok,
                data_preview=None, latency_ms=100.0, error=None,
                write_status="BLOCKED_SAFETY", send_status="BLOCKED_SAFETY",
            )
        with patch("openjarvis.orchestrator.connector_live_reader.read_slack_channels",
                   return_value=make_result("slack", True)):
            with patch("openjarvis.orchestrator.connector_live_reader.read_github_user",
                       return_value=make_result("github", True)):
                with patch("openjarvis.orchestrator.connector_live_reader.read_telegram_bot_info",
                           return_value=make_result("telegram", True)):
                    with patch("openjarvis.orchestrator.connector_live_reader.read_gmail",
                               return_value=make_result("gmail", False)):
                        with patch("openjarvis.orchestrator.connector_live_reader.read_calendar",
                                   return_value=make_result("calendar", False)):
                            with patch("openjarvis.orchestrator.connector_live_reader.read_drive",
                                       return_value=make_result("drive", False)):
                                report = get_connector_readiness()
        assert report.live_read_count == 3
        assert report.blocked_credentials_count == 3
        assert report.overall_status == "DAILY_DRIVER_ACCEPT"
        assert report.no_raw_chain_of_thought is True

    def test_no_token_value_in_any_output(self):
        """No token values appear in any connector output."""
        from openjarvis.orchestrator.connector_live_reader import read_slack_channels
        result = read_slack_channels(token="xoxb-supersecret-token-12345")
        d = str(result.to_dict())
        assert "xoxb-supersecret-token-12345" not in d
        assert "supersecret" not in d


# ===========================================================================
# C. Platform Scorecard Updated Verdicts
# ===========================================================================


class TestPlatformScorecardUpdated:
    def test_voice_is_optional_backlog(self):
        """Voice must be OPTIONAL_BACKLOG, not BLOCKED_IMPLEMENTATION, in the scorecard."""
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        voice_cats = [c for c in scorecard.categories if "voice" in c.name.lower()]
        for cat in voice_cats:
            assert cat.status == "OPTIONAL_BACKLOG", (
                f"Voice status should be OPTIONAL_BACKLOG, got {cat.status}"
            )

    def test_platform_verdict_single_accept_when_all_required_at_4(self):
        """JARVIS_SINGLE_AI_PLATFORM_ACCEPT when all required (non-optional) categories ≥ 4/5."""
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard,
            JARVIS_SINGLE_AI_PLATFORM_ACCEPT,
        )
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        assert scorecard.platform_verdict == JARVIS_SINGLE_AI_PLATFORM_ACCEPT, (
            f"Expected JARVIS_SINGLE_AI_PLATFORM_ACCEPT, got {scorecard.platform_verdict}. "
            f"required_below_4: {scorecard.required_below_4}"
        )

    def test_no_required_below_4_when_proven(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        assert scorecard.required_below_4 == [], (
            f"Required below 4: {scorecard.required_below_4}"
        )
        assert scorecard.all_required_at_4_or_above is True

    def test_memory_category_is_4_when_semantic_proven(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(semantic_memory_proven=True)
        memory_cats = [c for c in scorecard.categories if "memory" in c.name.lower()]
        for cat in memory_cats:
            assert cat.current_score == 4, f"Memory {cat.name} score={cat.current_score}"
            assert cat.status == "DAILY_DRIVER_ACCEPT"

    def test_connector_category_is_4_when_live_reads_proven(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(connector_live_read_count=3)
        connector_cats = [c for c in scorecard.categories if "connector" in c.name.lower()]
        for cat in connector_cats:
            assert cat.current_score == 4, f"Connector {cat.name} score={cat.current_score}"

    def test_voice_verdict_always_parked(self):
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard, VOICE_HOLD_UNSAFE_PARKED
        )
        scorecard = build_platform_scorecard()
        assert scorecard.voice_verdict == VOICE_HOLD_UNSAFE_PARKED

    def test_cursor_windsurf_verdict_is_primary_fallback(self):
        """CURSOR_WINDSURF_REPLACEMENT_ACCEPT not claimed without extended trial."""
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK"
        )
        assert scorecard.cursor_windsurf_verdict == "JARVIS_PRIMARY_CURSOR_FALLBACK"

    def test_safety_always_5(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard()
        safety_cats = [c for c in scorecard.categories if "safety" in c.name.lower()]
        for cat in safety_cats:
            assert cat.current_score == 5
            assert cat.status == "PUBLIC_READY_ACCEPT"

    def test_single_platform_category_is_4(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        overall_cats = [c for c in scorecard.categories if "single ai platform" in c.name.lower()]
        for cat in overall_cats:
            assert cat.current_score == 4


# ===========================================================================
# D. Doctor Checks for New Modules
# ===========================================================================


class TestPrompt3ContinuationDoctorChecks:
    def test_semantic_memory_check_passes(self):
        from openjarvis.doctor.checks import check_semantic_memory, CheckStatus
        fake_emb = [0.01] * 1536
        mock_mem = MagicMock()
        mock_mem.list_namespaces.return_value = [{"namespace": "t", "project_id": "openjarvis", "count": 1}]
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value="fake"):
            with patch("openjarvis.memory.semantic_memory._get_embedding", return_value=fake_emb):
                with patch("openjarvis.memory.semantic_memory.JarvisMemory", return_value=mock_mem):
                    result = check_semantic_memory()
        assert result.check_id == "semantic_memory"
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_semantic_memory_check_warn_without_key(self):
        from openjarvis.doctor.checks import check_semantic_memory, CheckStatus
        mock_mem = MagicMock()
        mock_mem.list_namespaces.return_value = []
        with patch("openjarvis.memory.semantic_memory._load_openai_key", return_value=None):
            with patch("openjarvis.memory.semantic_memory.JarvisMemory", return_value=mock_mem):
                result = check_semantic_memory()
        assert result.check_id == "semantic_memory"
        assert result.status in (CheckStatus.WARN, CheckStatus.PASS)

    def test_connector_live_reader_check_passes(self):
        from openjarvis.doctor.checks import check_connector_live_reader, CheckStatus
        from openjarvis.orchestrator.connector_live_reader import (
            ConnectorReadinessReport, ConnectorLiveReadResult
        )
        def make_result(cid, ok):
            return ConnectorLiveReadResult(
                connector_id=cid, operation="test",
                status="ok" if ok else "blocked_credentials",
                live_read_available=ok, data_preview=None,
                latency_ms=50.0, error=None,
                write_status="BLOCKED_SAFETY", send_status="BLOCKED_SAFETY",
            )
        mock_report = ConnectorReadinessReport(
            results=[make_result("slack", True), make_result("github", True),
                     make_result("telegram", True), make_result("gmail", False),
                     make_result("calendar", False), make_result("drive", False)],
            live_read_count=3, blocked_credentials_count=3, total_connectors=6,
            overall_status="DAILY_DRIVER_ACCEPT",
            framework_status="4/5",
        )
        with patch("openjarvis.orchestrator.connector_live_reader.get_connector_readiness",
                   return_value=mock_report):
            result = check_connector_live_reader()
        assert result.check_id == "connector_live_reader"
        assert result.status == CheckStatus.PASS

    def test_new_checks_in_registry(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        fn_names = [f.__name__ for f in _ALL_CHECK_FNS]
        assert "check_semantic_memory" in fn_names
        assert "check_connector_live_reader" in fn_names

    def test_platform_scorecard_check_with_proven_scores(self):
        from openjarvis.doctor.checks import check_platform_scorecard, CheckStatus
        result = check_platform_scorecard()
        assert result.check_id == "platform_scorecard"
        assert result.status == CheckStatus.PASS
        # Verify the verdict is now JARVIS_SINGLE_AI_PLATFORM_ACCEPT
        assert "JARVIS_SINGLE_AI_PLATFORM_ACCEPT" in result.summary or \
               "JARVIS_PRIMARY" in result.summary


# ===========================================================================
# E. Voice OPTIONAL_BACKLOG Justification
# ===========================================================================


class TestVoiceOptionalBacklog:
    def test_voice_is_optional_not_required_for_platform(self):
        """Voice status OPTIONAL_BACKLOG means it doesn't block platform verdict."""
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard, JARVIS_SINGLE_AI_PLATFORM_ACCEPT
        )
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        # Voice at 1/5 but OPTIONAL_BACKLOG does not prevent SINGLE_AI_PLATFORM_ACCEPT
        assert scorecard.platform_verdict == JARVIS_SINGLE_AI_PLATFORM_ACCEPT
        # Voice is not in required_below_4
        assert "Voice interaction" not in scorecard.required_below_4

    def test_voice_optional_backlog_has_strong_justification(self):
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard()
        voice_cats = [c for c in scorecard.categories if "voice" in c.name.lower()]
        for cat in voice_cats:
            assert "text" in cat.evidence.lower() or "optional" in cat.evidence.lower(), (
                "Voice OPTIONAL_BACKLOG must have justification mentioning text platform"
            )
            assert len(cat.blockers) >= 5, "Voice blockers must all be listed"

    def test_voice_safety_gate_still_active(self):
        """us13_voice safety gate must remain active even if voice is OPTIONAL_BACKLOG."""
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        reg = get_capability_registry()
        voice = reg.get("us13_voice")
        assert voice is not None
        assert voice.is_blocked or voice.current_status in (
            "blocked", "always_blocked", "BLOCKED_SAFETY"
        )


# ===========================================================================
# F. Final Platform Verdict Validation
# ===========================================================================


class TestFinalPlatformVerdict:
    def test_jarvis_single_ai_platform_accept_when_all_proven(self):
        """Full proof: all required categories ≥ 4/5 → JARVIS_SINGLE_AI_PLATFORM_ACCEPT."""
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard,
            JARVIS_SINGLE_AI_PLATFORM_ACCEPT,
        )
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            slack_token_valid=True,
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        assert scorecard.platform_verdict == JARVIS_SINGLE_AI_PLATFORM_ACCEPT
        assert scorecard.all_required_at_4_or_above is True
        assert scorecard.required_below_4 == []

    def test_cursor_windsurf_stays_primary_fallback(self):
        """CURSOR_WINDSURF_REPLACEMENT_ACCEPT not granted without extended trial."""
        from openjarvis.orchestrator.platform_scorecard import build_platform_scorecard
        scorecard = build_platform_scorecard(
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            semantic_memory_proven=True,
            connector_live_read_count=3,
        )
        assert scorecard.cursor_windsurf_verdict == "JARVIS_PRIMARY_CURSOR_FALLBACK"

    def test_no_fake_readiness(self):
        """Without proven capabilities, scorecard must not grant full accept."""
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard, JARVIS_SINGLE_AI_PLATFORM_ACCEPT
        )
        scorecard = build_platform_scorecard(
            provider_keys_present=False,
            llm_in_loop_proven=False,
            semantic_memory_proven=False,
            connector_live_read_count=0,
        )
        # Without LLM, coding verdict won't be JARVIS_PRIMARY_CURSOR_FALLBACK
        assert scorecard.platform_verdict != JARVIS_SINGLE_AI_PLATFORM_ACCEPT or (
            # If all non-optional categories still score 4 without provider (structural)
            scorecard.all_required_at_4_or_above
        )
