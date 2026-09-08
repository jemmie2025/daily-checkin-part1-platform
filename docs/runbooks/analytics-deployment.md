# ClickHouse and Grafana Configuration Runbook

## Configure existing ClickHouse

1. Confirm Keeper, replicas, TLS verification, backups, and the target database.
2. Apply `analytics/clickhouse/001_schema.sql`, `002_views.sql`,
   `003_archive_rollups.sql`, and `004_access.sql` in that order using the
   schema-owner identity.
3. Create separate credentials for `checkin_event_ingestor` and
   `checkin_grafana_reader`; store them in the approved secret systems.
4. Verify the ingestor can insert and can select only `event_id` plus
   `payload_hash`. Verify the Grafana identity can read only the three
   reporting views and is denied on raw and archive tables.
5. Inspect both 24-month TTLs and monthly partitions.
6. Inspect all three rows in `system.view_refreshes`, trigger an isolated manual
   refresh, and verify one aggregate row replaces safely on repeated refresh.
7. Backfill already-old aggregate dates before enabling the detail TTL; reconcile
   every date and record only counts/hashes as evidence.

## Activate ingestion

1. Import Event Ingestion and Expectation Ingestion into `n8n-analytics`.
2. Inject the shared producer token and ClickHouse identity from Vault.
3. Send all four canonical event fixtures twice. Expect 202 on first delivery
   and 200 on identical retry, with one deduplicated row per `event_id`.
4. Reuse an ID with changed content. Expect 409 and the conflict alert.
5. Confirm no confidential field appears in table columns, logs, or errors.

## Import into existing Grafana

Validate with `make grafana`, import
`analytics/grafana/daily-checkin-compliance.json`, and map
`DS_CHECKIN_CLICKHOUSE` to the approved secret-backed ClickHouse datasource.
Keep the dashboard private until every panel reconciles with the ClickHouse
reporting views for three clean pilot days.

## Rollback

Deactivate ingestion without blocking check-in submission. Restore the prior
reviewed views and dashboard version. Do not delete raw partitions during an
incident; replay stable event IDs after recovery and verify deduplication.
