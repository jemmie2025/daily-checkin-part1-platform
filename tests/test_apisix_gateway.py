from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = load_module("render_apisix", "scripts/render_apisix.py")
deployer = load_module("deploy_apisix", "scripts/deploy_apisix.py")
CONFIG_PATH = ROOT / "config" / "apisix.gateway.example.yaml"


def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def bundle() -> dict:
    return renderer.build_bundle(config())


def resources_by_id(rendered: dict) -> dict:
    return {item["id"]: item for item in rendered["resources"]}


class GatewayBundleTests(unittest.TestCase):
    def test_bundle_contains_upstream_then_two_routes(self) -> None:
        rendered = bundle()
        self.assertEqual([item["kind"] for item in rendered["resources"]], ["upstream", "route", "route"])

    def test_open_and_submit_are_separate_post_only_routes(self) -> None:
        resources = resources_by_id(bundle())
        open_route = resources["daily-checkin-open-v1"]["body"]
        submit_route = resources["daily-checkin-submit-v1"]["body"]
        self.assertEqual(open_route["uri"], "/webhook/checkin/open")
        self.assertEqual(submit_route["uri"], "/webhook/checkin/submit")
        self.assertEqual(open_route["methods"], ["POST"])
        self.assertEqual(submit_route["methods"], ["POST"])

    def test_both_routes_enforce_body_and_source_limits(self) -> None:
        resources = resources_by_id(bundle())
        for route_id in ("daily-checkin-open-v1", "daily-checkin-submit-v1"):
            plugins = resources[route_id]["body"]["plugins"]
            self.assertEqual(plugins["client-control"]["max_body_size"], 65536)
            self.assertEqual(plugins["checkin-context"]["max_body_size"], 65536)
            self.assertEqual(plugins["ip-restriction"]["whitelist"], ["192.0.2.0/24"])

    def test_rate_limit_is_shared_distributed_and_fail_closed(self) -> None:
        resources = resources_by_id(bundle())
        limits = [
            resources[route_id]["body"]["plugins"]["limit-count"]
            for route_id in ("daily-checkin-open-v1", "daily-checkin-submit-v1")
        ]
        self.assertEqual(limits[0], limits[1])
        self.assertEqual(limits[0]["count"], 10)
        self.assertEqual(limits[0]["time_window"], 60)
        self.assertEqual(limits[0]["key"], "http_x_checkin_user_id")
        self.assertEqual(limits[0]["policy"], "redis")
        self.assertFalse(limits[0]["allow_degradation"])
        self.assertTrue(limits[0]["redis_ssl"])
        self.assertTrue(limits[0]["redis_ssl_verify"])

    def test_open_route_has_sub_two_second_upstream_timeouts(self) -> None:
        resources = resources_by_id(bundle())
        timeout = resources["daily-checkin-open-v1"]["body"]["timeout"]
        self.assertTrue(all(0 < value < 2 for value in timeout.values()))

    def test_access_telemetry_excludes_bodies_and_sensitive_fields(self) -> None:
        resources = resources_by_id(bundle())
        forbidden = {"tasks", "tasks_md", "tasks_json", "proof_link", "proof_links", "token", "state", "nonce"}
        for route_id in ("daily-checkin-open-v1", "daily-checkin-submit-v1"):
            logger = resources[route_id]["body"]["plugins"]["http-logger"]
            self.assertFalse(logger["include_req_body"])
            self.assertFalse(logger["include_resp_body"])
            self.assertTrue(logger["ssl_verify"])
            self.assertFalse(forbidden & set(logger["log_format"]))
            self.assertNotIn("$request_body", logger["log_format"].values())

    def test_secret_values_remain_vault_rendered_runtime_references(self) -> None:
        resources = resources_by_id(bundle())
        plugins = resources["daily-checkin-open-v1"]["body"]["plugins"]
        self.assertEqual(plugins["limit-count"]["redis_password"], "$ENV://CHECKIN_REDIS_PASSWORD")
        self.assertEqual(plugins["http-logger"]["auth_header"], "$ENV://CHECKIN_TELEMETRY_AUTH_HEADER")

    def test_render_is_reproducible(self) -> None:
        self.assertEqual(renderer.serialized_bundle(bundle()), renderer.serialized_bundle(bundle()))


class GatewayFailClosedTests(unittest.TestCase):
    def test_production_rejects_documentation_cidr(self) -> None:
        candidate = config()
        candidate["environment"] = "production"
        with self.assertRaisesRegex(renderer.GatewayConfigError, "documentation CIDRs"):
            renderer.validate_config(candidate)

    def test_staging_rejects_plain_http_endpoints(self) -> None:
        candidate = config()
        candidate["environment"] = "staging"
        candidate["gateway"]["allowed_source_cidrs"] = ["10.42.0.0/16"]
        candidate["upstream"]["base_url"] = "http://n8n.internal"
        with self.assertRaisesRegex(renderer.GatewayConfigError, "HTTPS"):
            renderer.validate_config(candidate)

    def test_deployer_rejects_plain_http_admin_api(self) -> None:
        with self.assertRaisesRegex(deployer.DeploymentError, "HTTPS"):
            deployer.validate_admin_url("http://apisix-admin.internal", "staging")

    def test_custom_plugin_contains_required_static_guards(self) -> None:
        source = (ROOT / "apisix" / "custom" / "apisix" / "plugins" / "checkin-context.lua").read_text(
            encoding="utf-8"
        )
        self.assertIn("priority = 2999", source)
        self.assertIn("function _M.access", source)
        self.assertIn("function _M.header_filter", source)
        self.assertIn("payload_too_large", source)
        self.assertIn("invalid_user_id", source)
        self.assertNotIn("ngx.log", source)
        self.assertNotIn("core.log", source)


if __name__ == "__main__":
    unittest.main()
