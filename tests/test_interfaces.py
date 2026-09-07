from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_contracts_interfaces", ROOT / "scripts" / "validate_contracts.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def fixture_schema(fixture_name: str, schema_name: str, group: str) -> tuple[dict, dict]:
    fixture = json.loads((ROOT / "contracts" / group / "examples" / fixture_name).read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "contracts" / group / schema_name).read_text(encoding="utf-8"))
    return fixture, schema


class InterfaceSchemaTests(unittest.TestCase):
    def test_part1_baserow_idempotency_fields_are_unique(self) -> None:
        import yaml

        field_map = yaml.safe_load((ROOT / "baserow" / "field-map.yaml").read_text(encoding="utf-8"))
        self.assertTrue(field_map["tables"]["checkin_violations"]["fields"]["violation_id"]["unique"])
        self.assertTrue(field_map["tables"]["checkin_dlq"]["fields"]["dlq_id"]["unique"])
        self.assertIn("BASEROW_DLQ_REPLAY_VIEW_ID=", (ROOT / ".env.example").read_text(encoding="utf-8"))

    def test_all_nested_interface_examples_validate(self) -> None:
        for fixture_path, schema_path in validator.NESTED_FIXTURES.items():
            with self.subTest(fixture=fixture_path.name):
                validator.validate_schema_instance(
                    json.loads(fixture_path.read_text(encoding="utf-8")),
                    json.loads(schema_path.read_text(encoding="utf-8")),
                )

    def test_snapshot_rejects_duplicate_action_ids(self) -> None:
        fixture, schema = fixture_schema(
            "compliance-snapshot.json",
            "compliance-snapshot.v1.schema.json",
            "compliance",
        )
        fixture["existing_action_ids"] = ["nudge-one", "nudge-one"]
        with self.assertRaisesRegex(validator.ContractError, "unique"):
            validator.validate_schema_instance(fixture, schema)

    def test_snapshot_rejects_bad_local_sla_time(self) -> None:
        fixture, schema = fixture_schema(
            "compliance-snapshot.json",
            "compliance-snapshot.v1.schema.json",
            "compliance",
        )
        fixture["sla_rules"][0]["local_due_time"] = "29:91"
        with self.assertRaisesRegex(validator.ContractError, "pattern"):
            validator.validate_schema_instance(fixture, schema)

    def test_pod_holiday_requires_pod_id(self) -> None:
        fixture, schema = fixture_schema(
            "compliance-snapshot.json",
            "compliance-snapshot.v1.schema.json",
            "compliance",
        )
        fixture["holidays"] = [{"date": "2026-09-04", "scope": "pod"}]
        with self.assertRaisesRegex(validator.ContractError, "missing fields"):
            validator.validate_schema_instance(fixture, schema)

    def test_snapshot_minimizes_checkin_and_calendar_rows(self) -> None:
        fixture, schema = fixture_schema(
            "compliance-snapshot.json",
            "compliance-snapshot.v1.schema.json",
            "compliance",
        )
        fixture["checkins"] = [{
            "checkin_id": "user|2026-09-04|EOD",
            "user_id": "user",
            "pod_id": "pod",
            "cycle_date": "2026-09-04",
            "checkin_type": "EOD",
            "raw_submission": "must not enter compliance snapshot",
        }]
        with self.assertRaisesRegex(validator.ContractError, "unknown fields"):
            validator.validate_schema_instance(fixture, schema)

    def test_failure_context_rejects_unknown_stage(self) -> None:
        fixture, schema = fixture_schema(
            "submit-failure-context.json",
            "submit-failure-context.v1.schema.json",
            "reliability",
        )
        fixture["failure_stage"] = "unknown"
        with self.assertRaisesRegex(validator.ContractError, "allowed"):
            validator.validate_schema_instance(fixture, schema)

    def test_failure_context_rejects_extra_fields(self) -> None:
        fixture, schema = fixture_schema(
            "submit-failure-context.json",
            "submit-failure-context.v1.schema.json",
            "reliability",
        )
        fixture["token"] = "must-not-pass"
        with self.assertRaisesRegex(validator.ContractError, "unknown fields"):
            validator.validate_schema_instance(fixture, schema)

    def test_replay_request_requires_unique_ordered_step_names(self) -> None:
        fixture, schema = fixture_schema("replay-request.json", "replay-request.v1.schema.json", "reliability")
        fixture["replay_steps"] = ["ensure_event", "ensure_event"]
        with self.assertRaisesRegex(validator.ContractError, "unique"):
            validator.validate_schema_instance(fixture, schema)

    def test_replay_response_cannot_change_status(self) -> None:
        fixture, schema = fixture_schema("replay-response.json", "replay-response.v1.schema.json", "reliability")
        fixture["status"] = "partial"
        with self.assertRaisesRegex(validator.ContractError, "const"):
            validator.validate_schema_instance(fixture, schema)

    def test_contract_fixture_changes_do_not_mutate_original(self) -> None:
        fixture, _ = fixture_schema("replay-request.json", "replay-request.v1.schema.json", "reliability")
        copied = copy.deepcopy(fixture)
        copied["raw_submission"] = "changed"
        self.assertNotEqual(copied, fixture)


if __name__ == "__main__":
    unittest.main()
