"""Live Plan 9 orchestration executor tests — DAG, retrieval, batch integration."""

from __future__ import annotations

import pytest

from openjarvis.plan9.orchestration_executor import (
    TaskState,
    get_dag_run,
    get_batch_run,
    run_batch_integration,
    run_controlled_dag,
)


def test_controlled_dag_live_execution():
    record = run_controlled_dag(
        task_description="Plan 9 controlled DAG proof",
        scope="tests/fixtures",
    )
    assert record.retrieval_invoked is True
    assert record.state == TaskState.COMPLETED
    assert len(record.parallel_groups) == 1
    states = {n.task_id: n.state for n in record.nodes}
    assert states["retrieval"] == TaskState.COMPLETED
    assert states["read_a"] == TaskState.COMPLETED
    assert states["read_b"] == TaskState.COMPLETED
    assert states["summarize"] == TaskState.COMPLETED
    assert get_dag_run(record.run_id) is not None


def test_batch_integration_same_file_live():
    patch_a = "# Plan 9 batch integration fixture — safe allowlisted target.\nstatus=worker_a\n"
    patch_b = "review_marker=worker_b\n"
    record = run_batch_integration(
        target_file="tests/fixtures/plan9_batch_target.txt",
        worker_a_patch=patch_a,
        worker_b_patch=patch_b,
        run_tests=False,
    )
    assert record.state == TaskState.COMPLETED
    assert record.reviewer_verdict == "approved"
    assert "batch_integrator_merge" in record.integrated_content
    assert record.diff
    assert get_batch_run(record.run_id) is not None


def test_batch_integration_blocks_non_allowlisted():
    record = run_batch_integration(
        target_file="src/openjarvis/server/routes.py",
        worker_a_patch="a",
        worker_b_patch="b",
        run_tests=False,
    )
    assert record.blocked is True
    assert record.state == TaskState.BLOCKED
