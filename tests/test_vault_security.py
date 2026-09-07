from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = load_module("render_vault", "scripts/render_vault.py")
scanner = load_module("scan_secrets", "scripts/scan_secrets.py")
sys.path.insert(0, str(ROOT / "scripts"))
deployer = load_module("deploy_vault", "scripts/deploy_vault.py")
CONFIG_PATH = ROOT / "config" / "vault.security.example.yaml"


def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def artifacts() -> dict[str, str]:
    return renderer.render_artifacts(config())


class VaultPolicyTests(unittest.TestCase):
    def test_canonical_artifacts_match_deterministic_render(self) -> None:
        self.assertEqual(renderer.compare_directory(ROOT / "vault", artifacts()), [])

    def test_six_roles_have_six_distinct_read_only_policies(self) -> None:
        rendered = artifacts()
        policies = {name: body for name, body in rendered.items() if name.startswith("policies/")}
        roles = {name: body for name, body in rendered.items() if name.startswith("roles/")}
        self.assertEqual(len(policies), 6)
        self.assertEqual(len(roles), 6)
        for body in policies.values():
            self.assertNotIn("*", body)
            self.assertNotIn("metadata/", body)
            self.assertNotRegex(body, r'capabilities\s*=\s*\[[^]]*(?:create|update|delete|list|sudo)')
            self.assertGreaterEqual(body.count('capabilities = ["read"]'), 1)

    def test_secret_path_readers_are_exact(self) -> None:
        cfg = config()
        actual: dict[str, set[str]] = {}
        for workload in cfg["workloads"]:
            for binding in workload["bindings"]:
                actual.setdefault(binding["secret_path"], set()).add(workload["name"])
        self.assertEqual(actual, renderer.EXPECTED_PATH_READERS)
        self.assertEqual(actual["dialog-shared"], {"n8n-open", "n8n-submit"})
        self.assertEqual(actual["event-shared"], {"n8n-analytics", "n8n-submit"})

    def test_shared_object_contains_only_signing_key(self) -> None:
        inventory = json.loads(artifacts()["secret-inventory.json"])
        shared = next(item for item in inventory["secret_objects"] if item["path"].endswith("/dialog-shared"))
        self.assertEqual(shared["keys"], ["state_signing_key"])
        self.assertEqual(shared["consumers"], ["n8n-open", "n8n-submit"])

    def test_event_shared_object_contains_only_ingest_token(self) -> None:
        inventory = json.loads(artifacts()["secret-inventory.json"])
        shared = next(item for item in inventory["secret_objects"] if item["path"].endswith("/event-shared"))
        self.assertEqual(shared["keys"], ["event_ingest_token"])
        self.assertEqual(shared["consumers"], ["n8n-analytics", "n8n-submit"])

    def test_dlq_object_has_execution_recovery_reader(self) -> None:
        inventory = json.loads(artifacts()["secret-inventory.json"])
        dlq = next(item for item in inventory["secret_objects"] if item["path"].endswith("/dlq"))
        self.assertIn("n8n_execution_read_token", dlq["keys"])
        self.assertEqual(dlq["consumers"], ["n8n-dlq"])

    def test_roles_are_bound_to_namespace_job_task_and_one_audience(self) -> None:
        cfg = config()
        rendered = artifacts()
        for workload in cfg["workloads"]:
            role = json.loads(rendered[f'roles/{workload["role_name"]}.json'])
            self.assertEqual(role["bound_audiences"], ["vault.io"])
            self.assertEqual(
                role["bound_claims"],
                {
                    "nomad_namespace": "platform",
                    "nomad_job_id": workload["job_id"],
                    "nomad_task": workload["task"],
                    "vault_role": workload["role_name"],
                },
            )
            self.assertEqual(role["user_claim"], "/nomad_allocation_id")
            self.assertEqual(role["token_policies"], [workload["policy_name"]])
            self.assertTrue(role["token_no_default_policy"])

    def test_roles_issue_renewable_short_period_service_tokens(self) -> None:
        for name, body in artifacts().items():
            if not name.startswith("roles/"):
                continue
            role = json.loads(body)
            self.assertEqual(role["token_type"], "service")
            self.assertEqual(role["token_period"], "30m")
            self.assertEqual(role["token_explicit_max_ttl"], 0)

    def test_auth_config_has_no_default_role(self) -> None:
        auth_config = json.loads(artifacts()["auth/jwt-nomad-config.json"])
        self.assertEqual(auth_config["default_role"], "")


class VaultRuntimeTemplateTests(unittest.TestCase):
    def test_each_workload_is_a_dedicated_nomad_task(self) -> None:
        cfg = config()
        boundaries = {(item["job_id"], item["task"]) for item in cfg["workloads"]}
        self.assertEqual(len(boundaries), 6)
        self.assertTrue(all(item["dedicated_task"] for item in cfg["workloads"]))

    def test_templates_do_not_expose_vault_token(self) -> None:
        for name, body in artifacts().items():
            if not name.startswith("nomad/"):
                continue
            self.assertIn("env          = false", body)
            self.assertIn("disable_file = true", body)
            self.assertNotIn("VAULT_TOKEN=", body)

    def test_templates_are_kv2_fail_closed_and_rotation_aware(self) -> None:
        for name, body in artifacts().items():
            if not name.startswith("nomad/"):
                continue
            self.assertIn('name = "vault_default"', body)
            self.assertIn('aud  = ["vault.io"]', body)
            self.assertIn('ttl  = "1h"', body)
            self.assertIn('destination          = "secrets/daily-checkin.env"', body)
            self.assertIn('perms                = "0400"', body)
            self.assertIn("env                  = true", body)
            self.assertIn("error_on_missing_key = true", body)
            self.assertIn('change_mode          = "restart"', body)
            self.assertIn('secret "kv/data/n8n/mattermost/checkin/', body)
            self.assertIn(".Data.data.", body)

    def test_apisix_runtime_references_match_vault_bindings(self) -> None:
        gateway = yaml.safe_load((ROOT / "config" / "apisix.gateway.example.yaml").read_text(encoding="utf-8"))
        apisix = next(item for item in config()["workloads"] if item["name"] == "apisix")
        env_names = {binding["env"] for binding in apisix["bindings"]}
        self.assertEqual(
            {
                gateway["rate_limit"]["redis_password_secret_ref"].removeprefix("$ENV://"),
                gateway["telemetry"]["auth_header_secret_ref"].removeprefix("$ENV://"),
            },
            env_names,
        )
        self.assertEqual(gateway["secret_delivery"]["vault_kv_version"], 2)


class VaultFailClosedTests(unittest.TestCase):
    @staticmethod
    def preflight_responses(audit_count: int = 2, mismatched_jwks: bool = False):
        cfg = config()
        expected_auth = json.loads(artifacts()["auth/jwt-nomad-config.json"])
        if mismatched_jwks:
            expected_auth["jwks_url"] = "https://wrong.example.internal/.well-known/jwks.json"
        responses = {
            "sys/health": (200, {"initialized": True, "sealed": False}),
            "sys/audit": (
                200,
                {"data": {f"audit-{index}/": {"type": "file"} for index in range(audit_count)}},
            ),
            "sys/mounts": (200, {"data": {"kv/": {"type": "kv", "options": {"version": "2"}}}}),
            "sys/auth": (200, {"data": {"jwt-nomad/": {"type": "jwt"}}}),
            "auth/jwt-nomad/config": (200, {"data": expected_auth}),
        }

        def fake_request(base_url, token, namespace, path, method, body=None):
            status, payload = responses[path]
            return status, json.dumps(payload)

        return cfg, fake_request

    def test_production_rejects_plain_http(self) -> None:
        candidate = copy.deepcopy(config())
        candidate["environment"] = "production"
        candidate["vault"]["address"] = "http://vault.internal"
        with self.assertRaisesRegex(renderer.VaultConfigError, "HTTPS"):
            renderer.validate_config(candidate)

    def test_policy_renderer_rejects_shared_n8n_task(self) -> None:
        candidate = copy.deepcopy(config())
        submit = next(item for item in candidate["workloads"] if item["name"] == "n8n-submit")
        opened = next(item for item in candidate["workloads"] if item["name"] == "n8n-open")
        submit["job_id"] = opened["job_id"]
        submit["task"] = opened["task"]
        with self.assertRaisesRegex(renderer.VaultConfigError, "share a Nomad task"):
            renderer.validate_config(candidate)

    def test_policy_renderer_rejects_wildcard_or_unapproved_path(self) -> None:
        candidate = copy.deepcopy(config())
        candidate["workloads"][0]["bindings"][0]["secret_path"] = "*"
        with self.assertRaisesRegex(renderer.VaultConfigError, "unapproved secret path"):
            renderer.validate_config(candidate)

    def test_example_deployment_is_dry_run_only(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/deploy_vault.py", "--config", str(CONFIG_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("DRY-RUN: no external changes made", completed.stdout)
        self.assertNotIn("APPLIED:", completed.stdout)

    def test_live_preflight_accepts_only_hardened_dependencies(self) -> None:
        cfg, fake_request = self.preflight_responses()
        with patch.object(deployer, "request", side_effect=fake_request):
            deployer.preflight("https://vault.example/", "opaque", cfg, artifacts(), False)

    def test_live_preflight_rejects_single_audit_device(self) -> None:
        cfg, fake_request = self.preflight_responses(audit_count=1)
        with patch.object(deployer, "request", side_effect=fake_request):
            with self.assertRaisesRegex(deployer.DeploymentError, "at least two"):
                deployer.preflight("https://vault.example/", "opaque", cfg, artifacts(), False)

    def test_live_preflight_rejects_unreviewed_auth_drift(self) -> None:
        cfg, fake_request = self.preflight_responses(mismatched_jwks=True)
        with patch.object(deployer, "request", side_effect=fake_request):
            with self.assertRaisesRegex(deployer.DeploymentError, "jwks_url differs"):
                deployer.preflight("https://vault.example/", "opaque", cfg, artifacts(), False)


class SecretLeakGateTests(unittest.TestCase):
    def test_repository_secret_scan_is_clean(self) -> None:
        checked, findings = scanner.scan_tree(ROOT)
        self.assertGreater(checked, 50)
        self.assertEqual(findings, [])

    def test_scanner_detects_known_token_without_echoing_value(self) -> None:
        synthetic = "ghp_" + "A" * 36
        findings = scanner.scan_text("credential=" + synthetic, "fixture")
        self.assertTrue(findings)
        self.assertTrue(all(synthetic not in finding for finding in findings))


if __name__ == "__main__":
    unittest.main()
