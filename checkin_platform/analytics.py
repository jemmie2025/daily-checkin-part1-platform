"""Privacy-minimized event flattening, deduplication, and metric reconciliation."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Iterable, Mapping

from .ids import payload_hash


FORBIDDEN_KEYS = {
    "user_name",
    "tasks",
    "tasks_md",
    "tasks_json",
    "proof_link",
    "proof_links",
    "raw_submission",
    "nonce",
    "state",
    "token",
}


class AnalyticsError(ValueError):
    """Raised when telemetry would violate the analytics contract."""


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


def flatten_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten only contract-approved fields for ClickHouse JSONEachRow."""

    source = deepcopy(dict(event))
    leaked = _keys(source) & FORBIDDEN_KEYS
    if leaked:
        raise AnalyticsError(f"telemetry contains forbidden fields: {sorted(leaked)}")
    required = {
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
    if set(source) != required:
        raise AnalyticsError("event top-level fields do not match contract v1")
    outcome = source["outcome"]
    trace = source["trace"]
    flattened = {
        "event_id": source["event_id"],
        "event_name": source["event_name"],
        "event_version": source["event_version"],
        "occurred_at": source["occurred_at"],
        "correlation_id": source["correlation_id"],
        "source": source["source"],
        "user_id": source["user"]["user_id"],
        "pod_id": source["pod"]["pod_id"],
        "cycle_date": source["cycle"]["cycle_date"],
        "checkin_type": source["cycle"]["checkin_type"],
        "sla_code": source["cycle"]["sla_code"],
        "dialog_version": source["dialog_version"],
        "latency_ms": outcome["latency_ms"],
        "sla_status": outcome.get("sla_status"),
        "task_count": outcome.get("task_count"),
        "done_count": outcome.get("done_count"),
        "blocked_count": outcome.get("blocked_count"),
        "has_proof": outcome.get("has_proof"),
        "rule_ids": list(outcome.get("rule_ids", [])),
        "request_id": trace["request_id"],
        "execution_id": trace.get("execution_id"),
    }
    flattened["payload_hash"] = payload_hash(source)
    return flattened


class EventLedger:
    """In-memory model of event-id deduplication used by deterministic tests."""

    def __init__(self) -> None:
        self._events: dict[str, dict[str, Any]] = {}

    def accept(self, event: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        flattened = flatten_event(event)
        event_id = str(flattened["event_id"])
        existing = self._events.get(event_id)
        if existing:
            if existing["payload_hash"] != flattened["payload_hash"]:
                raise AnalyticsError("event_id was reused with a different payload")
            return 200, deepcopy(existing)
        self._events[event_id] = deepcopy(flattened)
        return 202, deepcopy(flattened)

    def rows(self) -> list[dict[str, Any]]:
        return [deepcopy(self._events[key]) for key in sorted(self._events)]


def reconcile_metrics(
    events: Iterable[Mapping[str, Any]], expectations: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Reproduce Grafana reporting metrics from deduplicated event fixtures."""

    unique_events: dict[str, Mapping[str, Any]] = {}
    for event in events:
        flattened = flatten_event(event) if "user" in event else dict(event)
        event_id = str(flattened["event_id"])
        previous = unique_events.get(event_id)
        if previous and previous.get("payload_hash") != flattened.get("payload_hash"):
            raise AnalyticsError("conflicting duplicate event_id")
        unique_events[event_id] = flattened

    expected_groups: dict[tuple[str, str, str], set[str]] = {}
    for item in expectations:
        if item.get("attendance_state") != "expected":
            continue
        key = (str(item["pod_id"]), str(item["cycle_date"]), str(item["checkin_type"]))
        expected_groups.setdefault(key, set()).add(str(item["user_id"]))

    event_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for event in unique_events.values():
        date.fromisoformat(str(event["cycle_date"]))
        key = (str(event["pod_id"]), str(event["cycle_date"]), str(event["checkin_type"]))
        event_groups.setdefault(key, []).append(event)

    output: list[dict[str, Any]] = []
    for key in sorted(set(expected_groups) | set(event_groups)):
        pod_id, cycle_date, checkin_type = key
        rows = event_groups.get(key, [])
        submitted = [row for row in rows if row["event_name"] == "checkin.submitted"]
        rejected = [row for row in rows if row["event_name"] == "checkin.rejected"]
        opened = [row for row in rows if row["event_name"] == "checkin.opened"]
        expected_count = len(expected_groups.get(key, set()))
        submission_users = {str(row["user_id"]) for row in submitted}
        eligible_submissions = submission_users & expected_groups.get(key, set())
        latencies = sorted(int(row["latency_ms"]) for row in submitted)
        midpoint = len(latencies) // 2
        if not latencies:
            median_latency = 0
        elif len(latencies) % 2:
            median_latency = latencies[midpoint]
        else:
            median_latency = round((latencies[midpoint - 1] + latencies[midpoint]) / 2)
        output.append(
            {
                "pod_id": pod_id,
                "cycle_date": cycle_date,
                "checkin_type": checkin_type,
                "expected_count": expected_count,
                "submitted_count": len(eligible_submissions),
                "submission_rate": round(len(eligible_submissions) / expected_count, 4) if expected_count else 0.0,
                "opened_count": len(opened),
                "rejected_count": len(rejected),
                "median_submit_latency_ms": median_latency,
                "proof_attach_rate": round(
                    sum(bool(row.get("has_proof")) for row in submitted) / len(submitted), 4
                ) if submitted else 0.0,
                "blocked_task_count": sum(int(row.get("blocked_count") or 0) for row in submitted),
            }
        )
    return output
