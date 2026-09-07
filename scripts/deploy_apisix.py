#!/usr/bin/env python3
"""Dry-run-first APISIX Admin API deployment for Task #5585."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit


REQUIRED_PLUGINS = {
    "checkin-context",
    "client-control",
    "http-logger",
    "ip-restriction",
    "limit-count",
    "request-id",
    "response-rewrite",
}


class DeploymentError(RuntimeError):
    """Raised on a fail-closed deployment condition."""


def load_bundle(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        bundle = json.load(handle)
    if bundle.get("bundle_version") != 1 or len(bundle.get("resources", [])) != 3:
        raise DeploymentError("invalid or incomplete APISIX bundle")
    return bundle


def validate_admin_url(value: str, environment: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise DeploymentError("APISIX_ADMIN_URL must be an HTTP(S) URL")
    if environment not in {"local", "example"} and parsed.scheme != "https":
        raise DeploymentError("APISIX Admin API must use HTTPS outside local/example")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DeploymentError("APISIX_ADMIN_URL must not contain credentials, query, or fragment")
    return value.rstrip("/") + "/"


def _request(base_url: str, path: str, token: str, method: str, body: dict[str, Any] | None = None) -> tuple[int, str]:
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        urljoin(base_url, path.lstrip("/")),
        data=encoded,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=ssl.create_default_context()) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise DeploymentError(f"Admin API connection failed: {exc.reason}") from exc


def _collect_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, list):
        for item in value:
            found.update(_collect_strings(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key))
            found.update(_collect_strings(item))
    return found


def preflight_plugins(base_url: str, token: str) -> None:
    status, raw = _request(base_url, "/apisix/admin/plugins/list", token, "GET")
    if status != 200:
        raise DeploymentError(f"plugin preflight failed with HTTP {status}")
    try:
        available = _collect_strings(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise DeploymentError("plugin preflight returned invalid JSON") from exc
    missing = sorted(REQUIRED_PLUGINS - available)
    if missing:
        raise DeploymentError(f"required APISIX plugins unavailable: {', '.join(missing)}")


def snapshot_resources(
    base_url: str,
    token: str,
    resources: list[dict[str, Any]],
    backup_dir: Path,
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest: list[dict[str, Any]] = []
    for resource in resources:
        status, raw = _request(base_url, resource["admin_path"], token, "GET")
        entry = {"kind": resource["kind"], "id": resource["id"], "http_status": status}
        if status == 200:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DeploymentError(f"snapshot for {resource['id']} returned invalid JSON") from exc
            snapshot_path = backup_dir / f"{resource['kind']}-{resource['id']}.json"
            snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            entry["snapshot"] = snapshot_path.name
        elif status != 404:
            raise DeploymentError(f"snapshot for {resource['id']} failed with HTTP {status}")
        manifest.append(entry)
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def apply_bundle(base_url: str, token: str, bundle: dict[str, Any], backup_root: Path) -> None:
    preflight_plugins(base_url, token)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / timestamp
    snapshot_resources(base_url, token, bundle["resources"], backup_dir)
    print(f"SNAPSHOT: {backup_dir}")

    for resource in bundle["resources"]:
        status, _ = _request(base_url, resource["admin_path"], token, "PUT", resource["body"])
        if status not in {200, 201}:
            raise DeploymentError(f"apply stopped at {resource['kind']}/{resource['id']} with HTTP {status}")
        print(f"APPLIED: {resource['kind']}/{resource['id']} (HTTP {status})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="perform Admin API writes; otherwise dry-run")
    parser.add_argument("--confirm-environment", choices=("local", "staging", "production"))
    parser.add_argument("--backup-root", type=Path, default=Path("build/apisix-backups"))
    args = parser.parse_args()

    try:
        bundle = load_bundle(args.bundle)
        print(f"PLAN: APISIX {bundle['target_apisix_version']}.x / {bundle['environment']}")
        for resource in bundle["resources"]:
            print(f"  PUT {resource['admin_path']} ({resource['kind']}/{resource['id']})")
        if not args.apply:
            print("DRY-RUN: no external changes made")
            return 0

        if args.confirm_environment != bundle["environment"]:
            raise DeploymentError("--confirm-environment must exactly match the bundle environment")
        token = os.environ.get("APISIX_ADMIN_TOKEN")
        if not token:
            raise DeploymentError("APISIX_ADMIN_TOKEN is required for --apply")
        base_url = validate_admin_url(os.environ.get("APISIX_ADMIN_URL", ""), bundle["environment"])
        apply_bundle(base_url, token, bundle, args.backup_root)
    except (DeploymentError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
