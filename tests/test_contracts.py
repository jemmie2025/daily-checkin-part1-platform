from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_contracts.py"
SPEC = importlib.util.spec_from_file_location("validate_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load_event(name: str) -> dict:
    path = ROOT / "contracts" / "events" / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class EventContractTests(unittest.TestCase):
    def test_json_schema_closes_event_specific_outcomes(self) -> None:
        schema = json.loads((ROOT / "contracts" / "events" / "checkin-event.v1.schema.json").read_text(encoding="utf-8"))
        opened = load_event("checkin.opened")
        opened["outcome"]["task_count"] = 1
        with self.assertRaisesRegex(validator.ContractError, "unknown fields"):
            validator.validate_schema_instance(opened, schema)

    def test_all_canonical_examples_are_valid(self) -> None:
        for name in (
            "checkin.opened",
            "checkin.submitted",
            "checkin.rejected",
            "checkin.cancelled",
        ):
            with self.subTest(name=name):
                validator.validate_event(load_event(name))

    def test_opened_event_must_be_gateway_telemetry(self) -> None:
        event = load_event("checkin.opened")
        event["source"] = "n8n_submit_handler"
        with self.assertRaisesRegex(validator.ContractError, "APISIX"):
            validator.validate_event(event)

    def test_opened_event_enforces_latency_budget(self) -> None:
        event = load_event("checkin.opened")
        event["outcome"]["latency_ms"] = 2000
        with self.assertRaisesRegex(validator.ContractError, "latency"):
            validator.validate_event(event)

    def test_rejected_event_requires_rule_ids(self) -> None:
        event = load_event("checkin.rejected")
        event["outcome"]["rule_ids"] = []
        with self.assertRaisesRegex(validator.ContractError, "rule_ids"):
            validator.validate_event(event)

    def test_private_payload_is_rejected_from_telemetry(self) -> None:
        event = load_event("checkin.submitted")
        event["outcome"]["tasks_md"] = "- confidential task"
        with self.assertRaisesRegex(validator.ContractError, "private"):
            validator.validate_event(event)

    def test_task_counts_cannot_exceed_total(self) -> None:
        event = load_event("checkin.submitted")
        event["outcome"]["task_count"] = 1
        with self.assertRaisesRegex(validator.ContractError, "counts"):
            validator.validate_event(event)


class IdempotencyTests(unittest.TestCase):
    def test_violation_id_is_deterministic(self) -> None:
        first = validator.violation_id("user-1", "2026-09-04")
        second = validator.violation_id("user-1", "2026-09-04")
        self.assertEqual(first, second)

    def test_violation_id_changes_for_cycle(self) -> None:
        first = validator.violation_id("user-1", "2026-09-04")
        second = validator.violation_id("user-1", "2026-09-05")
        self.assertNotEqual(first, second)

    def test_dlq_id_is_deterministic_per_failure_stage(self) -> None:
        first = validator.dlq_id("execution-99", "baserow_checkins_write")
        second = validator.dlq_id("execution-99", "baserow_checkins_write")
        other = validator.dlq_id("execution-99", "event_dispatch")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)


class OperationalRecordTests(unittest.TestCase):
    def test_all_operational_fixtures_match_contracts(self) -> None:
        for fixture_path, schema_path in validator.RECORD_FIXTURES.items():
            with self.subTest(fixture=fixture_path.name):
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                validator.validate_flat_record(fixture, schema)

    def test_operational_fixture_ids_are_canonical(self) -> None:
        violation = json.loads(
            (ROOT / "contracts" / "baserow" / "examples" / "checkin-violation.json").read_text(
                encoding="utf-8"
            )
        )
        dlq = json.loads(
            (ROOT / "contracts" / "baserow" / "examples" / "checkin-dlq.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            violation["violation_id"],
            validator.violation_id(
                violation["user_id"],
                violation["cycle_date"],
                violation["checkin_type"],
                violation["rule_id"],
            ),
        )
        self.assertEqual(
            dlq["dlq_id"],
            validator.dlq_id(dlq["source_execution_id"], dlq["failure_stage"]),
        )

    def test_dlq_requires_three_attempts(self) -> None:
        fixture_path = ROOT / "contracts" / "baserow" / "examples" / "checkin-dlq.json"
        schema_path = ROOT / "contracts" / "baserow" / "checkin-dlq.v1.schema.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        fixture["attempt_count"] = 2
        with self.assertRaisesRegex(validator.ContractError, "minimum"):
            validator.validate_flat_record(fixture, schema)


class OwnershipTests(unittest.TestCase):
    def test_write_authority_is_exclusive(self) -> None:
        ownership = validator.yaml.safe_load(
            (ROOT / "contracts" / "ownership.yaml").read_text(encoding="utf-8")
        )
        part_1 = ownership["part_1_platform"]
        part_2 = ownership["part_2_application"]
        self.assertIn("checkin_violations_writes", part_1["owns"])
        self.assertIn("checkin_dlq_writes", part_1["owns"])
        self.assertIn("grafana_clickhouse_dashboard", part_1["owns"])
        self.assertNotIn("superset_dashboard", part_1["owns"])
        self.assertIn("write_checkins", part_1["must_not"])
        self.assertIn("checkins_writes", part_2["owns"])
        self.assertIn("write_checkin_violations", part_2["must_not"])
        self.assertIn("write_checkin_dlq", part_2["must_not"])


if __name__ == "__main__":
    unittest.main()
