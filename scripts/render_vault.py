#!/usr/bin/env python3
"""Render deterministic Vault policies, JWT roles, and Nomad task fragments."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "vault"
EXPECTED_WORKLOADS = {
    "apisix",
    "n8n-open",
    "n8n-submit",
    "n8n-compliance",
    "n8n-dlq",
    "n8n-analytics",
}
EXPECTED_PATH_READERS = {
    "apisix": {"apisix"},
    "analytics": {"n8n-analytics"},
    "dialog-shared": {"n8n-open", "n8n-submit"},
    "event-shared": {"n8n-analytics", "n8n-submit"},
    "open": {"n8n-open"},
    "submit": {"n8n-submit"},
    "compliance": {"n8n-compliance"},
    "dlq": {"n8n-dlq"},
}
ENV_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
DURATION_PATTERN = re.compile(r"^(?P<number>[1-9][0-9]*)(?P<unit>[smh])$")


class VaultConfigError(ValueError):
    """Raised when Vault configuration weakens the security contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VaultConfigError(message)


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    require(isinstance(config, dict), "Vault config must be an object")
    return config


def duration_seconds(value: str) -> int:
    match = DURATION_PATTERN.fullmatch(str(value))
    require(match is not None, f"unsupported duration: {value}")
    multiplier = {"s": 1, "m": 60, "h": 3600}[match.group("unit")]
    return int(match.group("number")) * multiplier


def _validate_https_url(value: str, field: str, environment: str) -> None:
    parsed = urlsplit(value)
    require(parsed.scheme in {"http", "https"}, f"{field} must be an HTTP(S) URL")
    require(bool(parsed.hostname), f"{field} must include a hostname")
    require(not parsed.username and not parsed.password, f"{field} must not contain credentials")
    require(not parsed.query and not parsed.fragment, f"{field} must not contain query or fragment")
    if environment not in {"example", "local"}:
        require(parsed.scheme == "https", f"{field} must use HTTPS outside local/example")


def _binding_tuple(binding: dict[str, Any]) -> tuple[str, str, str]:
    return str(binding["env"]), str(binding["secret_path"]), str(binding["key"])


def validate_config(config: dict[str, Any]) -> None:
    require(config.get("config_version") == 1, "config_version must be 1")
    require(config.get("target_vault_version") == "1.18+", "Vault target must be 1.18+")
    require(config.get("target_nomad_version") == "1.10+", "Nomad target must be 1.10+")
    environment = config.get("environment")
    require(environment in {"example", "local", "staging", "production"}, "invalid environment")

    vault = config.get("vault", {})
    jwt = vault.get("jwt", {})
    nomad = config.get("nomad", {})
    workloads = config.get("workloads", [])

    _validate_https_url(vault.get("address", ""), "vault.address", environment)
    _validate_https_url(jwt.get("jwks_url", ""), "vault.jwt.jwks_url", environment)
    require(vault.get("kv_mount") == "kv", "canonical KV mount must be kv")
    require(vault.get("kv_version") == 2, "runtime delivery requires Vault KV v2")
    require(vault.get("logical_prefix") == "n8n/mattermost/checkin", "logical Vault prefix changed")
    require(NAME_PATTERN.fullmatch(str(vault.get("auth_mount", ""))) is not None, "invalid JWT auth mount")
    require(jwt.get("jwks_ca_pem_file_env") == "VAULT_NOMAD_JWKS_CA_PEM_FILE", "JWKS CA file variable changed")
    require(jwt.get("require_jwks_ca_pem") is True, "JWKS TLS CA must be required")
    require(jwt.get("jwt_supported_algs") == ["RS256", "EdDSA"], "only RS256 and EdDSA are allowed")
    require(jwt.get("audience") == "vault.io", "Vault workload audience must be vault.io")
    require(jwt.get("token_type") == "service", "long-running tasks require renewable service tokens")
    require(duration_seconds(jwt.get("token_period", "")) == 1800, "Vault token period must be 30 minutes")
    require(jwt.get("token_explicit_max_ttl_seconds") == 0, "renewable service tokens require max TTL 0")
    require(jwt.get("token_no_default_policy") is True, "Vault default policy must be excluded")

    require(NAME_PATTERN.fullmatch(str(nomad.get("namespace", ""))) is not None, "invalid Nomad namespace")
    require(nomad.get("vault_cluster") == "default", "community Vault identity must use default cluster")
    require(duration_seconds(nomad.get("workload_identity_ttl", "")) == 3600, "workload identity TTL must be 1h")
    require(nomad.get("template_destination") == "secrets/daily-checkin.env", "secret template must stay in secrets dir")

    require(isinstance(workloads, list), "workloads must be a list")
    names = {item.get("name") for item in workloads if isinstance(item, dict)}
    require(names == EXPECTED_WORKLOADS, "exactly six isolated workloads are required")
    require(len(workloads) == len(names), "workload names must be unique")

    roles: set[str] = set()
    policies: set[str] = set()
    task_boundaries: set[tuple[str, str]] = set()
    environment_names: dict[str, tuple[str, str]] = {}
    path_readers: dict[str, set[str]] = defaultdict(set)
    path_keys: dict[str, set[str]] = defaultdict(set)

    for workload in workloads:
        name = workload["name"]
        for field in ("job_id", "task", "role_name", "policy_name", "owner"):
            require(NAME_PATTERN.fullmatch(str(workload.get(field, ""))) is not None, f"invalid {name}.{field}")
        require(workload.get("dedicated_task") is True, f"{name} must run as a dedicated Nomad task")
        require(isinstance(workload.get("rotation_days"), int), f"{name} rotation_days must be an integer")
        require(1 <= workload["rotation_days"] <= 90, f"{name} rotation must be 90 days or less")
        require(workload["role_name"] not in roles, "Vault role names must be unique")
        require(workload["policy_name"] not in policies, "Vault policy names must be unique")
        roles.add(workload["role_name"])
        policies.add(workload["policy_name"])

        boundary = (workload["job_id"], workload["task"])
        require(boundary not in task_boundaries, "workloads must not share a Nomad task boundary")
        task_boundaries.add(boundary)

        bindings = workload.get("bindings", [])
        require(isinstance(bindings, list) and bindings, f"{name} needs at least one secret binding")
        seen_bindings: set[tuple[str, str, str]] = set()
        for binding in bindings:
            require(isinstance(binding, dict), f"{name} binding must be an object")
            env_name, relative_path, key = _binding_tuple(binding)
            require(ENV_PATTERN.fullmatch(env_name) is not None, f"invalid environment name: {env_name}")
            require(relative_path in EXPECTED_PATH_READERS, f"unapproved secret path: {relative_path}")
            require(KEY_PATTERN.fullmatch(key) is not None, f"invalid secret key: {key}")
            require((env_name, relative_path, key) not in seen_bindings, f"duplicate binding in {name}")
            seen_bindings.add((env_name, relative_path, key))
            if env_name in environment_names:
                require(
                    environment_names[env_name] == (relative_path, key),
                    f"{env_name} maps to conflicting secret coordinates",
                )
            environment_names[env_name] = (relative_path, key)
            path_readers[relative_path].add(name)
            path_keys[relative_path].add(key)

    require(dict(path_readers) == EXPECTED_PATH_READERS, "secret-path reader boundaries changed")
    require(path_keys["dialog-shared"] == {"state_signing_key"}, "shared path may contain only the dialog signing key")
    require(path_keys["event-shared"] == {"event_ingest_token"}, "event-shared may contain only the ingest token")


def _policy(config: dict[str, Any], workload: dict[str, Any]) -> str:
    vault = config["vault"]
    paths = sorted({binding["secret_path"] for binding in workload["bindings"]})
    blocks = [
        "# Generated by scripts/render_vault.py. Do not grant list or wildcard access.",
        "",
    ]
    for relative_path in paths:
        full_path = f'{vault["kv_mount"]}/data/{vault["logical_prefix"]}/{relative_path}'
        blocks.extend([
            f'path "{full_path}" {{',
            '  capabilities = ["read"]',
            "}",
            "",
        ])
    return "\n".join(blocks)


def _role(config: dict[str, Any], workload: dict[str, Any]) -> str:
    jwt = config["vault"]["jwt"]
    body = {
        "role_type": "jwt",
        "bound_audiences": [jwt["audience"]],
        "bound_claims": {
            "nomad_namespace": config["nomad"]["namespace"],
            "nomad_job_id": workload["job_id"],
            "nomad_task": workload["task"],
            "vault_role": workload["role_name"],
        },
        "user_claim": "/nomad_allocation_id",
        "user_claim_json_pointer": True,
        "claim_mappings": {
            "nomad_namespace": "nomad_namespace",
            "nomad_job_id": "nomad_job_id",
            "nomad_task": "nomad_task",
            "nomad_allocation_id": "nomad_allocation_id",
            "vault_role": "vault_role",
        },
        "token_type": jwt["token_type"],
        "token_policies": [workload["policy_name"]],
        "token_period": jwt["token_period"],
        "token_explicit_max_ttl": jwt["token_explicit_max_ttl_seconds"],
        "token_no_default_policy": jwt["token_no_default_policy"],
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _nomad_fragment(config: dict[str, Any], workload: dict[str, Any]) -> str:
    vault = config["vault"]
    nomad = config["nomad"]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for binding in workload["bindings"]:
        grouped[binding["secret_path"]].append(binding)

    template_lines: list[str] = []
    for relative_path in sorted(grouped):
        api_path = f'{vault["kv_mount"]}/data/{vault["logical_prefix"]}/{relative_path}'
        template_lines.append(f'{{{{ with secret "{api_path}" }}}}')
        for binding in sorted(grouped[relative_path], key=lambda item: item["env"]):
            template_lines.append(f'{binding["env"]}={{{{ .Data.data.{binding["key"]} | toJSON }}}}')
        template_lines.append("{{ end }}")

    indented_template = "\n".join(f"    {line}" for line in template_lines)
    return (
        f'# Generated task fragment for job "{workload["job_id"]}", task "{workload["task"]}".\n'
        "# Merge only into that dedicated task; do not place at group or job scope.\n\n"
        "vault {\n"
        f'  cluster      = "{nomad["vault_cluster"]}"\n'
        f'  role         = "{workload["role_name"]}"\n'
        '  change_mode  = "restart"\n'
        "  env          = false\n"
        "  disable_file = true\n"
        "}\n\n"
        "identity {\n"
        f'  name = "vault_{nomad["vault_cluster"]}"\n'
        f'  aud  = ["{vault["jwt"]["audience"]}"]\n'
        f'  ttl  = "{nomad["workload_identity_ttl"]}"\n'
        "}\n\n"
        "template {\n"
        "  data = <<-EOT\n"
        f"{indented_template}\n"
        "  EOT\n\n"
        f'  destination          = "{nomad["template_destination"]}"\n'
        '  perms                = "0400"\n'
        "  env                  = true\n"
        "  error_on_missing_key = true\n"
        '  change_mode          = "restart"\n'
        '  splay                = "30s"\n'
        "}\n"
    )


def render_artifacts(config: dict[str, Any]) -> dict[str, str]:
    validate_config(config)
    vault = config["vault"]
    jwt = vault["jwt"]
    auth_config = {
        "default_role": "",
        "jwks_url": jwt["jwks_url"],
        "jwt_supported_algs": jwt["jwt_supported_algs"],
    }
    artifacts: dict[str, str] = {
        f'auth/{vault["auth_mount"]}-config.json': json.dumps(auth_config, indent=2, sort_keys=True) + "\n",
    }

    path_consumers: dict[str, set[str]] = defaultdict(set)
    path_keys: dict[str, set[str]] = defaultdict(set)
    inventory_workloads = []
    for workload in sorted(config["workloads"], key=lambda item: item["name"]):
        artifacts[f'policies/{workload["policy_name"]}.hcl'] = _policy(config, workload)
        artifacts[f'roles/{workload["role_name"]}.json'] = _role(config, workload)
        artifacts[f'nomad/{workload["name"]}.nomad.hcl'] = _nomad_fragment(config, workload)
        inventory_workloads.append({
            "name": workload["name"],
            "owner": workload["owner"],
            "policy_name": workload["policy_name"],
            "role_name": workload["role_name"],
            "rotation_days": workload["rotation_days"],
        })
        for binding in workload["bindings"]:
            path_consumers[binding["secret_path"]].add(workload["name"])
            path_keys[binding["secret_path"]].add(binding["key"])

    inventory = {
        "schema_version": 1,
        "classification": "secret-coordinates-only",
        "kv_mount": vault["kv_mount"],
        "kv_version": vault["kv_version"],
        "logical_prefix": vault["logical_prefix"],
        "secret_objects": [
            {
                "path": f'{vault["kv_mount"]}/{vault["logical_prefix"]}/{relative_path}',
                "consumers": sorted(path_consumers[relative_path]),
                "keys": sorted(path_keys[relative_path]),
            }
            for relative_path in sorted(path_consumers)
        ],
        "workloads": inventory_workloads,
    }
    artifacts["secret-inventory.json"] = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    return dict(sorted(artifacts.items()))


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def compare_directory(directory: Path, artifacts: dict[str, str]) -> list[str]:
    mismatches: list[str] = []
    expected_paths = {directory / relative for relative in artifacts}
    actual_paths = {path for path in directory.rglob("*") if path.is_file()} if directory.exists() else set()
    for relative, expected in artifacts.items():
        path = directory / relative
        if not path.exists():
            mismatches.append(f"missing {relative}")
        elif path.read_text(encoding="utf-8") != expected:
            mismatches.append(f"stale {relative}")
    for extra in sorted(actual_paths - expected_paths):
        mismatches.append(f"unexpected {extra.relative_to(directory)}")
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        artifacts = render_artifacts(load_config(args.config))
    except (VaultConfigError, KeyError, TypeError, yaml.YAMLError) as exc:
        parser.error(str(exc))

    if args.output_dir:
        for relative, content in artifacts.items():
            write_atomic(args.output_dir / relative, content)
        print(f"WROTE: {len(artifacts)} Vault/Nomad artifacts to {args.output_dir}")

    if args.check:
        mismatches = compare_directory(CANONICAL_DIR, artifacts)
        if mismatches:
            parser.error("canonical Vault artifacts differ: " + "; ".join(mismatches))
        print(f"PASS: {len(artifacts)} canonical Vault/Nomad artifacts are deterministic")
        print("PASS: exact-path read policies, claim-bound roles, and runtime templates validated")
    elif not args.output_dir:
        print(f"PASS: {len(artifacts)} Vault/Nomad artifacts rendered in memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
