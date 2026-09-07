#!/usr/bin/env python3
"""Render and validate deterministic APISIX Admin API resources."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
INTERNAL_RESPONSE_HEADERS = [
    "X-Checkin-Outcome",
    "X-Checkin-User-Id",
    "X-Checkin-Pod-Id",
    "X-Checkin-Cycle-Date",
    "X-Checkin-Type",
    "X-Checkin-Sla-Code",
    "X-Checkin-Gateway-Verified",
]


class GatewayConfigError(ValueError):
    """Raised when gateway configuration violates the master plan."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GatewayConfigError(message)


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    require(isinstance(config, dict), "gateway config must be an object")
    return config


def _validate_https_url(value: str, field: str, environment: str) -> None:
    parsed = urlsplit(value)
    require(parsed.scheme in {"https", "http"}, f"{field} must be an HTTP(S) URL")
    require(bool(parsed.hostname), f"{field} must include a hostname")
    require(not parsed.username and not parsed.password, f"{field} must not contain credentials")
    require(not parsed.query and not parsed.fragment, f"{field} must not contain query or fragment")
    if environment not in {"local", "example"}:
        require(parsed.scheme == "https", f"{field} must use HTTPS outside local/example")


def validate_config(config: dict[str, Any]) -> None:
    require(config.get("config_version") == 1, "config_version must be 1")
    require(config.get("target_apisix_version") == "3.18", "target APISIX version must be 3.18")
    environment = config.get("environment")
    require(environment in {"example", "local", "staging", "production"}, "invalid environment")

    gateway = config["gateway"]
    upstream = config["upstream"]
    secret_delivery = config["secret_delivery"]
    rate = config["rate_limit"]
    telemetry = config["telemetry"]

    require(gateway["open_path"] == "/webhook/checkin/open", "open path changed")
    require(gateway["submit_path"] == "/webhook/checkin/submit", "submit path changed")
    require(gateway["open_path"] != gateway["submit_path"], "open and submit routes must be separate")
    require(gateway["max_body_bytes"] == 65536, "body limit must be exactly 64 KiB")
    require(gateway["custom_plugin_priority"] == 2999, "checkin-context priority must be 2999")
    _validate_https_url(gateway["public_base_url"], "gateway.public_base_url", environment)
    _validate_https_url(upstream["base_url"], "upstream.base_url", environment)
    _validate_https_url(telemetry["url"], "telemetry.url", environment)

    parsed_upstream = urlsplit(upstream["base_url"])
    require(parsed_upstream.path in {"", "/"}, "upstream.base_url must not contain a path")

    cidrs = gateway.get("allowed_source_cidrs", [])
    require(bool(cidrs), "at least one Mattermost egress CIDR is required")
    parsed_cidrs = []
    for value in cidrs:
        try:
            parsed_cidrs.append(ipaddress.ip_network(value, strict=True))
        except ValueError as exc:
            raise GatewayConfigError(f"invalid source CIDR: {value}") from exc
    if environment == "production":
        for network in parsed_cidrs:
            require(
                not any(network.overlaps(documentation) for documentation in DOCUMENTATION_NETWORKS),
                "documentation CIDRs are forbidden in production",
            )

    require(rate["count"] == 10, "rate limit must be 10 requests")
    require(rate["window_seconds"] == 60, "rate window must be 60 seconds")
    require(rate["key_variable"] == "http_x_checkin_user_id", "rate key must use normalized user header")
    require(rate["policy"] == "redis", "distributed production-safe Redis rate policy is required")
    require(rate["group"] == "daily-checkin-user-v1", "shared route rate-limit group changed")
    require(rate["redis_ssl"] is True, "Redis TLS is required")
    require(rate["redis_ssl_verify"] is True, "Redis certificate verification is required")
    require(rate["allow_degradation"] is False, "rate limiting must fail closed")
    require(secret_delivery["mode"] == "nomad_template_env", "APISIX secrets must use Nomad runtime templates")
    require(secret_delivery["vault_kv_version"] == 2, "APISIX runtime secrets must originate in KV v2")
    require(
        secret_delivery["vault_path"] == "kv/n8n/mattermost/checkin/apisix",
        "APISIX Vault path changed",
    )
    require(
        rate["redis_password_secret_ref"] == "$ENV://CHECKIN_REDIS_PASSWORD",
        "Redis password must use the Vault-rendered environment reference",
    )

    require(telemetry["ssl_verify"] is True, "telemetry TLS verification is required")
    require(telemetry["include_request_body"] is False, "request bodies must not be logged")
    require(telemetry["include_response_body"] is False, "response bodies must not be logged")
    require(
        telemetry["auth_header_secret_ref"] == "$ENV://CHECKIN_TELEMETRY_AUTH_HEADER",
        "telemetry auth must use the Vault-rendered environment reference",
    )

    open_timeout = upstream["open_timeout_seconds"]
    require(0 < open_timeout["connect"] < 2, "open connect timeout must be below 2 seconds")
    require(0 < open_timeout["send"] < 2, "open send timeout must be below 2 seconds")
    require(0 < open_timeout["read"] < 2, "open read timeout must be below 2 seconds")


def _upstream_node(base_url: str) -> tuple[str, str]:
    parsed = urlsplit(base_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, f"{parsed.hostname}:{port}"


def _rate_limit(config: dict[str, Any]) -> dict[str, Any]:
    rate = config["rate_limit"]
    return {
        "count": rate["count"],
        "time_window": rate["window_seconds"],
        "window_type": "fixed",
        "key_type": "var",
        "key": rate["key_variable"],
        "policy": "redis",
        "group": rate["group"],
        "redis_host": rate["redis_host"],
        "redis_port": rate["redis_port"],
        "redis_password": rate["redis_password_secret_ref"],
        "redis_ssl": True,
        "redis_ssl_verify": True,
        "redis_timeout": 1000,
        "allow_degradation": False,
        "show_limit_quota_header": False,
        "rejected_code": 429,
        "rejected_msg": "Rate limit exceeded",
    }


def _http_logger(config: dict[str, Any]) -> dict[str, Any]:
    telemetry = config["telemetry"]
    return {
        "uri": telemetry["url"],
        "auth_header": telemetry["auth_header_secret_ref"],
        "timeout": telemetry["timeout_seconds"],
        "ssl_verify": True,
        "include_req_body": False,
        "include_resp_body": False,
        "concat_method": "json",
        "log_format": {
            "schema_version": "1",
            "logged_at": "$time_iso8601",
            "route_id": "$route_id",
            "request_method": "$request_method",
            "status": "$status",
            "upstream_status": "$upstream_status",
            "latency_seconds": "$request_time",
            "correlation_id": "$http_x_checkin_correlation_id",
            "user_id": "$http_x_checkin_user_id",
            "outcome": "$upstream_http_x_checkin_outcome",
            "pod_id": "$upstream_http_x_checkin_pod_id",
            "cycle_date": "$upstream_http_x_checkin_cycle_date",
            "checkin_type": "$upstream_http_x_checkin_type",
            "sla_code": "$upstream_http_x_checkin_sla_code",
        },
    }


def _plugins(config: dict[str, Any], payload_type: str) -> dict[str, Any]:
    gateway = config["gateway"]
    plugins = {
        "ip-restriction": {
            "whitelist": gateway["allowed_source_cidrs"],
            "message": "Access denied",
            "response_code": 403,
        },
        "client-control": {
            "max_body_size": gateway["max_body_bytes"],
        },
        "request-id": {
            "header_name": "X-Checkin-Correlation-Id",
            "include_in_response": False,
            "algorithm": "uuid",
        },
        "checkin-context": {
            "payload_type": payload_type,
            "max_body_size": gateway["max_body_bytes"],
            "user_header": "X-Checkin-User-Id",
            "correlation_header": "X-Checkin-Correlation-Id",
        },
        "limit-count": _rate_limit(config),
        "response-rewrite": {
            "headers": {
                "remove": INTERNAL_RESPONSE_HEADERS,
            }
        },
        "http-logger": _http_logger(config),
    }
    return plugins


def build_bundle(config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    ids = config["resource_ids"]
    scheme, node = _upstream_node(config["upstream"]["base_url"])

    upstream = {
        "name": "Daily Check-in n8n upstream v1",
        "type": "roundrobin",
        "scheme": scheme,
        "pass_host": "node",
        "nodes": {node: 1},
        "labels": {"task": "5585", "component": "daily-checkin"},
    }

    def route(route_id: str, name: str, path: str, payload_type: str, timeout: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "uri": path,
            "methods": ["POST"],
            "priority": 100,
            "status": 1,
            "upstream_id": ids["upstream"],
            "timeout": deepcopy(timeout),
            "plugins": _plugins(config, payload_type),
            "labels": {
                "task": "5585",
                "contract": "checkin_v1",
                "data_classification": "confidential",
            },
        }

    resources = [
        {
            "kind": "upstream",
            "id": ids["upstream"],
            "admin_path": f"/apisix/admin/upstreams/{ids['upstream']}",
            "body": upstream,
        },
        {
            "kind": "route",
            "id": ids["open_route"],
            "admin_path": f"/apisix/admin/routes/{ids['open_route']}",
            "body": route(
                ids["open_route"],
                "Daily Check-in Open Handler v1",
                config["gateway"]["open_path"],
                "open",
                config["upstream"]["open_timeout_seconds"],
            ),
        },
        {
            "kind": "route",
            "id": ids["submit_route"],
            "admin_path": f"/apisix/admin/routes/{ids['submit_route']}",
            "body": route(
                ids["submit_route"],
                "Daily Check-in Submit Handler v1",
                config["gateway"]["submit_path"],
                "submit",
                config["upstream"]["submit_timeout_seconds"],
            ),
        },
    ]

    return {
        "bundle_version": 1,
        "target_apisix_version": config["target_apisix_version"],
        "environment": config["environment"],
        "resources": resources,
    }


def serialized_bundle(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        bundle = build_bundle(load_config(args.config))
    except (GatewayConfigError, KeyError, TypeError, yaml.YAMLError) as exc:
        parser.error(str(exc))

    if args.output:
        write_atomic(args.output, serialized_bundle(bundle))
        print(f"WROTE: {args.output}")
    if args.check or not args.output:
        print(f"PASS: APISIX {bundle['target_apisix_version']}.x bundle validated")
        print(f"PASS: {len(bundle['resources'])} deterministic Admin API resources rendered")
        print("PASS: route separation, 64 KiB cap, CIDR, Redis rate limit, TLS, and log privacy enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
