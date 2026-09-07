#!/usr/bin/env python3
"""Run sanitized staging access, isolation, and rotation checks against Vault."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import stat
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import yaml


class SmokeFailure(RuntimeError):
    """Raised when Vault violates a Phase 3 acceptance condition."""


def tls_context() -> ssl.SSLContext:
    ca_file = os.environ.get("VAULT_CACERT")
    if ca_file:
        if not Path(ca_file).is_file():
            raise SmokeFailure("VAULT_CACERT does not name a readable file")
        return ssl.create_default_context(cafile=ca_file)
    return ssl.create_default_context()


def call(
    base_url: str,
    namespace: str,
    path: str,
    method: str,
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, Any] | None]:
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if namespace:
        headers["X-Vault-Namespace"] = namespace
    if token:
        headers["X-Vault-Token"] = token
    request = urllib.request.Request(
        urljoin(base_url, "v1/" + path.lstrip("/")),
        data=encoded,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=tls_context()) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, None
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SmokeFailure("Vault request failed or returned invalid JSON") from exc


def read_jwt(jwt_dir: Path, workload_name: str) -> str:
    path = jwt_dir / f"{workload_name}.jwt"
    if path.is_symlink() or not path.is_file():
        raise SmokeFailure(f"missing regular JWT file for {workload_name}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SmokeFailure(f"JWT file for {workload_name} must not be group/world accessible")
    value = path.read_text(encoding="utf-8").strip()
    if not 32 <= len(value) <= 16384:
        raise SmokeFailure(f"JWT file for {workload_name} has an invalid length")
    return value


def login(
    base_url: str,
    namespace: str,
    auth_mount: str,
    role_name: str,
    jwt: str,
) -> tuple[int, dict[str, Any] | None]:
    return call(
        base_url,
        namespace,
        f"auth/{quote(auth_mount, safe='')}/login",
        "POST",
        {"role": role_name, "jwt": jwt},
    )


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")


def run(config: dict[str, Any], jwt_dir: Path) -> dict[str, Any]:
    vault = config["vault"]
    base_url = vault["address"].rstrip("/") + "/"
    parsed = urlsplit(base_url)
    if parsed.scheme != "https":
        raise SmokeFailure("staging Vault must use HTTPS")
    namespace = vault["namespace"]
    auth_mount = vault["auth_mount"]
    mount = vault["kv_mount"]
    prefix = vault["logical_prefix"]

    all_paths: dict[str, set[str]] = {}
    for workload in config["workloads"]:
        for binding in workload["bindings"]:
            all_paths.setdefault(binding["secret_path"], set()).add(binding["key"])

    results: list[dict[str, Any]] = []
    jwt_values = {workload["name"]: read_jwt(jwt_dir, workload["name"]) for workload in config["workloads"]}
    for workload in sorted(config["workloads"], key=lambda item: item["name"]):
        name = workload["name"]
        status, payload = login(base_url, namespace, auth_mount, workload["role_name"], jwt_values[name])
        if status != 200 or not payload or not isinstance(payload.get("auth"), dict):
            raise SmokeFailure(f"own-role login failed for {name} with HTTP {status}")
        auth = payload["auth"]
        token = auth.get("client_token")
        if not isinstance(token, str) or not token:
            raise SmokeFailure(f"Vault returned no client token for {name}")
        if auth.get("renewable") is not True or not 1 <= int(auth.get("lease_duration", 0)) <= 1800:
            raise SmokeFailure(f"{name} did not receive the expected renewable short-lived token")
        if set(auth.get("token_policies", [])) != {workload["policy_name"]}:
            raise SmokeFailure(f"{name} received unexpected token policies")

        approved_paths = {binding["secret_path"] for binding in workload["bindings"]}
        versions: dict[str, int] = {}
        denied = 0
        for relative_path, expected_keys in sorted(all_paths.items()):
            api_path = f"{mount}/data/{prefix}/{relative_path}"
            read_status, secret_payload = call(base_url, namespace, api_path, "GET", token=token)
            if relative_path in approved_paths:
                if read_status != 200 or not secret_payload:
                    raise SmokeFailure(f"{name} could not read approved path {relative_path}")
                response_data = secret_payload.get("data", {})
                secret_data = response_data.get("data", {})
                if set(secret_data) != expected_keys:
                    raise SmokeFailure(f"{relative_path} has missing or undeclared keys")
                version = response_data.get("metadata", {}).get("version")
                if not isinstance(version, int) or version < 1:
                    raise SmokeFailure(f"{relative_path} returned no KV v2 version")
                versions[relative_path] = version
            else:
                if read_status != 403:
                    raise SmokeFailure(
                        f"{name} cross-path read for {relative_path} was not denied (HTTP {read_status})"
                    )
                denied += 1

        cross_role_denials = 0
        for other in config["workloads"]:
            if other["name"] == name:
                continue
            cross_status, _ = login(base_url, namespace, auth_mount, other["role_name"], jwt_values[name])
            if cross_status not in {400, 403}:
                raise SmokeFailure(
                    f"{name} JWT authenticated to foreign role {other['role_name']} (HTTP {cross_status})"
                )
            cross_role_denials += 1

        results.append({
            "workload": name,
            "role": workload["role_name"],
            "approved_path_versions": versions,
            "cross_path_denials": denied,
            "cross_role_denials": cross_role_denials,
            "renewable": True,
            "max_observed_lease_seconds": int(auth["lease_duration"]),
        })

    return {
        "schema_version": 1,
        "environment": config["environment"],
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "result": "pass",
        "contains_secret_values": False,
        "workloads": results,
    }


def verify_rotation(evidence: dict[str, Any], baseline_path: Path, expected_paths: set[str]) -> None:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    old_versions: dict[tuple[str, str], int] = {}
    for item in baseline.get("workloads", []):
        for relative_path, version in item.get("approved_path_versions", {}).items():
            old_versions[(item["workload"], relative_path)] = version
    advanced: set[str] = set()
    for item in evidence["workloads"]:
        for relative_path, version in item["approved_path_versions"].items():
            previous = old_versions.get((item["workload"], relative_path))
            if previous is not None and version > previous:
                advanced.add(relative_path)
    missing = expected_paths - advanced
    if missing:
        raise SmokeFailure("expected rotated paths did not advance KV version: " + ", ".join(sorted(missing)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--jwt-dir", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--baseline-evidence", type=Path)
    parser.add_argument("--expect-rotated-path", action="append", default=[])
    parser.add_argument("--confirm-staging", action="store_true")
    args = parser.parse_args()

    if not args.confirm_staging:
        parser.error("--confirm-staging is required")
    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        if config.get("environment") != "staging":
            raise SmokeFailure("smoke tests require config.environment=staging")
        evidence = run(config, args.jwt_dir)
        if args.expect_rotated_path:
            if not args.baseline_evidence:
                raise SmokeFailure("--baseline-evidence is required for rotation assertions")
            verify_rotation(evidence, args.baseline_evidence, set(args.expect_rotated_path))
            evidence["rotation_paths_verified"] = sorted(set(args.expect_rotated_path))
        write_evidence(args.evidence_output, evidence)
    except (SmokeFailure, KeyError, TypeError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"PASS: {len(evidence['workloads'])} workload identities authenticated only to their own roles")
    print("PASS: approved exact-path reads succeeded and every cross-path read was denied")
    print(f"EVIDENCE: {args.evidence_output} (secret values excluded; mode 0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
