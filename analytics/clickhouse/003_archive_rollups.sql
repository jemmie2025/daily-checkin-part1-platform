-- Aggregate-only retention beyond the 24-month detail window.
-- Refreshes copy each day at month 23, leaving a one-month safety buffer.

CREATE TABLE IF NOT EXISTS checkin_analytics.checkin_submission_metrics_archive
(
    cycle_date Date,
    pod_id LowCardinality(String),
    checkin_type LowCardinality(String),
    expected_count UInt64,
    submitted_count UInt64,
    missing_count UInt64,
    submission_rate Float64,
    on_time_count UInt64,
    late_count UInt64,
    proof_attach_rate Float64,
    blocked_task_count UInt64,
    median_submit_latency_ms Float64,
    archived_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/checkin_analytics/checkin_submission_metrics_archive', '{replica}', archived_at)
PARTITION BY toYYYY(cycle_date)
ORDER BY (cycle_date, pod_id, checkin_type);

CREATE TABLE IF NOT EXISTS checkin_analytics.checkin_rejection_rules_archive
(
    cycle_date Date,
    pod_id LowCardinality(String),
    checkin_type LowCardinality(String),
    rule_id LowCardinality(String),
    rejection_count UInt64,
    archived_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/checkin_analytics/checkin_rejection_rules_archive', '{replica}', archived_at)
PARTITION BY toYYYY(cycle_date)
ORDER BY (cycle_date, pod_id, checkin_type, rule_id);

CREATE TABLE IF NOT EXISTS checkin_analytics.checkin_event_health_archive
(
    event_date Date,
    event_name LowCardinality(String),
    event_count UInt64,
    p50_latency_ms Float64,
    p95_latency_ms Float64,
    max_ingestion_lag_seconds Int64,
    archived_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/checkin_analytics/checkin_event_health_archive', '{replica}', archived_at)
PARTITION BY toYYYY(event_date)
ORDER BY (event_date, event_name);

CREATE MATERIALIZED VIEW IF NOT EXISTS checkin_analytics.archive_submission_metrics_daily
REFRESH EVERY 1 DAY OFFSET 2 HOUR
SETTINGS refresh_retries = 5,
         refresh_retry_initial_backoff_ms = 1000,
         refresh_retry_max_backoff_ms = 60000
APPEND TO checkin_analytics.checkin_submission_metrics_archive
EMPTY
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT *, now64(3) AS archived_at
FROM checkin_analytics.checkin_submission_metrics_daily
WHERE cycle_date = toDate(today() - INTERVAL 23 MONTH);

CREATE MATERIALIZED VIEW IF NOT EXISTS checkin_analytics.archive_rejection_rules_daily
REFRESH EVERY 1 DAY OFFSET 2 HOUR
SETTINGS refresh_retries = 5,
         refresh_retry_initial_backoff_ms = 1000,
         refresh_retry_max_backoff_ms = 60000
APPEND TO checkin_analytics.checkin_rejection_rules_archive
EMPTY
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT *, now64(3) AS archived_at
FROM checkin_analytics.checkin_rejection_rules_daily
WHERE cycle_date = toDate(today() - INTERVAL 23 MONTH);

CREATE MATERIALIZED VIEW IF NOT EXISTS checkin_analytics.archive_event_health_daily
REFRESH EVERY 1 DAY OFFSET 2 HOUR
SETTINGS refresh_retries = 5,
         refresh_retry_initial_backoff_ms = 1000,
         refresh_retry_max_backoff_ms = 60000
APPEND TO checkin_analytics.checkin_event_health_archive
EMPTY
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT *, now64(3) AS archived_at
FROM checkin_analytics.checkin_event_health_daily
WHERE event_date = toDate(today() - INTERVAL 23 MONTH);

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_submission_metrics_reporting
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    cycle_date, pod_id, checkin_type, expected_count, submitted_count,
    missing_count, submission_rate, on_time_count, late_count,
    proof_attach_rate, blocked_task_count, median_submit_latency_ms
FROM checkin_analytics.checkin_submission_metrics_daily
WHERE cycle_date >= toDate(today() - INTERVAL 23 MONTH)
UNION ALL
SELECT
    cycle_date, pod_id, checkin_type, expected_count, submitted_count,
    missing_count, submission_rate, on_time_count, late_count,
    proof_attach_rate, blocked_task_count, median_submit_latency_ms
FROM checkin_analytics.checkin_submission_metrics_archive FINAL
WHERE cycle_date < toDate(today() - INTERVAL 23 MONTH);

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_rejection_rules_reporting
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT cycle_date, pod_id, checkin_type, rule_id, rejection_count
FROM checkin_analytics.checkin_rejection_rules_daily
WHERE cycle_date >= toDate(today() - INTERVAL 23 MONTH)
UNION ALL
SELECT cycle_date, pod_id, checkin_type, rule_id, rejection_count
FROM checkin_analytics.checkin_rejection_rules_archive FINAL
WHERE cycle_date < toDate(today() - INTERVAL 23 MONTH);

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_event_health_reporting
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT event_date, event_name, event_count, p50_latency_ms, p95_latency_ms, max_ingestion_lag_seconds
FROM checkin_analytics.checkin_event_health_daily
WHERE event_date >= toDate(today() - INTERVAL 23 MONTH)
UNION ALL
SELECT event_date, event_name, event_count, p50_latency_ms, p95_latency_ms, max_ingestion_lag_seconds
FROM checkin_analytics.checkin_event_health_archive FINAL
WHERE event_date < toDate(today() - INTERVAL 23 MONTH);
