from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLICKHOUSE = ROOT / "analytics" / "clickhouse"
SUPERSET = ROOT / "analytics" / "superset"
SUPERSET_ARCHIVE = ROOT / "analytics" / "superset-import" / "daily-checkin-compliance-v1.zip"


class ClickHouseTests(unittest.TestCase):
    def test_raw_tables_use_replicated_replacing_engines(self) -> None:
        ddl = (CLICKHOUSE / "001_schema.sql").read_text(encoding="utf-8")
        self.assertEqual(ddl.count("ENGINE = ReplicatedReplacingMergeTree"), 2)
        self.assertIn("replicated_deduplication_window", ddl)
        self.assertIn("payload_hash FixedString(64)", ddl)
        self.assertIn("ORDER BY event_id", ddl)
        self.assertIn("valid_task_state_counts", ddl)

    def test_detail_tables_have_24_month_ttl(self) -> None:
        ddl = (CLICKHOUSE / "001_schema.sql").read_text(encoding="utf-8")
        self.assertEqual(ddl.count("INTERVAL 24 MONTH DELETE"), 2)
        self.assertEqual(ddl.count("PARTITION BY toYYYYMM"), 2)

    def test_analytics_schema_has_no_confidential_content_columns(self) -> None:
        ddl = (CLICKHOUSE / "001_schema.sql").read_text(encoding="utf-8").lower()
        for field in ("user_name", "tasks_md", "tasks_json", "proof_links", "raw_submission", "nonce"):
            self.assertNotIn(field, ddl)

    def test_deduplicated_views_use_argmax_by_ingest_time(self) -> None:
        views = (CLICKHOUSE / "002_views.sql").read_text(encoding="utf-8")
        self.assertGreaterEqual(views.count("argMax("), 20)
        self.assertIn("GROUP BY event_id", views)
        self.assertIn("GROUP BY expectation_id", views)

    def test_views_are_explicit_security_definer_boundaries(self) -> None:
        views = (CLICKHOUSE / "002_views.sql").read_text(encoding="utf-8")
        self.assertEqual(views.count("DEFINER = CURRENT_USER SQL SECURITY DEFINER"), 5)

    def test_dashboard_views_cover_all_required_metrics(self) -> None:
        views = (CLICKHOUSE / "002_views.sql").read_text(encoding="utf-8")
        for metric in (
            "submission_rate",
            "median_submit_latency_ms",
            "rejection_count",
            "proof_attach_rate",
            "blocked_task_count",
        ):
            self.assertIn(metric, views)

    def test_submission_metrics_match_pod_sla_and_expected_roster(self) -> None:
        views = (CLICKHOUSE / "002_views.sql").read_text(encoding="utf-8")
        self.assertIn("expectation.pod_id = event.pod_id", views)
        self.assertIn("expectation.sla_code = event.sla_code", views)
        self.assertGreaterEqual(views.count("expectation.attendance_state = 'expected'"), 6)

    def test_superset_role_cannot_read_raw_tables(self) -> None:
        access = (CLICKHOUSE / "004_access.sql").read_text(encoding="utf-8")
        self.assertIn("REVOKE ALL ON checkin_analytics.checkin_events_raw FROM checkin_superset_reader", access)
        self.assertNotIn("GRANT SELECT ON checkin_analytics.checkin_events_raw TO checkin_superset_reader", access)
        self.assertIn("GRANT INSERT, SELECT(event_id, payload_hash)", access)

    def test_aggregate_history_survives_detail_ttl(self) -> None:
        archive = (CLICKHOUSE / "003_archive_rollups.sql").read_text(encoding="utf-8")
        self.assertEqual(archive.count("REFRESH EVERY 1 DAY OFFSET 2 HOUR"), 3)
        self.assertEqual(archive.count("INTERVAL 23 MONTH"), 9)
        self.assertEqual(archive.count("SQL SECURITY DEFINER"), 6)
        self.assertNotIn(" TTL ", archive.upper())
        for private_field in ("user_id", "user_name", "raw_submission", "tasks_md", "proof_links"):
            self.assertNotIn(private_field, archive)

    def test_superset_reads_reporting_views_only(self) -> None:
        access = (CLICKHOUSE / "004_access.sql").read_text(encoding="utf-8")
        self.assertEqual(access.count("GRANT SELECT ON checkin_analytics."), 3)
        self.assertEqual(access.count("_reporting TO checkin_superset_reader"), 3)
        self.assertEqual(access.count("_archive FROM checkin_superset_reader"), 3)


class SupersetTests(unittest.TestCase):
    def test_six_chart_assets_have_unique_uuids(self) -> None:
        charts = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((SUPERSET / "charts").glob("*.yaml"))]
        self.assertEqual(len(charts), 6)
        self.assertEqual(len({chart["uuid"] for chart in charts}), 6)
        self.assertTrue(all(chart["version"] == "1.0.0" for chart in charts))

    def test_chart_params_are_valid_json(self) -> None:
        for path in (SUPERSET / "charts").glob("*.yaml"):
            chart = yaml.safe_load(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.name):
                params = json.loads(chart["params"])
                self.assertEqual(params["viz_type"], chart["viz_type"])

    def test_three_datasets_are_read_only_aggregate_views(self) -> None:
        datasets = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((SUPERSET / "datasets").rglob("*.yaml"))]
        self.assertEqual(len(datasets), 3)
        self.assertEqual(
            {item["table_name"] for item in datasets},
            {
                "checkin_submission_metrics_reporting",
                "checkin_rejection_rules_reporting",
                "checkin_event_health_reporting",
            },
        )

    def test_dashboard_references_every_chart(self) -> None:
        dashboard = yaml.safe_load((SUPERSET / "dashboards" / "Daily_Checkin_Compliance.yaml").read_text(encoding="utf-8"))
        chart_ids = {yaml.safe_load(path.read_text(encoding="utf-8"))["uuid"] for path in (SUPERSET / "charts").glob("*.yaml")}
        self.assertEqual(set(dashboard["charts"]), chart_ids)
        self.assertFalse(dashboard["published"])
        metadata = json.loads(dashboard["metadata"])
        self.assertEqual(len(metadata["native_filter_configuration"]), 2)

    def test_database_export_contains_no_real_password(self) -> None:
        database = yaml.safe_load((SUPERSET / "databases" / "Daily_Checkin_ClickHouse.yaml").read_text(encoding="utf-8"))
        self.assertIn("XXXXXXXXXX", database["sqlalchemy_uri"])
        self.assertFalse(database["allow_dml"])
        self.assertFalse(database["allow_file_upload"])

    def test_superset_archive_matches_deterministic_builder(self) -> None:
        spec = importlib.util.spec_from_file_location("package_superset", ROOT / "scripts" / "package_superset.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = module.archive_bytes()
        self.assertEqual(SUPERSET_ARCHIVE.read_bytes(), expected)
        self.assertEqual(hashlib.sha256(SUPERSET_ARCHIVE.read_bytes()).hexdigest(), hashlib.sha256(expected).hexdigest())


if __name__ == "__main__":
    unittest.main()
