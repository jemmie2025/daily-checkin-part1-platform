#!/usr/bin/env python3
"""Destructive-to-quota staging smoke test for the rendered APISIX routes."""

from __future__ import annotations

import argparse
import json
import math
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit


class SmokeFailure(RuntimeError):
    """Raised when a gateway acceptance check fails."""


@dataclass(frozen=True)
class Result:
    status: int
    elapsed_ms: float


def request(url: str, method: str, body: bytes | None, content_type: str | None = None) -> Result:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    call = urllib.request.Request(url, data=body, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(call, timeout=5, context=ssl.create_default_context()) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.read()
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"gateway connection failed: {exc.reason}") from exc
    return Result(status=status, elapsed_ms=(time.perf_counter() - started) * 1000)


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def run(base_url: str) -> None:
    open_url = base_url.rstrip("/") + "/webhook/checkin/open"
    get_result = request(open_url, "GET", None)
    if get_result.status not in {404, 405}:
        raise SmokeFailure(f"GET method was not denied: HTTP {get_result.status}")

    smoke_user = "smoke-" + uuid.uuid4().hex[:12]
    oversized = urllib.parse.urlencode(
        {"user_id": smoke_user, "token": "invalid-staging-token", "padding": "x" * 65536}
    ).encode("utf-8")
    oversized_result = request(open_url, "POST", oversized, "application/x-www-form-urlencoded")
    if oversized_result.status != 413:
        raise SmokeFailure(f"oversized payload was not rejected: HTTP {oversized_result.status}")

    regular = urllib.parse.urlencode(
        {
            "user_id": smoke_user,
            "token": "invalid-staging-token",
            "trigger_id": "staging-smoke-trigger",
            "channel_id": "staging-smoke-channel",
            "team_id": "staging-smoke-team",
            "command": "/ci",
        }
    ).encode("utf-8")

    attempts = [
        request(open_url, "POST", regular, "application/x-www-form-urlencoded")
        for _ in range(11)
    ]
    if any(item.status == 429 for item in attempts[:10]):
        raise SmokeFailure("rate limit rejected a request before the quota was consumed")
    if attempts[10].status != 429:
        raise SmokeFailure(f"eleventh request was not rate limited: HTTP {attempts[10].status}")

    p95 = percentile([item.elapsed_ms for item in attempts[:10]], 0.95)
    if p95 >= 2000:
        raise SmokeFailure(f"open-route staging p95 exceeded 2 seconds: {p95:.1f} ms")

    print("PASS: GET denied")
    print("PASS: 65,537+ byte encoded request rejected with HTTP 413")
    print("PASS: requests 1–10 admitted and request 11 rejected with HTTP 429")
    print(f"PASS: admitted-request p95 {p95:.1f} ms (< 2000 ms)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--confirm-staging",
        action="store_true",
        help="confirm the target is an isolated staging gateway with a mock/rejection upstream",
    )
    args = parser.parse_args()

    if not args.confirm_staging:
        parser.error("--confirm-staging is required; this test consumes a rate-limit window")
    parsed = urlsplit(args.base_url)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        parser.error("gateway must use HTTPS unless it is localhost")

    try:
        run(args.base_url)
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
