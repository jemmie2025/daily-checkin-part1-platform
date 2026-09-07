#!/usr/bin/env python3
"""Validate SLO, alerting, privacy, load, security, and runbook gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


class HardeningError(ValueError):
    """Raised when a production-readiness invariant is missing."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HardeningError(message)


def load_yaml(relative: str) -> dict[str, Any]:
    value = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{relative} must contain an object")
    return value


def validate_slos() -> tuple[int, int]:
    config = load_yaml("config/slos.yaml")
    alerts = load_yaml("observability/prometheus/checkin-alerts.yaml")
    recording = load_yaml("observability/prometheus/checkin-recording-rules.yaml")
    slos = config.get("slos", [])
    require(len(slos) == 5, "exactly five service SLOs are required")
    identifiers = {item["id"] for item in slos}
    require(len(identifiers) == len(slos), "SLO IDs must be unique")
    require({item["objective_percent"] for item in slos} <= {99.0, 99.9, 100.0}, "unsupported SLO target")
    durability = next(item for item in slos if item["id"] == "submission_durability")
    require(durability["objective_percent"] == 100.0, "submission durability target must remain 100%")

    alert_rules = [rule for group in alerts.get("groups", []) for rule in group.get("rules", [])]
    alert_names = {rule.get("alert") for rule in alert_rules}
    require(all(item["critical_alert"] in alert_names for item in slos), "every SLO needs its mapped alert")
    recording_names = {
        rule.get("record")
        for group in recording.get("groups", [])
        for rule in group.get("rules", [])
    }
    require(all(item["indicator"] in recording_names for item in slos), "every SLO needs its recording rule")
    for rule in alert_rules:
        require(rule.get("labels", {}).get("owner"), f"alert {rule.get('alert')} has no owner")
        require(rule.get("annotations", {}).get("runbook_url"), f"alert {rule.get('alert')} has no runbook")
    return len(slos), len(alert_rules)


def validate_telemetry() -> int:
    contract = load_yaml("observability/telemetry-contract.yaml")
    forbidden = set(contract["forbidden_labels_and_log_fields"])
    allowed = set(contract["allowed_log_fields"])
    require(not (forbidden & allowed), "telemetry allowlist overlaps forbidden fields")
    require(contract["cardinality_limits"]["correlation_id_as_metric_label"] is False, "correlation IDs cannot be labels")
    require(contract["cardinality_limits"]["request_id_as_metric_label"] is False, "request IDs cannot be labels")
    require(contract["cardinality_limits"]["execution_id_as_metric_label"] is False, "execution IDs cannot be labels")
    for metric in contract["metrics"]:
        require(not (set(metric["labels"]) & forbidden), f"metric {metric['name']} has a forbidden label")
    return len(contract["metrics"])


def validate_test_plans() -> int:
    open_load = (ROOT / "load/k6/open-handler.js").read_text(encoding="utf-8")
    controls = (ROOT / "load/k6/gateway-controls.js").read_text(encoding="utf-8")
    zap = load_yaml("security/zap/checkin-api.yaml")
    for required in ("p(95)<1800", "p(99)<1950", "timeout: '2s'", "https://"):
        require(required in open_load, f"open load plan missing {required}")
    require("request <= 11" in controls, "quota test must send eleven requests")
    require("65537" in controls, "body-limit test must send 65,537 bytes")
    require("http.get(target)" in controls, "method control test is missing")
    jobs = {item["type"] for item in zap.get("jobs", [])}
    require({"passiveScan-config", "spider", "passiveScan-wait", "report"} <= jobs, "ZAP plan is incomplete")
    return 3


def validate_runbooks() -> int:
    required = {
        "docs/runbooks/apisix-deployment.md": ("staging", "rollback"),
        "docs/runbooks/vault-deployment-and-rotation.md": ("rotation", "revocation"),
        "docs/runbooks/compliance-operations.md": ("suppression", "rollback"),
        "docs/runbooks/dlq-operations.md": ("replay", "outage"),
        "docs/runbooks/analytics-deployment.md": ("deduplication", "rollback"),
        "docs/runbooks/incident-response.md": ("submission durability", "credential exposure"),
        "docs/runbooks/disaster-recovery.md": ("rpo", "restore order"),
        "docs/runbooks/production-rollout.md": ("abort conditions", "three clean"),
    }
    for relative, terms in required.items():
        content = (ROOT / relative).read_text(encoding="utf-8").lower()
        require(all(term in content for term in terms), f"{relative} is missing an operational section")
    return len(required)


def validate_superset_assets() -> int:
    dashboard = load_yaml("analytics/superset/dashboards/Daily_Checkin_Compliance.yaml")
    require(dashboard["published"] is False, "dashboard must ship unpublished")
    require(len(dashboard["charts"]) == 6, "dashboard must contain six charts")
    json.loads(dashboard["position"])
    json.loads(dashboard["metadata"])
    return len(dashboard["charts"])


def main() -> int:
    try:
        slo_count, alert_count = validate_slos()
        metric_count = validate_telemetry()
        test_plan_count = validate_test_plans()
        runbook_count = validate_runbooks()
        chart_count = validate_superset_assets()
    except (HardeningError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {slo_count} SLOs map to recording rules and {alert_count} owned alerts")
    print(f"PASS: {metric_count} telemetry metrics obey privacy and cardinality controls")
    print(f"PASS: {test_plan_count} load/security plans enforce release thresholds")
    print(f"PASS: {runbook_count} operational runbooks contain required recovery controls")
    print(f"PASS: {chart_count} Superset charts remain unpublished and structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
