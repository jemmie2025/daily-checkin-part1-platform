#!/usr/bin/env python3
"""Dependency-free validation for Task #5585 Part 1 contracts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "contracts" / "events" / "examples"
EVENT_SCHEMA = ROOT / "contracts" / "events" / "checkin-event.v1.schema.json"
RECORD_FIXTURES = {
    ROOT / "contracts" / "baserow" / "examples" / "checkin-violation.json":
        ROOT / "contracts" / "baserow" / "checkin-violation.v1.schema.json",
    ROOT / "contracts" / "baserow" / "examples" / "checkin-dlq.json":
        ROOT / "contracts" / "baserow" / "checkin-dlq.v1.schema.json",
    ROOT / "contracts" / "compliance" / "examples" / "expected-checkin.json":
        ROOT / "contracts" / "compliance" / "expected-checkin.v1.schema.json",
    ROOT / "contracts" / "apisix" / "examples" / "apisix-opened-access-log.json":
        ROOT / "contracts" / "apisix" / "apisix-access-log.v1.schema.json",
    ROOT / "contracts" / "analytics" / "examples" / "checkin-violation-fact.json":
        ROOT / "contracts" / "analytics" / "checkin-violation-fact.v1.schema.json",
    ROOT / "contracts" / "analytics" / "examples" / "checkin-dlq-lifecycle.json":
        ROOT / "contracts" / "analytics" / "checkin-dlq-lifecycle.v1.schema.json",
}
NESTED_FIXTURES = {
    ROOT / "contracts" / "compliance" / "examples" / "compliance-snapshot.json":
        ROOT / "contracts" / "compliance" / "compliance-snapshot.v1.schema.json",
    ROOT / "contracts" / "reliability" / "examples" / "submit-failure-context.json":
        ROOT / "contracts" / "reliability" / "submit-failure-context.v1.schema.json",
    ROOT / "contracts" / "reliability" / "examples" / "replay-request.json":
        ROOT / "contracts" / "reliability" / "replay-request.v1.schema.json",
    ROOT / "contracts" / "reliability" / "examples" / "replay-response.json":
        ROOT / "contracts" / "reliability" / "replay-response.v1.schema.json",
}
EVENT_NAMES = {
    "checkin.opened",
    "checkin.submitted",
    "checkin.rejected",
    "checkin.cancelled",
}
TOP_LEVEL_FIELDS = {
    "event_id",
    "event_name",
    "event_version",
    "occurred_at",
    "correlation_id",
    "source",
    "user",
    "pod",
    "cycle",
    "dialog_version",
    "outcome",
    "trace",
}
FORBIDDEN_TELEMETRY_FIELDS = {
    "user_name",
    "tasks",
    "tasks_md",
    "tasks_json",
    "proof_link",
    "proof_links",
    "raw_submission",
    "state",
    "nonce",
    "token",
}
RULE_ID_PATTERN = re.compile(r"^(FMT-[1-8]|PI-[0-9]+)$")
IGNORED_DIRECTORIES = {"build", "__pycache__", ".git"}


class ContractError(ValueError):
    """Raised when a versioned contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _parse_utc(value: str, field: str) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), f"{field} must end in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be RFC3339") from exc
    _require(parsed.utcoffset() is not None, f"{field} must include UTC offset")
    return parsed


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be RFC3339") from exc
    _require(parsed.utcoffset() is not None, f"{field} must include an offset")
    return parsed


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def validate_event(event: dict[str, Any]) -> None:
    _require(set(event) == TOP_LEVEL_FIELDS, "event top-level fields must match v1 exactly")
    _require(not (_walk_keys(event) & FORBIDDEN_TELEMETRY_FIELDS), "event contains forbidden private fields")

    try:
        uuid.UUID(event["event_id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContractError("event_id must be a UUID") from exc

    _require(event["event_name"] in EVENT_NAMES, "unsupported event_name")
    _require(event["event_version"] == 1, "event_version must be 1")
    _parse_utc(event["occurred_at"], "occurred_at")
    correlation_id = event["correlation_id"]
    _require(8 <= len(correlation_id) <= 128, "invalid correlation_id")
    _require(re.fullmatch(r"[A-Za-z0-9._:-]+", correlation_id) is not None, "unsafe correlation_id")
    _require(event["dialog_version"] == "checkin_v1", "invalid dialog_version")

    _require(set(event["user"]) == {"user_id"}, "telemetry user must contain user_id only")
    _require(bool(event["user"]["user_id"]), "user_id is required")
    _require(set(event["pod"]) == {"pod_id"}, "telemetry pod must contain pod_id only")
    _require(bool(event["pod"]["pod_id"]), "pod_id is required")

    cycle = event["cycle"]
    _require(set(cycle) == {"cycle_date", "checkin_type", "sla_code"}, "invalid cycle fields")
    try:
        _require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", cycle["cycle_date"]) is not None, "cycle_date must use YYYY-MM-DD")
        datetime.strptime(cycle["cycle_date"], "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise ContractError("cycle_date must use YYYY-MM-DD") from exc
    _require(cycle["checkin_type"] in {"SOD", "EOD", "ADHOC"}, "invalid checkin_type")
    _require(bool(cycle["sla_code"]), "sla_code is required")

    outcome = event["outcome"]
    _require(isinstance(outcome.get("latency_ms"), int) and outcome["latency_ms"] >= 0, "invalid latency_ms")
    _require(set(event["trace"]) >= {"request_id"}, "request_id is required")
    _require(set(event["trace"]) <= {"request_id", "execution_id"}, "invalid trace fields")

    if event["event_name"] == "checkin.opened":
        _require(event["source"] == "apisix_telemetry", "opened events must come from APISIX telemetry")
        _require(outcome["latency_ms"] < 2000, "opened example exceeds latency budget")
    else:
        _require(event["source"] == "n8n_submit_handler", "submit events must come from submit handler")

    if event["event_name"] == "checkin.submitted":
        required = {"latency_ms", "sla_status", "task_count", "done_count", "blocked_count", "has_proof"}
        _require(set(outcome) == required, "submitted outcome fields do not match v1")
        _require(outcome["sla_status"] in {"on_time", "late"}, "invalid sla_status")
        for field in ("task_count", "done_count", "blocked_count"):
            _require(isinstance(outcome[field], int) and 0 <= outcome[field] <= 20, f"invalid {field}")
        _require(outcome["done_count"] + outcome["blocked_count"] <= outcome["task_count"], "counts exceed task_count")
        _require(isinstance(outcome["has_proof"], bool), "has_proof must be boolean")

    if event["event_name"] == "checkin.rejected":
        _require(set(outcome) == {"latency_ms", "rule_ids"}, "rejected outcome fields do not match v1")
        _require(bool(outcome["rule_ids"]), "rejected event requires rule_ids")
        _require(len(outcome["rule_ids"]) == len(set(outcome["rule_ids"])), "rule_ids must be unique")
        _require(all(RULE_ID_PATTERN.fullmatch(item) for item in outcome["rule_ids"]), "invalid rule_id")

    if event["event_name"] == "checkin.cancelled":
        _require(set(outcome) == {"latency_ms"}, "cancelled outcome fields do not match v1")


def _matches_type(value: Any, expected: str) -> bool:
    mappings = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
        "array": lambda item: isinstance(item, list),
        "object": lambda item: isinstance(item, dict),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
    }
    return mappings[expected](value)


def validate_schema_instance(value: Any, rules: dict[str, Any], path: str = "$") -> None:
    """Validate the strict JSON Schema subset used by internal interface fixtures."""

    if "const" in rules:
        _require(value == rules["const"], f"{path} does not match const")
    if "enum" in rules:
        _require(value in rules["enum"], f"{path} is not an allowed value")
    if "type" in rules:
        expected = rules["type"] if isinstance(rules["type"], list) else [rules["type"]]
        _require(any(_matches_type(value, item) for item in expected), f"{path} has invalid type")
    if value is None:
        return
    if isinstance(value, dict):
        required = set(rules.get("required", []))
        properties = rules.get("properties", {})
        _require(required <= set(value), f"{path} missing fields: {sorted(required - set(value))}")
        if rules.get("additionalProperties") is False:
            _require(set(value) <= set(properties), f"{path} has unknown fields: {sorted(set(value) - set(properties))}")
        for key, child in value.items():
            if key in properties:
                validate_schema_instance(child, properties[key], f"{path}.{key}")
    if isinstance(value, list):
        _require(len(value) >= rules.get("minItems", 0), f"{path} has too few items")
        _require(len(value) <= rules.get("maxItems", len(value)), f"{path} has too many items")
        if rules.get("uniqueItems"):
            canonical = [json.dumps(item, sort_keys=True) for item in value]
            _require(len(canonical) == len(set(canonical)), f"{path} items must be unique")
        if "items" in rules:
            for index, child in enumerate(value):
                validate_schema_instance(child, rules["items"], f"{path}[{index}]")
    if isinstance(value, str):
        _require(len(value) >= rules.get("minLength", 0), f"{path} is too short")
        _require(len(value) <= rules.get("maxLength", len(value)), f"{path} is too long")
        if "pattern" in rules:
            _require(re.fullmatch(rules["pattern"], value) is not None, f"{path} does not match pattern")
        if rules.get("format") == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                raise ContractError(f"{path} must use YYYY-MM-DD") from exc
        if rules.get("format") == "date-time":
            _parse_datetime(value, path)
    if isinstance(value, int) and not isinstance(value, bool):
        _require(value >= rules.get("minimum", value), f"{path} is below minimum")
        _require(value <= rules.get("maximum", value), f"{path} is above maximum")
    for branch in rules.get("allOf", []):
        condition = branch.get("if")
        applies = condition is None
        if condition is not None:
            try:
                validate_schema_instance(value, condition, path)
                applies = True
            except ContractError:
                applies = False
        if applies and "then" in branch:
            validate_schema_instance(value, branch["then"], path)


def validate_flat_record(record: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate the supported flat subset used by operational record schemas."""

    required = set(schema["required"])
    properties = schema["properties"]
    _require(required <= set(record), f"missing record fields: {sorted(required - set(record))}")
    if schema.get("additionalProperties") is False:
        _require(set(record) <= set(properties), f"unknown record fields: {sorted(set(record) - set(properties))}")

    for name, value in record.items():
        rules = properties[name]
        if "const" in rules:
            _require(value == rules["const"], f"{name} does not match const")
        if "enum" in rules:
            _require(value in rules["enum"], f"{name} is not an allowed value")
        if "pattern" in rules and isinstance(value, str):
            _require(re.fullmatch(rules["pattern"], value) is not None, f"{name} does not match pattern")
        if "type" in rules:
            expected_types = rules["type"] if isinstance(rules["type"], list) else [rules["type"]]
            _require(any(_matches_type(value, item) for item in expected_types), f"{name} has invalid type")
        if value is None:
            continue
        if isinstance(value, str):
            _require(len(value) >= rules.get("minLength", 0), f"{name} is too short")
            _require(len(value) <= rules.get("maxLength", len(value)), f"{name} is too long")
            if rules.get("format") == "date":
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError as exc:
                    raise ContractError(f"{name} must use YYYY-MM-DD") from exc
            if rules.get("format") == "date-time":
                _parse_datetime(value, name)
        if isinstance(value, int) and not isinstance(value, bool):
            _require(value >= rules.get("minimum", value), f"{name} is below minimum")


def validate_repository_hygiene() -> int:
    checked = 0
    text_names = {"Makefile", "VERSION", ".gitignore", ".editorconfig", ".env.example"}
    text_suffixes = {".hcl", ".lua", ".md", ".json", ".yaml", ".yml", ".py", ".txt"}
    for path in sorted(ROOT.rglob("*")):
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        if not path.is_file() or (path.name not in text_names and path.suffix not in text_suffixes):
            continue
        content = path.read_text(encoding="utf-8")
        _require(content.endswith("\n"), f"{path.relative_to(ROOT)} must end with a newline")
        _require(
            not content.endswith("\n\n"),
            f"{path.relative_to(ROOT)} must not end with a blank line",
        )
        for line_number, line in enumerate(content.splitlines(), start=1):
            _require(line == line.rstrip(), f"trailing whitespace: {path.relative_to(ROOT)}:{line_number}")
        checked += 1
    return checked


def violation_id(user_id: str, cycle_date: str, checkin_type: str = "EOD", rule_id: str = "PI-6") -> str:
    canonical = "|".join((user_id, cycle_date, checkin_type, rule_id))
    return "viol_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def dlq_id(source_execution_id: str, failure_stage: str) -> str:
    canonical = "|".join((source_execution_id, failure_stage))
    return "dlq_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def validate_serialized_files() -> tuple[int, int]:
    json_count = 0
    yaml_count = 0
    for path in sorted(ROOT.rglob("*.json")):
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
        json_count += 1
    for pattern in ("*.yaml", "*.yml"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue
            with path.open(encoding="utf-8") as handle:
                yaml.safe_load(handle)
            yaml_count += 1
    return json_count, yaml_count


def main() -> int:
    try:
        json_count, yaml_count = validate_serialized_files()
        examples = sorted(EVENTS_DIR.glob("*.json"))
        _require(len(examples) == 4, "exactly four canonical event examples are required")
        event_schema = json.loads(EVENT_SCHEMA.read_text(encoding="utf-8"))
        for path in examples:
            with path.open(encoding="utf-8") as handle:
                event = json.load(handle)
            validate_event(event)
            validate_schema_instance(event, event_schema)
            _require(path.stem == event["event_name"], f"{path.name} does not match event_name")
        for fixture_path, schema_path in RECORD_FIXTURES.items():
            with fixture_path.open(encoding="utf-8") as handle:
                fixture = json.load(handle)
            with schema_path.open(encoding="utf-8") as handle:
                schema = json.load(handle)
            validate_flat_record(fixture, schema)
            if fixture_path.name == "checkin-violation.json":
                expected_id = violation_id(
                    fixture["user_id"], fixture["cycle_date"], fixture["checkin_type"], fixture["rule_id"]
                )
                _require(fixture["violation_id"] == expected_id, "violation fixture id is not deterministic")
            if fixture_path.name == "checkin-dlq.json":
                expected_id = dlq_id(fixture["source_execution_id"], fixture["failure_stage"])
                _require(fixture["dlq_id"] == expected_id, "DLQ fixture id is not deterministic")
                expected_replay_key = f'{fixture["source_execution_id"]}|{fixture["failure_stage"]}'
                _require(fixture["replay_key"] == expected_replay_key, "DLQ replay_key is not canonical")
        for fixture_path, schema_path in NESTED_FIXTURES.items():
            with fixture_path.open(encoding="utf-8") as handle:
                fixture = json.load(handle)
            with schema_path.open(encoding="utf-8") as handle:
                schema = json.load(handle)
            validate_schema_instance(fixture, schema)
        text_count = validate_repository_hygiene()
    except (ContractError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"PASS: {json_count} JSON files parsed")
    print(f"PASS: {yaml_count} YAML files parsed")
    print(f"PASS: {len(examples)} event contracts validated")
    print(f"PASS: {len(RECORD_FIXTURES) + len(NESTED_FIXTURES)} operational record contracts validated")
    print(f"PASS: {text_count} text files passed repository hygiene checks")
    print("PASS: privacy, source, latency, and idempotency invariants validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
