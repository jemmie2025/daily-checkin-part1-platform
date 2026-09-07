CREATE DATABASE IF NOT EXISTS checkin_analytics;

CREATE TABLE IF NOT EXISTS checkin_analytics.checkin_events_raw
(
    event_id UUID,
    event_name LowCardinality(String),
    event_version UInt16,
    occurred_at DateTime64(3, 'UTC'),
    received_at DateTime64(3, 'UTC') DEFAULT now64(3),
    correlation_id String,
    source LowCardinality(String),
    user_id String,
    pod_id LowCardinality(String),
    cycle_date Date,
    checkin_type LowCardinality(String),
    sla_code LowCardinality(String),
    dialog_version LowCardinality(String),
    latency_ms UInt32,
    sla_status Nullable(LowCardinality(String)),
    task_count Nullable(UInt8),
    done_count Nullable(UInt8),
    blocked_count Nullable(UInt8),
    has_proof Nullable(Bool),
    rule_ids Array(String),
    request_id String,
    execution_id Nullable(String),
    payload_hash FixedString(64),
    CONSTRAINT valid_event_name CHECK event_name IN ('checkin.opened', 'checkin.submitted', 'checkin.rejected', 'checkin.cancelled'),
    CONSTRAINT valid_checkin_type CHECK checkin_type IN ('SOD', 'EOD', 'ADHOC'),
    CONSTRAINT valid_task_count CHECK task_count IS NULL OR task_count <= 20,
    CONSTRAINT valid_done_count CHECK done_count IS NULL OR done_count <= 20,
    CONSTRAINT valid_blocked_count CHECK blocked_count IS NULL OR blocked_count <= 20,
    CONSTRAINT valid_task_state_counts CHECK task_count IS NULL OR ifNull(done_count, 0) + ifNull(blocked_count, 0) <= task_count
)
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/checkin_analytics/checkin_events_raw', '{replica}', received_at)
PARTITION BY toYYYYMM(occurred_at)
ORDER BY event_id
TTL occurred_at + INTERVAL 24 MONTH DELETE
SETTINGS index_granularity = 8192, replicated_deduplication_window = 100000;

CREATE TABLE IF NOT EXISTS checkin_analytics.checkin_expectations_raw
(
    expectation_id String,
    user_id String,
    pod_id LowCardinality(String),
    timezone LowCardinality(String),
    cycle_date Date,
    checkin_type LowCardinality(String),
    sla_code LowCardinality(String),
    sla_due_at DateTime64(3, 'UTC'),
    attendance_state LowCardinality(String),
    roster_source_version String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64(3),
    CONSTRAINT valid_expectation_type CHECK checkin_type IN ('SOD', 'EOD'),
    CONSTRAINT valid_attendance_state CHECK attendance_state IN ('expected', 'approved_leave', 'holiday', 'inactive')
)
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/checkin_analytics/checkin_expectations_raw', '{replica}', updated_at)
PARTITION BY toYYYYMM(cycle_date)
ORDER BY (cycle_date, pod_id, checkin_type, expectation_id)
TTL toDateTime(cycle_date, 'UTC') + INTERVAL 24 MONTH DELETE
SETTINGS index_granularity = 8192, replicated_deduplication_window = 100000;
