"""Pure compliance planner used as executable specification for the n8n worker."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .ids import escalation_id, expectation_id, nudge_id, resolution_id, rollup_id, violation_id


UTC = timezone.utc
EXPECTED_STATES = {"expected", "approved_leave", "holiday", "inactive"}


class ComplianceError(ValueError):
    """Raised when roster, calendar, SLA, or check-in input is unsafe."""


def _date(value: str | date, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ComplianceError(f"{field} must use YYYY-MM-DD") from exc


def _aware_datetime(value: str | datetime, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ComplianceError(f"{field} must be RFC3339") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ComplianceError(f"{field} must be an aware datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ComplianceError(f"{field} must include a timezone offset")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _local_due(cycle_day: date, timezone_name: str, local_due_time: str) -> datetime:
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ComplianceError(f"unknown IANA timezone: {timezone_name}") from exc
    try:
        hour_text, minute_text = local_due_time.split(":", maxsplit=1)
        local_time = time(hour=int(hour_text), minute=int(minute_text))
    except (ValueError, TypeError) as exc:
        raise ComplianceError("local_due_time must use HH:MM") from exc
    return datetime.combine(cycle_day, local_time, tzinfo=local_zone).astimezone(UTC)


def _is_active(member: Mapping[str, Any], cycle_day: date) -> bool:
    if member.get("active") is False:
        return False
    active_from = _date(member.get("active_from", "1900-01-01"), "active_from")
    active_until_raw = member.get("active_until")
    active_until = _date(active_until_raw, "active_until") if active_until_raw else date.max
    return active_from <= cycle_day <= active_until


def _on_approved_leave(user_id: str, cycle_day: date, leave_records: Iterable[Mapping[str, Any]]) -> bool:
    for record in leave_records:
        if record.get("user_id") != user_id or record.get("status") != "approved":
            continue
        if _date(record["start_date"], "leave.start_date") <= cycle_day <= _date(
            record["end_date"], "leave.end_date"
        ):
            return True
    return False


def _is_holiday(pod_id: str, cycle_day: date, holidays: Iterable[Mapping[str, Any]]) -> bool:
    for holiday in holidays:
        if _date(holiday["date"], "holiday.date") != cycle_day:
            continue
        scope = holiday.get("scope", "global")
        if scope == "global" or (scope == "pod" and holiday.get("pod_id") == pod_id):
            return True
    return False


def build_expectations(
    roster: Iterable[Mapping[str, Any]],
    cycle_date: str | date,
    sla_rules: Iterable[Mapping[str, Any]],
    *,
    leave_records: Iterable[Mapping[str, Any]] = (),
    holidays: Iterable[Mapping[str, Any]] = (),
    roster_source_version: str,
) -> list[dict[str, Any]]:
    """Build deterministic user-local expectations with absence suppression."""

    cycle_day = _date(cycle_date, "cycle_date")
    members = list(roster)
    rules = list(sla_rules)
    leave = list(leave_records)
    holiday_rows = list(holidays)
    if not roster_source_version or len(roster_source_version) > 128:
        raise ComplianceError("roster_source_version is required and must be at most 128 characters")

    identities: set[str] = set()
    expectation_ids: set[str] = set()
    expectations: list[dict[str, Any]] = []
    for member in members:
        required = ("user_id", "user_name", "pod_id", "timezone")
        if any(not member.get(field) for field in required):
            raise ComplianceError("roster member is missing a required identity field")
        user_id = str(member["user_id"])
        if user_id in identities:
            raise ComplianceError(f"duplicate roster user_id: {user_id}")
        identities.add(user_id)

        if not _is_active(member, cycle_day):
            attendance_state = "inactive"
        elif _on_approved_leave(user_id, cycle_day, leave):
            attendance_state = "approved_leave"
        elif _is_holiday(str(member["pod_id"]), cycle_day, holiday_rows):
            attendance_state = "holiday"
        else:
            attendance_state = "expected"

        for rule in rules:
            checkin_type = str(rule.get("checkin_type", ""))
            if checkin_type not in {"SOD", "EOD"}:
                raise ComplianceError("SLA checkin_type must be SOD or EOD")
            rule_pod = rule.get("pod_id")
            if rule_pod and rule_pod != member["pod_id"]:
                continue
            sla_code = str(rule.get("sla_code", ""))
            if not sla_code:
                raise ComplianceError("SLA rule requires sla_code")
            due_at = _local_due(cycle_day, str(member["timezone"]), str(rule.get("local_due_time", "")))
            cycle_text = cycle_day.isoformat()
            identifier = expectation_id(user_id, cycle_text, checkin_type, sla_code)
            if identifier in expectation_ids:
                raise ComplianceError(f"duplicate SLA expectation: {identifier}")
            expectation_ids.add(identifier)
            expectations.append(
                {
                    "expectation_id": identifier,
                    "user_id": user_id,
                    "user_name": str(member["user_name"]),
                    "pod_id": str(member["pod_id"]),
                    "timezone": str(member["timezone"]),
                    "cycle_date": cycle_text,
                    "checkin_type": checkin_type,
                    "sla_code": sla_code,
                    "sla_due_at": _utc_text(due_at),
                    "attendance_state": attendance_state,
                    "roster_source_version": roster_source_version,
                }
            )
    return sorted(expectations, key=lambda item: item["expectation_id"])


def _checkin_key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(record["user_id"]), str(record["cycle_date"]), str(record["checkin_type"])


def _violation_record(
    expectation: Mapping[str, Any], now: datetime, workflow_execution_id: str
) -> dict[str, Any]:
    identifier = violation_id(
        str(expectation["user_id"]),
        str(expectation["cycle_date"]),
        str(expectation["checkin_type"]),
        "PI-6",
    )
    evidence = json.dumps(
        {
            "accepted_checkin_found": False,
            "expected": True,
            "expectation_id": expectation["expectation_id"],
            "roster_source_version": expectation["roster_source_version"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "violation_id": identifier,
        "rule_id": "PI-6",
        "rule_name": "EOD status update not submitted",
        "user_id": expectation["user_id"],
        "user_name": expectation["user_name"],
        "pod_id": expectation["pod_id"],
        "cycle_date": expectation["cycle_date"],
        "checkin_type": "EOD",
        "sla_code": expectation["sla_code"],
        "sla_due_at": expectation["sla_due_at"],
        "detected_at": _utc_text(now),
        "status": "open",
        "evidence_json": evidence,
        "workflow_execution_id": workflow_execution_id,
        "resolved_at": None,
        "resolved_by_checkin_id": None,
        "waiver_reason": None,
    }


def plan_compliance_actions(
    expectations: Iterable[Mapping[str, Any]],
    checkins: Iterable[Mapping[str, Any]],
    *,
    now: str | datetime,
    workflow_execution_id: str,
    existing_action_ids: Iterable[str] = (),
    violations: Iterable[Mapping[str, Any]] = (),
    nudge_before_minutes: int = 60,
    escalation_after_hours: int = 24,
) -> list[dict[str, Any]]:
    """Plan idempotent nudges, PI-6 upserts, resolutions, and pod digests."""

    current = _aware_datetime(now, "now")
    if not workflow_execution_id:
        raise ComplianceError("workflow_execution_id is required")
    if nudge_before_minutes <= 0 or escalation_after_hours <= 0:
        raise ComplianceError("compliance timing values must be positive")

    accepted = {_checkin_key(row): dict(row) for row in checkins}
    existing_ids = set(existing_action_ids)
    violation_by_key = {
        (str(row["user_id"]), str(row["cycle_date"]), str(row["checkin_type"])): dict(row)
        for row in violations
        if row.get("rule_id") == "PI-6"
    }
    actions: list[dict[str, Any]] = []
    escalations: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for raw_expectation in sorted(expectations, key=lambda item: str(item["expectation_id"])):
        expectation = dict(raw_expectation)
        state = expectation.get("attendance_state")
        if state not in EXPECTED_STATES:
            raise ComplianceError(f"invalid attendance_state: {state}")
        if state != "expected":
            continue

        key = (
            str(expectation["user_id"]),
            str(expectation["cycle_date"]),
            str(expectation["checkin_type"]),
        )
        due_at = _aware_datetime(str(expectation["sla_due_at"]), "sla_due_at")
        accepted_row = accepted.get(key)
        existing_violation = violation_by_key.get(key)

        if accepted_row:
            if existing_violation and existing_violation.get("status") == "open":
                checkin_id = str(accepted_row.get("checkin_id") or "|".join(key))
                action_id = resolution_id(str(existing_violation["violation_id"]), checkin_id)
                if action_id not in existing_ids:
                    actions.append(
                        {
                            "action_id": action_id,
                            "action_type": "resolve_violation",
                            "violation_id": existing_violation["violation_id"],
                            "resolved_at": _utc_text(current),
                            "resolved_by_checkin_id": checkin_id,
                        }
                    )
            continue

        nudge_at = due_at - timedelta(minutes=nudge_before_minutes)
        nudge_action_id = nudge_id(str(expectation["expectation_id"]))
        if nudge_at <= current < due_at and nudge_action_id not in existing_ids:
            actions.append(
                {
                    "action_id": nudge_action_id,
                    "action_type": "nudge",
                    "user_id": expectation["user_id"],
                    "pod_id": expectation["pod_id"],
                    "cycle_date": expectation["cycle_date"],
                    "checkin_type": expectation["checkin_type"],
                    "sla_due_at": expectation["sla_due_at"],
                }
            )

        if expectation["checkin_type"] != "EOD" or current < due_at:
            continue

        record = existing_violation or _violation_record(expectation, current, workflow_execution_id)
        action_id = f'upsert_{record["violation_id"]}'
        if existing_violation is None and action_id not in existing_ids:
            actions.append(
                {
                    "action_id": action_id,
                    "action_type": "upsert_violation",
                    "record": record,
                }
            )

        if current >= due_at + timedelta(hours=escalation_after_hours) and record.get("status") == "open":
            group_key = (
                str(expectation["pod_id"]),
                str(expectation["cycle_date"]),
                str(expectation["checkin_type"]),
            )
            escalations[group_key].append(record)

    for (pod_id, cycle_day, checkin_type), rows in sorted(escalations.items()):
        action_id = escalation_id(pod_id, cycle_day, checkin_type)
        if action_id in existing_ids:
            continue
        actions.append(
            {
                "action_id": action_id,
                "action_type": "escalation_digest",
                "pod_id": pod_id,
                "cycle_date": cycle_day,
                "checkin_type": checkin_type,
                "missing_count": len(rows),
                "violation_ids": sorted(str(row["violation_id"]) for row in rows),
                "user_ids": sorted(str(row["user_id"]) for row in rows),
            }
        )
    return actions


def weekly_rollup(
    expectations: Iterable[Mapping[str, Any]],
    checkins: Iterable[Mapping[str, Any]],
    *,
    period_start: str | date,
    period_end: str | date,
) -> list[dict[str, Any]]:
    """Return deterministic, privacy-minimized weekly pod metrics."""

    start = _date(period_start, "period_start")
    end = _date(period_end, "period_end")
    if end < start or (end - start).days > 6:
        raise ComplianceError("weekly period must be ordered and at most seven calendar days")

    expected_by_pod: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for row in expectations:
        cycle_day = _date(str(row["cycle_date"]), "cycle_date")
        if start <= cycle_day <= end and row.get("attendance_state") == "expected":
            expected_by_pod[str(row["pod_id"])].add(_checkin_key(row))

    submitted_by_pod: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for raw in checkins:
        row = dict(raw)
        cycle_day = _date(str(row["cycle_date"]), "cycle_date")
        if start <= cycle_day <= end:
            submitted_by_pod[str(row["pod_id"])][_checkin_key(row)] = row

    output: list[dict[str, Any]] = []
    for pod_id in sorted(expected_by_pod):
        expected_keys = expected_by_pod[pod_id]
        rows = [row for key, row in submitted_by_pod[pod_id].items() if key in expected_keys]
        expected_count = len(expected_keys)
        submitted_count = len(rows)
        on_time_count = sum(row.get("sla_status") == "on_time" for row in rows)
        late_count = sum(row.get("sla_status") == "late" for row in rows)
        proof_count = sum(bool(row.get("has_proof")) for row in rows)
        blocked_count = sum(int(row.get("blocked_count", 0)) for row in rows)
        output.append(
            {
                "rollup_id": rollup_id(pod_id, start.isoformat(), end.isoformat()),
                "pod_id": pod_id,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "expected_count": expected_count,
                "submitted_count": submitted_count,
                "missing_count": max(expected_count - submitted_count, 0),
                "on_time_count": on_time_count,
                "late_count": late_count,
                "submission_rate": round(submitted_count / expected_count, 4) if expected_count else 0.0,
                "proof_attach_rate": round(proof_count / submitted_count, 4) if submitted_count else 0.0,
                "blocked_task_count": blocked_count,
                "blocked_per_submission": round(blocked_count / submitted_count, 4) if submitted_count else 0.0,
            }
        )
    return output
