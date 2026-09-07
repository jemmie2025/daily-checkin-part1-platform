"""Stable identifiers shared by compliance, DLQ, and analytics code."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _digest(prefix: str, *parts: object, length: int = 32) -> str:
    canonical = "|".join(str(part) for part in parts)
    value = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{value}"


def expectation_id(user_id: str, cycle_date: str, checkin_type: str, sla_code: str) -> str:
    return "|".join((user_id, cycle_date, checkin_type, sla_code))


def violation_id(user_id: str, cycle_date: str, checkin_type: str = "EOD", rule_id: str = "PI-6") -> str:
    return _digest("viol_", user_id, cycle_date, checkin_type, rule_id)


def nudge_id(expectation: str) -> str:
    return _digest("nudge_", expectation)


def escalation_id(pod_id: str, cycle_date: str, checkin_type: str) -> str:
    return _digest("esc_", pod_id, cycle_date, checkin_type)


def resolution_id(violation: str, checkin_id: str) -> str:
    return _digest("resolve_", violation, checkin_id)


def rollup_id(pod_id: str, period_start: str, period_end: str) -> str:
    return _digest("rollup_", pod_id, period_start, period_end)


def dlq_id(source_execution_id: str, failure_stage: str) -> str:
    return _digest("dlq_", source_execution_id, failure_stage)


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
