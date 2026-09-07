from __future__ import annotations

import unittest

from checkin_platform.reliability import (
    OperationFailure,
    ReliabilityError,
    RetryPolicy,
    build_dlq_record,
    is_retryable_http,
    plan_replay,
    resolved_dlq_patch,
    run_with_retry,
    sanitize_error_summary,
    verbatim_dm,
)


def submission(raw: str = "- publish notes @status:done ~30m") -> dict:
    return {
        "correlation_id": "ci-20260904-abcdef",
        "user_id": "mm-user-1",
        "pod_id": "pod-nails",
        "cycle_date": "2026-09-04",
        "checkin_type": "EOD",
        "raw_submission": raw,
    }


def dlq(**overrides) -> dict:
    record = build_dlq_record(
        submission(),
        failure_stage="baserow_checkins_write",
        source_execution_id="n8n-9001",
        error_code="BASEROW_503",
        error_summary="Service unavailable",
        created_at="2026-09-04T16:07:21Z",
    )
    record.update(overrides)
    return record


class RetryTests(unittest.TestCase):
    def test_default_policy_is_exactly_three_attempts(self) -> None:
        policy = RetryPolicy()
        self.assertEqual(policy.attempts, 3)
        self.assertEqual(policy.between_attempt_seconds, (1, 4))
        self.assertEqual(policy.dlq_retry_after_seconds, 16)

    def test_policy_rejects_mismatched_delays(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "one delay"):
            RetryPolicy(attempts=3, between_attempt_seconds=(1,))

    def test_http_retry_classification(self) -> None:
        for status in (408, 425, 429, 500, 503, 599):
            self.assertTrue(is_retryable_http(status), status)
        for status in (400, 401, 403, 404, 409, 422):
            self.assertFalse(is_retryable_http(status), status)

    def test_retry_succeeds_on_third_attempt(self) -> None:
        sleeps: list[int] = []

        def operation(attempt: int) -> str:
            if attempt < 3:
                raise OperationFailure("HTTP_503", "temporary", retryable=True, http_status=503)
            return "stored"

        result = run_with_retry(operation, sleep=sleeps.append)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(sleeps, [1, 4])

    def test_non_retryable_failure_stops_immediately(self) -> None:
        result = run_with_retry(
            lambda _attempt: (_ for _ in ()).throw(OperationFailure("HTTP_400", "bad request", retryable=False))
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.attempts, 1)

    def test_retry_exhaustion_returns_sanitized_failure(self) -> None:
        result = run_with_retry(
            lambda _attempt: (_ for _ in ()).throw(
                OperationFailure("HTTP_503", "Authorization: Bearer super-secret", retryable=True)
            )
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.attempts, 3)
        self.assertNotIn("super-secret", result.failure.summary)


class DlqTests(unittest.TestCase):
    def test_record_preserves_raw_submission_exactly(self) -> None:
        raw = "  • first item  \n\t- second item `literal`"
        record = build_dlq_record(
            submission(raw),
            failure_stage="event_dispatch",
            source_execution_id="exec-raw",
            error_code="CH_503",
            error_summary="unavailable",
            created_at="2026-09-04T16:00:00+00:00",
        )
        self.assertEqual(record["raw_submission"], raw)

    def test_record_id_is_deterministic(self) -> None:
        first = dlq()
        second = dlq()
        self.assertEqual(first["dlq_id"], second["dlq_id"])
        self.assertEqual(first["replay_key"], "n8n-9001|baserow_checkins_write")

    def test_different_failure_stages_have_different_ids(self) -> None:
        first = dlq()
        second = build_dlq_record(
            submission(),
            failure_stage="event_dispatch",
            source_execution_id="n8n-9001",
            error_code="CH_503",
            error_summary="unavailable",
            created_at="2026-09-04T16:07:21Z",
        )
        self.assertNotEqual(first["dlq_id"], second["dlq_id"])

    def test_capture_before_attempt_three_fails_closed(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "exactly"):
            build_dlq_record(
                submission(),
                failure_stage="event_dispatch",
                source_execution_id="exec-early",
                error_code="CH_503",
                error_summary="unavailable",
                created_at="2026-09-04T16:00:00Z",
                attempt_count=2,
            )

    def test_capture_after_attempt_three_also_fails_closed(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "exactly"):
            build_dlq_record(
                submission(),
                failure_stage="event_dispatch",
                source_execution_id="exec-late",
                error_code="CH_503",
                error_summary="unavailable",
                created_at="2026-09-04T16:00:00Z",
                attempt_count=4,
            )

    def test_raw_submission_is_limited_by_utf8_bytes(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "65536"):
            build_dlq_record(
                submission("é" * 40000),
                failure_stage="event_dispatch",
                source_execution_id="exec-large",
                error_code="CH_503",
                error_summary="unavailable",
                created_at="2026-09-04T16:00:00Z",
            )

    def test_error_summary_redacts_common_secret_forms(self) -> None:
        sanitized = sanitize_error_summary(
            "Authorization: Bearer abc token=def password:ghi https://name:pass@example.internal"
        )
        for secret in ("abc", "def", "ghi", "name:pass@"):
            self.assertNotIn(secret, sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_verbatim_dm_uses_safe_fence(self) -> None:
        raw = "line one\n```\nline two"
        message = verbatim_dm(raw, "dlq-1")
        self.assertIn("````\n" + raw + "\n````", message)


class ReplayTests(unittest.TestCase):
    def test_replay_resumes_from_failed_stage(self) -> None:
        expectations = {
            "baserow_checkins_write": ["upsert_checkin", "ensure_canonical_post", "ensure_event"],
            "mattermost_canonical_post": ["verify_checkin", "ensure_canonical_post", "ensure_event"],
            "event_dispatch": ["verify_checkin", "verify_canonical_post", "ensure_event"],
        }
        for stage, steps in expectations.items():
            with self.subTest(stage=stage):
                record = dlq(failure_stage=stage, next_retry_at="2026-09-04T16:07:00Z")
                plan = plan_replay(record, now="2026-09-04T16:08:00Z", worker_id="worker-a")
                self.assertEqual(plan["steps"], steps)
                self.assertEqual(plan["correlation_id"], record["correlation_id"])
                self.assertEqual(plan["replay_key"], record["replay_key"])

    def test_not_due_record_is_not_acquired(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "not due"):
            plan_replay(dlq(), now="2026-09-04T16:07:30Z", worker_id="worker-a")

    def test_active_lease_prevents_concurrent_replay(self) -> None:
        record = dlq(
            status="replaying",
            replay_started_at="2026-09-04T16:10:00Z",
            next_retry_at=None,
        )
        with self.assertRaisesRegex(ReliabilityError, "active replay lease"):
            plan_replay(record, now="2026-09-04T16:20:00Z", worker_id="worker-b")

    def test_stale_lease_can_be_recovered(self) -> None:
        record = dlq(
            status="replaying",
            replay_started_at="2026-09-04T16:00:00Z",
            replay_attempt_count=1,
            next_retry_at=None,
        )
        plan = plan_replay(record, now="2026-09-04T16:16:00Z", worker_id="worker-b")
        self.assertEqual(plan["replay_attempt_count"], 2)

    def test_resolved_row_is_not_replayable(self) -> None:
        with self.assertRaisesRegex(ReliabilityError, "not replayable"):
            plan_replay(dlq(status="resolved"), now="2026-09-05T00:00:00Z", worker_id="worker-a")

    def test_resolution_sets_retention_date(self) -> None:
        patch = resolved_dlq_patch(
            dlq(status="replaying"),
            resolved_at="2026-09-05T10:00:00Z",
            checkin_id="mm-user-1|2026-09-04|EOD",
        )
        self.assertEqual(patch["status"], "resolved")
        self.assertEqual(patch["retention_delete_after"], "2026-10-05T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
