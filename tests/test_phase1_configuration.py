from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ExistingPlatformConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = yaml.safe_load(
            (ROOT / "config/integration.topology.yaml").read_text(encoding="utf-8")
        )

    def test_delivery_configures_existing_platform(self) -> None:
        self.assertEqual(self.topology["delivery_mode"], "existing_platform_configuration")
        self.assertEqual(
            self.topology["existing_services"],
            {
                "gateway": "apisix",
                "service_discovery": "consul",
                "scheduler": "nomad",
                "secret_store": "vault",
                "workflow_engine": "n8n",
                "operational_store": "baserow",
                "analytics_store": "clickhouse",
                "logs": "loki",
                "dashboards": "grafana",
            },
        )

    def test_open_and_submit_routes_remain_separate(self) -> None:
        connections = {item["id"]: item for item in self.topology["connections"]}
        self.assertEqual(connections["mattermost_open"]["gateway_path"], "/webhook/checkin/open")
        self.assertEqual(connections["mattermost_open"]["application_writes"], "forbidden")
        self.assertEqual(connections["mattermost_submit"]["gateway_path"], "/webhook/checkin/submit")
        self.assertEqual(connections["mattermost_submit"]["operational_sink"], "baserow_checkins")

    def test_clickhouse_is_async_final_analytics_sink(self) -> None:
        analytics = self.topology["analytics"]
        self.assertEqual(analytics["final_sink"], "clickhouse")
        self.assertEqual(analytics["orchestrator"], "n8n")
        self.assertFalse(analytics["direct_mattermost_to_clickhouse"])
        self.assertFalse(analytics["request_path_blocks_on_analytics"])
        self.assertIn("airflow", analytics["forbidden_processors"])

    def test_dlq_keeps_raw_submission_out_of_clickhouse(self) -> None:
        dlq = next(item for item in self.topology["connections"] if item["id"] == "dead_letter")
        self.assertEqual(dlq["durable_first_copy"], "n8n_execution_store")
        self.assertEqual(dlq["operational_sink"], "baserow_checkin_dlq")
        self.assertEqual(dlq["analytical_sink"], "clickhouse")
        self.assertEqual(dlq["raw_submission_in_clickhouse"], "forbidden")

    def test_analytics_fact_examples_exclude_private_payloads(self) -> None:
        forbidden = {"user_name", "tasks_md", "tasks_json", "proof_links", "raw_submission", "nonce", "token"}
        for path in (ROOT / "contracts/analytics/examples").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(forbidden.isdisjoint(payload), path.name)

    def test_removed_reporting_assets_do_not_exist(self) -> None:
        self.assertFalse((ROOT / "analytics/superset").exists())
        self.assertFalse((ROOT / "analytics/superset-import").exists())
        self.assertFalse((ROOT / "scripts/package_superset.py").exists())


if __name__ == "__main__":
    unittest.main()
