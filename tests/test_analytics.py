from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from checkin_platform.analytics import AnalyticsError, EventLedger, flatten_event, reconcile_metrics


ROOT = Path(__file__).resolve().parents[1]


def event(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "events" / "examples" / f"{name}.json").read_text(encoding="utf-8"))


class FlatteningTests(unittest.TestCase):
    def test_all_four_event_types_flatten(self) -> None:
        for name in ("checkin.opened", "checkin.submitted", "checkin.rejected", "checkin.cancelled"):
            with self.subTest(name=name):
                row = flatten_event(event(name))
                self.assertEqual(row["event_name"], name)
                self.assertEqual(len(row["payload_hash"]), 64)

    def test_flat_row_contains_no_nested_or_private_payload(self) -> None:
        row = flatten_event(event("checkin.submitted"))
        self.assertNotIn("user", row)
        self.assertNotIn("pod", row)
        self.assertNotIn("outcome", row)
        self.assertNotIn("tasks_md", row)
        self.assertNotIn("proof_links", row)

    def test_private_field_fails_closed(self) -> None:
        broken = event("checkin.submitted")
        broken["outcome"]["raw_submission"] = "restricted"
        with self.assertRaisesRegex(AnalyticsError, "forbidden fields"):
            flatten_event(broken)

    def test_unknown_top_level_field_fails_closed(self) -> None:
        broken = event("checkin.opened")
        broken["extra"] = "no"
        with self.assertRaisesRegex(AnalyticsError, "top-level"):
            flatten_event(broken)

    def test_payload_hash_is_key_order_independent(self) -> None:
        original = event("checkin.opened")
        reordered = dict(reversed(list(original.items())))
        self.assertEqual(flatten_event(original)["payload_hash"], flatten_event(reordered)["payload_hash"])


class DeduplicationTests(unittest.TestCase):
    def test_first_event_returns_202_and_duplicate_returns_200(self) -> None:
        ledger = EventLedger()
        first_status, _ = ledger.accept(event("checkin.submitted"))
        second_status, _ = ledger.accept(event("checkin.submitted"))
        self.assertEqual((first_status, second_status), (202, 200))
        self.assertEqual(len(ledger.rows()), 1)

    def test_same_id_with_different_payload_is_rejected(self) -> None:
        ledger = EventLedger()
        original = event("checkin.submitted")
        ledger.accept(original)
        conflict = copy.deepcopy(original)
        conflict["outcome"]["blocked_count"] = 0
        with self.assertRaisesRegex(AnalyticsError, "different payload"):
            ledger.accept(conflict)

    def test_distinct_event_ids_are_retained(self) -> None:
        ledger = EventLedger()
        for name in ("checkin.opened", "checkin.submitted", "checkin.rejected", "checkin.cancelled"):
            ledger.accept(event(name))
        self.assertEqual(len(ledger.rows()), 4)


class ReconciliationTests(unittest.TestCase):
    def test_submission_rate_uses_expected_roster_denominator(self) -> None:
        submitted = event("checkin.submitted")
        expected = [
            {
                "user_id": "mm-user-1001",
                "pod_id": "pod-nails-squad",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "attendance_state": "expected",
            },
            {
                "user_id": "mm-user-1009",
                "pod_id": "pod-nails-squad",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "attendance_state": "expected",
            },
            {
                "user_id": "mm-user-leave",
                "pod_id": "pod-nails-squad",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "attendance_state": "approved_leave",
            },
        ]
        metrics = reconcile_metrics([submitted], expected)
        self.assertEqual(metrics[0]["expected_count"], 2)
        self.assertEqual(metrics[0]["submitted_count"], 1)
        self.assertEqual(metrics[0]["submission_rate"], 0.5)

    def test_duplicate_events_do_not_inflate_metrics(self) -> None:
        submitted = event("checkin.submitted")
        expected = [
            {
                "user_id": "mm-user-1001",
                "pod_id": "pod-nails-squad",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "attendance_state": "expected",
            }
        ]
        metrics = reconcile_metrics([submitted, copy.deepcopy(submitted)], expected)
        self.assertEqual(metrics[0]["submitted_count"], 1)
        self.assertEqual(metrics[0]["blocked_task_count"], 1)

    def test_proof_and_blocked_metrics_reconcile(self) -> None:
        submitted = event("checkin.submitted")
        expected = [
            {
                "user_id": "mm-user-1001",
                "pod_id": "pod-nails-squad",
                "cycle_date": "2026-09-04",
                "checkin_type": "EOD",
                "attendance_state": "expected",
            }
        ]
        metrics = reconcile_metrics([submitted], expected)[0]
        self.assertEqual(metrics["proof_attach_rate"], 1.0)
        self.assertEqual(metrics["blocked_task_count"], 1)
        self.assertEqual(metrics["median_submit_latency_ms"], 426)


if __name__ == "__main__":
    unittest.main()
