CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_events_deduplicated
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    event_id,
    argMax(event_name, received_at) AS event_name,
    argMax(event_version, received_at) AS event_version,
    argMax(occurred_at, received_at) AS occurred_at,
    argMax(correlation_id, received_at) AS correlation_id,
    argMax(source, received_at) AS source,
    argMax(user_id, received_at) AS user_id,
    argMax(pod_id, received_at) AS pod_id,
    argMax(cycle_date, received_at) AS cycle_date,
    argMax(checkin_type, received_at) AS checkin_type,
    argMax(sla_code, received_at) AS sla_code,
    argMax(dialog_version, received_at) AS dialog_version,
    argMax(latency_ms, received_at) AS latency_ms,
    argMax(sla_status, received_at) AS sla_status,
    argMax(task_count, received_at) AS task_count,
    argMax(done_count, received_at) AS done_count,
    argMax(blocked_count, received_at) AS blocked_count,
    argMax(has_proof, received_at) AS has_proof,
    argMax(rule_ids, received_at) AS rule_ids,
    argMax(request_id, received_at) AS request_id,
    argMax(execution_id, received_at) AS execution_id,
    argMax(payload_hash, received_at) AS payload_hash,
    max(received_at) AS received_at
FROM checkin_analytics.checkin_events_raw
GROUP BY event_id;

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_expectations_deduplicated
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    expectation_id,
    argMax(user_id, updated_at) AS user_id,
    argMax(pod_id, updated_at) AS pod_id,
    argMax(timezone, updated_at) AS timezone,
    argMax(cycle_date, updated_at) AS cycle_date,
    argMax(checkin_type, updated_at) AS checkin_type,
    argMax(sla_code, updated_at) AS sla_code,
    argMax(sla_due_at, updated_at) AS sla_due_at,
    argMax(attendance_state, updated_at) AS attendance_state,
    argMax(roster_source_version, updated_at) AS roster_source_version,
    max(updated_at) AS updated_at
FROM checkin_analytics.checkin_expectations_raw
GROUP BY expectation_id;

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_submission_metrics_daily
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    cycle_date,
    pod_id,
    checkin_type,
    expected_count,
    submitted_count,
    greatest(expected_count - submitted_count, 0) AS missing_count,
    if(expected_count = 0, 0, submitted_count / expected_count) AS submission_rate,
    on_time_count,
    late_count,
    if(submitted_count = 0, 0, proof_count / submitted_count) AS proof_attach_rate,
    blocked_task_count,
    median_submit_latency_ms
FROM
(
    SELECT
        expectation.cycle_date AS cycle_date,
        expectation.pod_id AS pod_id,
        expectation.checkin_type AS checkin_type,
        uniqExactIf(expectation.user_id, expectation.attendance_state = 'expected') AS expected_count,
        uniqExactIf(event.user_id, expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted') AS submitted_count,
        uniqExactIf(event.user_id, expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted' AND event.sla_status = 'on_time') AS on_time_count,
        uniqExactIf(event.user_id, expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted' AND event.sla_status = 'late') AS late_count,
        uniqExactIf(event.user_id, expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted' AND event.has_proof = true) AS proof_count,
        sumIf(ifNull(event.blocked_count, 0), expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted') AS blocked_task_count,
        quantileExactIf(0.5)(event.latency_ms, expectation.attendance_state = 'expected' AND event.event_name = 'checkin.submitted') AS median_submit_latency_ms
    FROM checkin_analytics.checkin_expectations_deduplicated AS expectation
    LEFT JOIN checkin_analytics.checkin_events_deduplicated AS event
        ON expectation.user_id = event.user_id
        AND expectation.pod_id = event.pod_id
        AND expectation.cycle_date = event.cycle_date
        AND expectation.checkin_type = event.checkin_type
        AND expectation.sla_code = event.sla_code
    GROUP BY cycle_date, pod_id, checkin_type
);

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_rejection_rules_daily
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    cycle_date,
    pod_id,
    checkin_type,
    arrayJoin(rule_ids) AS rule_id,
    uniqExact(event_id) AS rejection_count
FROM checkin_analytics.checkin_events_deduplicated
WHERE event_name = 'checkin.rejected'
GROUP BY cycle_date, pod_id, checkin_type, rule_id;

CREATE VIEW IF NOT EXISTS checkin_analytics.checkin_event_health_daily
DEFINER = CURRENT_USER SQL SECURITY DEFINER AS
SELECT
    toDate(occurred_at) AS event_date,
    event_name,
    count() AS event_count,
    quantileExact(0.5)(latency_ms) AS p50_latency_ms,
    quantileExact(0.95)(latency_ms) AS p95_latency_ms,
    max(dateDiff('second', occurred_at, received_at)) AS max_ingestion_lag_seconds
FROM checkin_analytics.checkin_events_deduplicated
GROUP BY event_date, event_name;
