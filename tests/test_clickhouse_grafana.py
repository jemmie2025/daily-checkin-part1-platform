from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLICKHOUSE = ROOT / "analytics" / "clickhouse"
GRAFANA = ROOT / "analytics" / "grafana"


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

    def test_dashboard_views_cover_required_metrics(self) -> None:
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

    def test_grafana_role_reads_only_reporting_views(self) -> None:
        access = (CLICKHOUSE / "004_access.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE ROLE IF NOT EXISTS checkin_grafana_reader", access)
        self.assertEqual(access.count("_reporting TO checkin_grafana_reader"), 3)
        self.assertEqual(access.count("_archive FROM checkin_grafana_reader"), 3)
        self.assertIn("REVOKE ALL ON checkin_analytics.checkin_events_raw FROM checkin_grafana_reader", access)
        self.assertNotIn("GRANT SELECT ON checkin_analytics.checkin_events_raw TO checkin_grafana_reader", access)
        self.assertIn("GRANT INSERT, SELECT(event_id, payload_hash)", access)

    def test_aggregate_history_survives_detail_ttl(self) -> None:
        archive = (CLICKHOUSE / "003_archive_rollups.sql").read_text(encoding="utf-8")
        self.assertEqual(archive.count("REFRESH EVERY 1 DAY OFFSET 2 HOUR"), 3)
        self.assertEqual(archive.count("INTERVAL 23 MONTH"), 9)
        self.assertEqual(archive.count("SQL SECURITY DEFINER"), 6)
        self.assertNotIn(" TTL ", archive.upper())
        for private_field in ("user_id", "user_name", "raw_submission", "tasks_md", "proof_links"):
            self.assertNotIn(private_field, archive)


class GrafanaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dashboard = json.loads(
            (GRAFANA / "daily-checkin-compliance.json").read_text(encoding="utf-8")
        )

    def test_dashboard_has_six_unique_panels(self) -> None:
        panels = self.dashboard["panels"]
        self.assertEqual(len(panels), 6)
        self.assertEqual(len({panel["id"] for panel in panels}), 6)
        self.assertEqual(
            {panel["title"] for panel in panels},
            {
                "Submission Rate",
                "Median Submit Latency",
                "Top Rejection Rules",
                "Proof Attachment Rate",
                "Blocked Task Trend",
                "On-time versus Late",
            },
        )

    def test_dashboard_uses_clickhouse_input_and_reporting_views_only(self) -> None:
        self.assertEqual(self.dashboard["__inputs"][0]["pluginId"], "grafana-clickhouse-datasource")
        serialized = json.dumps(self.dashboard)
        self.assertIn("${DS_CHECKIN_CLICKHOUSE}", serialized)
        self.assertNotIn("checkin_events_raw", serialized)
        self.assertNotIn("checkin_expectations_raw", serialized)
        for panel in self.dashboard["panels"]:
            for target in panel["targets"]:
                self.assertIn("_reporting", target["rawSql"])

    def test_dashboard_is_safe_for_reviewed_import(self) -> None:
        self.assertIsNone(self.dashboard["id"])
        self.assertFalse(self.dashboard["editable"])
        self.assertEqual(self.dashboard["timezone"], "utc")
        self.assertEqual(self.dashboard["uid"], "daily-checkin-compliance-v1")


if __name__ == "__main__":
    unittest.main()
