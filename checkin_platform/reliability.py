"""Retry, DLQ, and replay state-machine reference implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence, TypeVar

from .ids import dlq_id


UTC = timezone.utc
T = TypeVar("T")
FAILURE_STAGES = {
    "baserow_checkins_write",
    "mattermost_canonical_post",
    "event_dispatch",
}
REPLAY_STEPS = {
    "baserow_checkins_write": ("upsert_checkin", "ensure_canonical_post", "ensure_event"),
    "mattermost_canonical_post": ("verify_checkin", "ensure_canonical_post", "ensure_event"),
    "event_dispatch": ("verify_checkin", "verify_canonical_post", "ensure_event"),
}
RETRYABLE_HTTP = {408, 425, 429}


class ReliabilityError(ValueError):
    """Raised when a retry or replay operation violates its contract."""


class OperationFailure(RuntimeError):
    """Failure carrying a stable, non-sensitive code and retry hint."""

    def __init__(self, code: str, summary: str, *, retryable: bool, http_status: int | None = None):
        super().__init__(summary)
        self.code = code
        self.summary = sanitize_error_summary(summary)
        self.retryable = retryable
        self.http_status = http_status


@dataclass(frozen=True)
class RetryPolicy:
    """Three total attempts; 16 seconds schedules the first DLQ recovery scan."""

    attempts: int = 3
    between_attempt_seconds: tuple[int, ...] = (1, 4)
    dlq_retry_after_seconds: int = 16

    def __post_init__(self) -> None:
        if self.attempts < 1 or self.attempts > 5:
            raise ReliabilityError("attempts must be between 1 and 5")
        if len(self.between_attempt_seconds) != max(self.attempts - 1, 0):
            raise ReliabilityError("one delay is required between each attempt")
        delays = (*self.between_attempt_seconds, self.dlq_retry_after_seconds)
        if any(not isinstance(delay, int) or delay <= 0 or delay > 300 for delay in delays):
            raise ReliabilityError("retry delays must be positive integers no greater than 300 seconds")
        if tuple(sorted(delays)) != delays:
            raise ReliabilityError("retry delays must be monotonically non-decreasing")


@dataclass(frozen=True)
class RetryOutcome:
    succeeded: bool
    attempts: int
    value: Any = None
    failure: OperationFailure | None = None


def sanitize_error_summary(value: str) -> str:
    """Remove common credentials and control characters without logging raw input."""

    text = str(value).replace("\r", " ").replace("\n", " ")
    patterns = (
        r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+",
        r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+",
        r"(?i)(https?://[^:/\s]+:)[^@/\s]+@",
    )
    for pattern in patterns:
        text = re.sub(pattern, r"\1[REDACTED]", text)
    return " ".join(text.split())[:2000] or "Unspecified downstream failure"


def is_retryable_http(status: int) -> bool:
    return status in RETRYABLE_HTTP or 500 <= status <= 599


def run_with_retry(
    operation: Callable[[int], T],
    *,
    policy: RetryPolicy = RetryPolicy(),
    sleep: Callable[[int], None] = lambda _seconds: None,
) -> RetryOutcome:
    """Execute without jitter in tests; orchestration adds bounded jitter externally."""

    last_failure: OperationFailure | None = None
    for attempt in range(1, policy.attempts + 1):
        try:
            return RetryOutcome(succeeded=True, attempts=attempt, value=operation(attempt))
        except OperationFailure as exc:
            last_failure = exc
            if not exc.retryable or attempt == policy.attempts:
                return RetryOutcome(succeeded=False, attempts=attempt, failure=exc)
            sleep(policy.between_attempt_seconds[attempt - 1])
    raise AssertionError("retry loop exhausted without an outcome")


def _aware(value: str | datetime, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReliabilityError(f"{field} must be RFC3339") from exc
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReliabilityError(f"{field} must include an offset")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_dlq_record(
    submission: Mapping[str, Any],
    *,
    failure_stage: str,
    source_execution_id: str,
    error_code: str,
    error_summary: str,
    created_at: str | datetime,
    attempt_count: int = 3,
    policy: RetryPolicy = RetryPolicy(),
) -> dict[str, Any]:
    """Create the sole canonical DLQ row while preserving input verbatim."""

    if failure_stage not in FAILURE_STAGES:
        raise ReliabilityError(f"unsupported failure_stage: {failure_stage}")
    required = ("correlation_id", "user_id", "pod_id", "cycle_date", "checkin_type", "raw_submission")
    if any(field not in submission for field in required):
        raise ReliabilityError("submission is missing required DLQ context")
    if not source_execution_id:
        raise ReliabilityError("source_execution_id is required")
    if attempt_count != policy.attempts:
        raise ReliabilityError("DLQ capture requires exactly the configured attempts")
    raw_submission = submission["raw_submission"]
    if not isinstance(raw_submission, str) or not 1 <= len(raw_submission.encode("utf-8")) <= 65536:
        raise ReliabilityError("raw_submission must contain between 1 and 65536 UTF-8 bytes")
    created = _aware(created_at, "created_at")
    identifier = dlq_id(source_execution_id, failure_stage)
    return {
        "dlq_id": identifier,
        "replay_key": f"{source_execution_id}|{failure_stage}",
        "source_workflow": "checkin_submit_v1",
        "source_execution_id": source_execution_id,
        "correlation_id": str(submission["correlation_id"]),
        "user_id": str(submission["user_id"]),
        "pod_id": str(submission["pod_id"]),
        "cycle_date": str(submission["cycle_date"]),
        "checkin_type": str(submission["checkin_type"]),
        "failure_stage": failure_stage,
        "attempt_count": attempt_count,
        "status": "pending",
        "last_error_code": str(error_code)[:128],
        "last_error_summary": sanitize_error_summary(error_summary),
        "raw_submission": raw_submission,
        "created_at": _utc_text(created),
        "next_retry_at": _utc_text(created + timedelta(seconds=policy.dlq_retry_after_seconds)),
        "dm_notified_at": None,
        "resolved_at": None,
        "resolved_checkin_id": None,
        "replay_started_at": None,
        "replay_owner": None,
        "replay_attempt_count": 0,
        "retention_delete_after": None,
    }


def verbatim_dm(raw_submission: str, dlq_identifier: str) -> str:
    """Create a readable DM without changing a byte of the user's text."""

    longest = max((len(match) for match in re.findall(r"`+", raw_submission)), default=0)
    fence = "`" * max(3, longest + 1)
    return (
        "Your Daily Check-in could not be safely stored after three attempts. "
        f"Reference: `{dlq_identifier}`. Your exact input is preserved below:\n\n"
        f"{fence}\n{raw_submission}\n{fence}\n\n"
        "Operations has queued it for controlled replay; please do not resubmit unless contacted."
    )


def plan_replay(record: Mapping[str, Any], *, now: str | datetime, worker_id: str) -> dict[str, Any]:
    """Acquire or resume a replay lease and return stage-safe downstream steps."""

    current = _aware(now, "now")
    status = record.get("status")
    if status not in {"pending", "replaying"}:
        raise ReliabilityError(f"DLQ status {status!r} is not replayable")
    if not worker_id or len(worker_id) > 128:
        raise ReliabilityError("worker_id is required and must be at most 128 characters")
    failure_stage = str(record.get("failure_stage", ""))
    if failure_stage not in REPLAY_STEPS:
        raise ReliabilityError("DLQ failure_stage is not replayable")
    next_retry = record.get("next_retry_at")
    if next_retry and current < _aware(str(next_retry), "next_retry_at"):
        raise ReliabilityError("DLQ row is not due for replay")

    if status == "replaying":
        started_raw = record.get("replay_started_at")
        if not started_raw or current - _aware(str(started_raw), "replay_started_at") < timedelta(minutes=15):
            raise ReliabilityError("DLQ row already has an active replay lease")

    return {
        "dlq_id": record["dlq_id"],
        "replay_key": record["replay_key"],
        "correlation_id": record["correlation_id"],
        "raw_submission": record["raw_submission"],
        "status": "replaying",
        "replay_started_at": _utc_text(current),
        "replay_owner": worker_id,
        "replay_attempt_count": int(record.get("replay_attempt_count") or 0) + 1,
        "steps": list(REPLAY_STEPS[failure_stage]),
    }


def resolved_dlq_patch(
    record: Mapping[str, Any], *, resolved_at: str | datetime, checkin_id: str, retention_days: int = 30
) -> dict[str, Any]:
    if record.get("status") != "replaying":
        raise ReliabilityError("only a replaying DLQ row can be resolved")
    if not checkin_id:
        raise ReliabilityError("resolved checkin_id is required")
    resolved = _aware(resolved_at, "resolved_at")
    return {
        "status": "resolved",
        "resolved_at": _utc_text(resolved),
        "resolved_checkin_id": checkin_id,
        "next_retry_at": None,
        "retention_delete_after": _utc_text(resolved + timedelta(days=retention_days)),
    }
