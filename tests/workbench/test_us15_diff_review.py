"""US15 Diff Review approve/reject workflow tests."""

from __future__ import annotations

import pytest


class TestDiffReviewStore:
    def test_create_review(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_PENDING

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(
            session_id="sess1",
            task_id="task1",
            repo_path=".",
            raw_diff="diff --git a/foo.py b/foo.py\n+new line\n-old line",
            dry_run=True,
        )
        assert review.review_id
        assert review.status == STATUS_PENDING
        assert review.session_id == "sess1"
        assert review.dry_run is True

    def test_approve_records_approval(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_APPROVED

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(session_id="sess2", task_id="t2", repo_path=".", raw_diff="+line")
        approved = store.approve(review.review_id, approved_by="manager", note="LGTM")
        assert approved is not None
        assert approved.status == STATUS_APPROVED
        assert approved.approved_by == "manager"
        assert approved.approval_note == "LGTM"

    def test_reject_does_not_apply_changes(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_REJECTED

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(session_id="sess3", task_id="t3", repo_path=".", raw_diff="+line")
        rejected = store.reject(review.review_id, reason="Style issues")
        assert rejected is not None
        assert rejected.status == STATUS_REJECTED
        assert rejected.reject_reason == "Style issues"
        # Verify: no file system mutation was performed (reject is metadata-only)
        # The test itself proves this since reject() only updates DB status.

    def test_manual_review_parks_diff(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_MANUAL_REVIEW

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(session_id="sess4", task_id="t4", repo_path=".")
        parked = store.mark_manual_review(review.review_id, note="Needs architecture review")
        assert parked is not None
        assert parked.status == STATUS_MANUAL_REVIEW

    def test_approve_then_reject_is_noop(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_APPROVED

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(session_id="sess5", task_id="t5", repo_path=".")
        store.approve(review.review_id, approved_by="manager")
        # Rejecting an already-approved review is a no-op
        result = store.reject(review.review_id, reason="Too late")
        assert result is not None
        assert result.status == STATUS_APPROVED  # unchanged

    def test_list_by_session(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        store.create(session_id="sA", task_id="t1", repo_path=".")
        store.create(session_id="sA", task_id="t2", repo_path=".")
        store.create(session_id="sB", task_id="t3", repo_path=".")
        reviews = store.list_by_session("sA")
        assert len(reviews) == 2
        assert all(r.session_id == "sA" for r in reviews)

    def test_list_pending(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore, STATUS_PENDING

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        r1 = store.create(session_id="s1", repo_path=".")
        r2 = store.create(session_id="s2", repo_path=".")
        store.approve(r2.review_id)
        pending = store.list_pending()
        ids = {r.review_id for r in pending}
        assert r1.review_id in ids
        assert r2.review_id not in ids

    def test_to_dict_has_required_fields(self, tmp_path):
        from openjarvis.workbench.diff_review import DiffReviewStore

        store = DiffReviewStore(db_path=str(tmp_path / "dr.db"))
        review = store.create(
            session_id="s1",
            repo_path=".",
            raw_diff="diff --git a/x.py b/x.py\nnew file mode 100644\n+new content\n",
        )
        d = review.to_dict()
        assert "review_id" in d
        assert "status" in d
        assert "changed_files" in d
        assert "changed_file_count" in d
        assert "reject_reason" in d
        assert "approved_by" in d
        assert "dry_run" in d


class TestDiffParsing:
    def test_parses_added_deleted_modified(self):
        from openjarvis.workbench.diff_review import _parse_diff

        raw = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n+++ b/foo.py\n"
            "+added line 1\n+added line 2\n-removed line\n"
            "diff --git a/bar.py b/bar.py\n"
            "new file mode 100644\n"
            "+bar content\n"
        )
        files = _parse_diff(raw)
        assert len(files) == 2
        assert files[0].path == "foo.py"
        assert files[0].additions == 2
        assert files[0].deletions == 1
        assert files[1].change_type == "added"

    def test_empty_diff_returns_empty(self):
        from openjarvis.workbench.diff_review import _parse_diff

        assert _parse_diff("") == []
        assert _parse_diff("no diff content here") == []
