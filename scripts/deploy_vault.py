#!/usr/bin/env python3
"""Dry-run-first Vault policy and Nomad JWT-role deployment for Task #5585."""

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
from urllib.parse import quote, urljoin, urlsplit

from render_vault import VaultConfigError, load_config, render_artifacts


class DeploymentError(RuntimeError):
    """Raised when a Vault deployment cannot proceed safely."""


def validate_vault_url(value: str, environment: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise DeploymentError("Vault address must be an HTTP(S) URL")
    if environment != "local" and parsed.scheme != "https":
        raise DeploymentError("Vault must use HTTPS outside local")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DeploymentError("Vault address must not contain credentials, query, or fragment")
    return value.rstrip("/") + "/"


def tls_context() -> ssl.SSLContext:
    ca_file = os.environ.get("VAULT_CACERT")
    if ca_file:
        path = Path(ca_file)
        if not path.is_file():
            raise DeploymentError("VAULT_CACERT does not name a readable file")
        return ssl.create_default_context(cafile=str(path))
    return ssl.create_default_context()


def request(
    base_url: str,
    token: str,
    namespace: str,
    path: str,
    method: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, str]:
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Vault-Token": token,
    }
    if namespace:
        headers["X-Vault-Namespace"] = namespace
    call = urllib.request.Request(
        urljoin(base_url, "v1/" + path.lstrip("/")),
        data=encoded,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(call, timeout=10, context=tls_context()) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise DeploymentError(f"Vault connection failed: {exc.reason}") from exc


def parse_json(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DeploymentError(f"{label} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise DeploymentError(f"{label} returned a non-object response")
    return value


def preflight(
    base_url: str,
    token: str,
    config: dict[str, Any],
    artifacts: dict[str, str],
    include_auth_config: bool,
) -> None:
    namespace = config["vault"]["namespace"]
    status, raw = request(base_url, token, namespace, "sys/health", "GET")
    if status != 200:
        raise DeploymentError(f"Vault active-node health preflight failed with HTTP {status}")
    health = parse_json(raw, "Vault health preflight")
    if health.get("sealed") is not False or health.get("initialized") is not True:
        raise DeploymentError("Vault is not initialized and unsealed")

    status, raw = request(base_url, token, namespace, "sys/audit", "GET")
    if status != 200:
        raise DeploymentError(f"audit-device preflight failed with HTTP {status}")
    audit_devices = parse_json(raw, "audit-device preflight").get("data", {})
    usable_audit_devices = [
        name
        for name, details in audit_devices.items()
        if isinstance(details, dict) and details.get("type") in {"file", "socket", "syslog"}
    ]
    if len(usable_audit_devices) < 2:
        raise DeploymentError("at least two file, socket, or syslog audit devices are required")

    mount = config["vault"]["kv_mount"]
    status, raw = request(base_url, token, namespace, "sys/mounts", "GET")
    if status != 200:
        raise DeploymentError(f"KV mount preflight failed with HTTP {status}")
    mounts = parse_json(raw, "KV mount preflight").get("data", {})
    mount_data = mounts.get(mount + "/", {})
    if mount_data.get("type") != "kv" or str(mount_data.get("options", {}).get("version")) != "2":
        raise DeploymentError(f"Vault mount {mount}/ is not KV v2")

    auth_mount = config["vault"]["auth_mount"] + "/"
    status, raw = request(base_url, token, namespace, "sys/auth", "GET")
    if status != 200:
        raise DeploymentError(f"auth-mount preflight failed with HTTP {status}")
    auth_data = parse_json(raw, "auth-mount preflight").get("data", {})
    if auth_mount not in auth_data or auth_data[auth_mount].get("type") != "jwt":
        raise DeploymentError(f"JWT auth mount {auth_mount} must already exist")

    status, raw = request(
        base_url,
        token,
        namespace,
        f'auth/{quote(config["vault"]["auth_mount"], safe="")}/config',
        "GET",
    )
    if status != 200:
        raise DeploymentError(f"JWT auth configuration preflight failed with HTTP {status}")
    current_payload = parse_json(raw, "JWT auth configuration preflight")
    current_auth = current_payload.get("data", current_payload)
    if not include_auth_config:
        expected = json.loads(artifacts[f'auth/{config["vault"]["auth_mount"]}-config.json'])
        for field in ("jwks_url", "jwt_supported_algs", "default_role"):
            actual_value = current_auth.get(field, "" if field == "default_role" else None)
            expected_value = expected[field]
            matches = (
                set(actual_value) == set(expected_value)
                if field == "jwt_supported_algs" and isinstance(actual_value, list)
                else actual_value == expected_value
            )
            if not matches:
                raise DeploymentError(
                    f"existing JWT auth {field} differs; review and use --include-auth-config explicitly"
                )


def deployment_resources(config: dict[str, Any], artifacts: dict[str, str]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    auth_mount = config["vault"]["auth_mount"]
    for workload in sorted(config["workloads"], key=lambda item: item["name"]):
        policy_name = workload["policy_name"]
        role_name = workload["role_name"]
        resources.append({
            "kind": "policy",
            "name": policy_name,
            "path": f"sys/policies/acl/{quote(policy_name, safe='')}",
            "body": {"policy": artifacts[f"policies/{policy_name}.hcl"]},
        })
        resources.append({
            "kind": "role",
            "name": role_name,
            "path": f"auth/{quote(auth_mount, safe='')}/role/{quote(role_name, safe='')}",
            "body": json.loads(artifacts[f"roles/{role_name}.json"]),
        })
    return resources


def snapshot_resources(
    base_url: str,
    token: str,
    namespace: str,
    resources: list[dict[str, Any]],
    backup_dir: Path,
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest: list[dict[str, Any]] = []
    for resource in resources:
        status, raw = request(base_url, token, namespace, resource["path"], "GET")
        entry = {"kind": resource["kind"], "name": resource["name"], "http_status": status}
        if status == 200:
            payload = parse_json(raw, f"snapshot {resource['kind']}/{resource['name']}")
            snapshot_path = backup_dir / f"{resource['kind']}-{resource['name']}.json"
            snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            snapshot_path.chmod(0o600)
            entry["snapshot"] = snapshot_path.name
        elif status != 404:
            raise DeploymentError(
                f"snapshot for {resource['kind']}/{resource['name']} failed with HTTP {status}"
            )
        manifest.append(entry)
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)


def apply_auth_config(
    base_url: str,
    token: str,
    namespace: str,
    config: dict[str, Any],
    artifacts: dict[str, str],
) -> None:
    vault = config["vault"]
    auth_body = json.loads(artifacts[f'auth/{vault["auth_mount"]}-config.json'])
    ca_path_value = os.environ.get(vault["jwt"]["jwks_ca_pem_file_env"])
    if vault["jwt"]["require_jwks_ca_pem"]:
        if not ca_path_value or not Path(ca_path_value).is_file():
            raise DeploymentError(
                f'{vault["jwt"]["jwks_ca_pem_file_env"]} must name the Nomad JWKS CA PEM file'
            )
        auth_body["jwks_ca_pem"] = Path(ca_path_value).read_text(encoding="utf-8")
    status, _ = request(
        base_url,
        token,
        namespace,
        f'auth/{quote(vault["auth_mount"], safe="")}/config',
        "POST",
        auth_body,
    )
    if status not in {200, 204}:
        raise DeploymentError(f"JWT auth configuration failed with HTTP {status}")
    print(f'APPLIED: auth/{vault["auth_mount"]}/config (HTTP {status})')


def apply_resources(
    base_url: str,
    token: str,
    config: dict[str, Any],
    artifacts: dict[str, str],
    backup_root: Path,
    include_auth_config: bool,
) -> None:
    preflight(base_url, token, config, artifacts, include_auth_config)
    namespace = config["vault"]["namespace"]
    resources = deployment_resources(config, artifacts)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / timestamp
    snapshot_targets = list(resources)
    if include_auth_config:
        auth_mount = config["vault"]["auth_mount"]
        snapshot_targets.append({
            "kind": "auth-config",
            "name": auth_mount,
            "path": f"auth/{quote(auth_mount, safe='')}/config",
        })
    snapshot_resources(base_url, token, namespace, snapshot_targets, backup_dir)
    print(f"SNAPSHOT: {backup_dir}")

    if include_auth_config:
        apply_auth_config(base_url, token, namespace, config, artifacts)

    for resource in resources:
        status, _ = request(base_url, token, namespace, resource["path"], "PUT", resource["body"])
        if status not in {200, 204}:
            raise DeploymentError(
                f"apply stopped at {resource['kind']}/{resource['name']} with HTTP {status}"
            )
        print(f"APPLIED: {resource['kind']}/{resource['name']} (HTTP {status})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="perform Vault writes; otherwise dry-run")
    parser.add_argument("--confirm-environment", choices=("local", "staging", "production"))
    parser.add_argument("--include-auth-config", action="store_true", help="also update the shared JWT auth config")
    parser.add_argument("--backup-root", type=Path, default=Path("build/vault-backups"))
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        artifacts = render_artifacts(config)
        resources = deployment_resources(config, artifacts)
        print(f"PLAN: Vault/Nomad security resources / {config['environment']}")
        if args.include_auth_config:
            print(f"  POST /v1/auth/{config['vault']['auth_mount']}/config (shared auth configuration)")
        for resource in resources:
            print(f"  PUT /v1/{resource['path']} ({resource['kind']}/{resource['name']})")
        print("  SECRET VALUES: unchanged (provisioned through the approved secure channel)")
        if not args.apply:
            print("DRY-RUN: no external changes made")
            return 0

        if config["environment"] == "example":
            raise DeploymentError("example configuration cannot be applied")
        if args.confirm_environment != config["environment"]:
            raise DeploymentError("--confirm-environment must exactly match config.environment")
        token = os.environ.get("VAULT_TOKEN")
        if not token:
            raise DeploymentError("VAULT_TOKEN is required for --apply and must not be passed on the command line")
        base_url = validate_vault_url(config["vault"]["address"], config["environment"])
        apply_resources(base_url, token, config, artifacts, args.backup_root, args.include_auth_config)
    except (DeploymentError, VaultConfigError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
