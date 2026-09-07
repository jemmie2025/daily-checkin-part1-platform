from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from checkin_platform.compliance import (
    ComplianceError,
    build_expectations,
    plan_compliance_actions,
    weekly_rollup,
)


UTC = timezone.utc


def roster() -> list[dict]:
    return [
        {
            "user_id": "mm-alice",
            "user_name": "Alice Example",
            "pod_id": "pod-nails",
            "timezone": "Africa/Lagos",
            "active": True,
            "active_from": "2026-01-01",
        },
        {
            "user_id": "mm-bob",
            "user_name": "Bob Example",
            "pod_id": "pod-nails",
            "timezone": "Europe/London",
            "active": True,
            "active_from": "2026-01-01",
        },
        {
            "user_id": "mm-cara",
            "user_name": "Cara Example",
            "pod_id": "pod-platform",
            "timezone": "Africa/Lagos",
            "active": False,
        },
    ]


def rules() -> list[dict]:
    return [
        {"checkin_type": "SOD", "sla_code": "SOD-0900", "local_due_time": "09:00"},
        {"checkin_type": "EOD", "sla_code": "EOD-1700", "local_due_time": "17:00"},
    ]


def expectations(**kwargs) -> list[dict]:
    return build_expectations(
        roster(),
        "2026-09-04",
        rules(),
        roster_source_version="roster-v7",
        **kwargs,
    )


class ExpectationTests(unittest.TestCase):
    def test_builds_deterministic_expectations_for_each_cycle(self) -> None:
        first = expectations()
        second = expectations()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual(len({item["expectation_id"] for item in first}), 6)

    def test_cycle_date_is_user_local_and_due_time_is_utc(self) -> None:
        eod = next(item for item in expectations() if item["user_id"] == "mm-alice" and item["checkin_type"] == "EOD")
        self.assertEqual(eod["cycle_date"], "2026-09-04")
        self.assertEqual(eod["sla_due_at"], "2026-09-04T16:00:00Z")

    def test_dst_timezone_conversion_is_correct(self) -> None:
        london = [dict(roster()[1])]
        result = build_expectations(
            london,
            "2026-07-01",
            [{"checkin_type": "EOD", "sla_code": "EOD-1700", "local_due_time": "17:00"}],
            roster_source_version="roster-summer",
        )
        self.assertEqual(result[0]["sla_due_at"], "2026-07-01T16:00:00Z")

    def test_approved_leave_is_suppressed(self) -> None:
        result = expectations(
            leave_records=[
                {"user_id": "mm-bob", "status": "approved", "start_date": "2026-09-01", "end_date": "2026-09-05"}
            ]
        )
        self.assertEqual({item["attendance_state"] for item in result if item["user_id"] == "mm-bob"}, {"approved_leave"})

    def test_unapproved_leave_is_not_suppressed(self) -> None:
        result = expectations(
            leave_records=[
                {"user_id": "mm-bob", "status": "requested", "start_date": "2026-09-01", "end_date": "2026-09-05"}
            ]
        )
        self.assertEqual({item["attendance_state"] for item in result if item["user_id"] == "mm-bob"}, {"expected"})

    def test_global_holiday_is_suppressed(self) -> None:
        result = expectations(holidays=[{"date": "2026-09-04", "scope": "global"}])
        self.assertNotIn("expected", {item["attendance_state"] for item in result})

    def test_pod_holiday_does_not_suppress_another_pod(self) -> None:
        result = expectations(holidays=[{"date": "2026-09-04", "scope": "pod", "pod_id": "pod-nails"}])
        nails = {item["attendance_state"] for item in result if item["pod_id"] == "pod-nails"}
        platform = {item["attendance_state"] for item in result if item["pod_id"] == "pod-platform"}
        self.assertEqual(nails, {"holiday"})
        self.assertEqual(platform, {"inactive"})

    def test_inactive_member_remains_out_of_denominator(self) -> None:
        result = expectations()
        self.assertEqual({item["attendance_state"] for item in result if item["user_id"] == "mm-cara"}, {"inactive"})

    def test_duplicate_roster_identity_fails_closed(self) -> None:
        duplicate = roster() + [copy.deepcopy(roster()[0])]
        with self.assertRaisesRegex(ComplianceError, "duplicate roster user_id"):
            build_expectations(duplicate, "2026-09-04", rules(), roster_source_version="v1")

    def test_duplicate_sla_expectation_fails_closed(self) -> None:
        duplicate_rules = rules() + [copy.deepcopy(rules()[0])]
        with self.assertRaisesRegex(ComplianceError, "duplicate SLA expectation"):
            build_expectations(roster(), "2026-09-04", duplicate_rules, roster_source_version="v1")

    def test_unknown_timezone_fails_closed(self) -> None:
        broken = [dict(roster()[0], timezone="Mars/Olympus")]
        with self.assertRaisesRegex(ComplianceError, "unknown IANA timezone"):
            build_expectations(broken, "2026-09-04", rules(), roster_source_version="v1")

    def test_invalid_sla_time_fails_closed(self) -> None:
        with self.assertRaisesRegex(ComplianceError, "local_due_time"):
            build_expectations(
                roster()[:1],
                "2026-09-04",
                [{"checkin_type": "EOD", "sla_code": "bad", "local_due_time": "25:00"}],
                roster_source_version="v1",
            )


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.expected = expectations()

    def plan(self, now: str, **kwargs) -> list[dict]:
        return plan_compliance_actions(
            self.expected,
            [],
            now=now,
            workflow_execution_id="n8n-compliance-1",
            **kwargs,
        )

    def test_nudge_is_emitted_at_sla_minus_sixty(self) -> None:
        actions = self.plan("2026-09-04T15:00:00Z")
        nudges = [item for item in actions if item["action_type"] == "nudge"]
        self.assertEqual({item["user_id"] for item in nudges}, {"mm-alice", "mm-bob"})

    def test_nudge_is_not_emitted_early(self) -> None:
        actions = self.plan("2026-09-04T14:59:59Z")
        self.assertFalse(any(item["action_type"] == "nudge" and item["checkin_type"] == "EOD" for item in actions))

    def test_existing_nudge_id_prevents_duplicate(self) -> None:
        first = self.plan("2026-09-04T15:00:00Z")
        existing = {item["action_id"] for item in first}
        second = self.plan("2026-09-04T15:10:00Z", existing_action_ids=existing)
        self.assertFalse(any(item["action_type"] == "nudge" for item in second))

    def test_accepted_checkin_prevents_nudge_and_violation(self) -> None:
        accepted = [{"checkin_id": "ci-a", "user_id": "mm-alice", "cycle_date": "2026-09-04", "checkin_type": "EOD"}]
        actions = plan_compliance_actions(
            self.expected,
            accepted,
            now="2026-09-04T16:01:00Z",
            workflow_execution_id="exec-1",
        )
        alice = [item for item in actions if item.get("user_id") == "mm-alice" or item.get("record", {}).get("user_id") == "mm-alice"]
        self.assertEqual(alice, [])

    def test_breach_creates_one_pi6_record(self) -> None:
        actions = self.plan("2026-09-04T16:00:00Z")
        rows = [item["record"] for item in actions if item["action_type"] == "upsert_violation"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["rule_id"] == "PI-6" for row in rows))
        self.assertTrue(all(row["checkin_type"] == "EOD" for row in rows))

    def test_sod_does_not_create_pi6_violation(self) -> None:
        actions = self.plan("2026-09-04T09:00:00Z")
        self.assertFalse(any(item["action_type"] == "upsert_violation" for item in actions))

    def test_violation_id_is_stable_across_executions(self) -> None:
        first = self.plan("2026-09-04T16:00:00Z")
        second = plan_compliance_actions(
            self.expected,
            [],
            now="2026-09-04T16:05:00Z",
            workflow_execution_id="different-execution",
        )
        first_ids = {item["record"]["violation_id"] for item in first if item["action_type"] == "upsert_violation"}
        second_ids = {item["record"]["violation_id"] for item in second if item["action_type"] == "upsert_violation"}
        self.assertEqual(first_ids, second_ids)

    def test_late_checkin_resolves_open_violation_without_editing_checkin(self) -> None:
        violation_action = next(item for item in self.plan("2026-09-04T16:01:00Z") if item["action_type"] == "upsert_violation")
        record = violation_action["record"]
        checkin = {
            "checkin_id": "mm-alice|2026-09-04|EOD",
            "user_id": record["user_id"],
            "cycle_date": record["cycle_date"],
            "checkin_type": "EOD",
        }
        actions = plan_compliance_actions(
            self.expected,
            [checkin],
            now="2026-09-04T16:30:00Z",
            workflow_execution_id="exec-2",
            violations=[record],
        )
        resolution = next(item for item in actions if item["action_type"] == "resolve_violation")
        self.assertEqual(resolution["resolved_by_checkin_id"], checkin["checkin_id"])
        self.assertNotIn("checkin_patch", resolution)

    def test_escalation_is_one_digest_per_pod(self) -> None:
        actions = self.plan("2026-09-05T16:00:00Z")
        digests = [item for item in actions if item["action_type"] == "escalation_digest"]
        self.assertEqual(len(digests), 1)
        self.assertEqual(digests[0]["pod_id"], "pod-nails")
        self.assertEqual(digests[0]["missing_count"], 2)

    def test_suppressed_members_never_receive_actions(self) -> None:
        suppressed = expectations(holidays=[{"date": "2026-09-04", "scope": "global"}])
        actions = plan_compliance_actions(
            suppressed,
            [],
            now="2026-09-06T00:00:00Z",
            workflow_execution_id="exec-suppressed",
        )
        self.assertEqual(actions, [])


class WeeklyRollupTests(unittest.TestCase):
    def test_rollup_reconciles_expected_submissions(self) -> None:
        expected = [item for item in expectations() if item["checkin_type"] == "EOD"]
        checkins = [
            {
                "checkin_id": "a",
                "user_id": "mm-alice",
                "pod_id": "pod-nails",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "sla_status": "on_time",
                "has_proof": True,
                "blocked_count": 1,
            }
        ]
        result = weekly_rollup(expected, checkins, period_start="2026-09-01", period_end="2026-09-07")
        nails = next(item for item in result if item["pod_id"] == "pod-nails")
        self.assertEqual(nails["expected_count"], 2)
        self.assertEqual(nails["submitted_count"], 1)
        self.assertEqual(nails["submission_rate"], 0.5)
        self.assertEqual(nails["proof_attach_rate"], 1.0)

    def test_rollup_deduplicates_same_checkin_key(self) -> None:
        expected = [item for item in expectations() if item["user_id"] == "mm-alice" and item["checkin_type"] == "EOD"]
        base = {
            "user_id": "mm-alice",
            "pod_id": "pod-nails",
            "cycle_date": "2026-09-04",
            "checkin_type": "EOD",
            "sla_status": "late",
            "has_proof": False,
            "blocked_count": 0,
        }
        result = weekly_rollup(expected, [dict(base, checkin_id="one"), dict(base, checkin_id="two")], period_start="2026-09-04", period_end="2026-09-04")
        self.assertEqual(result[0]["submitted_count"], 1)

    def test_rollup_ignores_submission_without_expected_roster_entry(self) -> None:
        unexpected = {
            "user_id": "not-expected",
            "pod_id": "pod-other",
            "cycle_date": "2026-09-04",
            "checkin_type": "ADHOC",
            "sla_status": "on_time",
            "has_proof": False,
            "blocked_count": 0,
        }
        self.assertEqual(
            weekly_rollup([], [unexpected], period_start="2026-09-04", period_end="2026-09-04"),
            [],
        )

    def test_rollup_rejects_long_window(self) -> None:
        with self.assertRaisesRegex(ComplianceError, "at most seven"):
            weekly_rollup([], [], period_start="2026-09-01", period_end="2026-09-10")


if __name__ == "__main__":
    unittest.main()
