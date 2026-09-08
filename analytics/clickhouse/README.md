# Existing ClickHouse integration

Apply all four numbered configuration files to the company-managed ClickHouse
service in order with a reviewed schema-owner identity.
The production DDL uses `ReplicatedReplacingMergeTree`, Keeper insert
deduplication, stable `event_id` tokens, query-time deduplicated views, and a
24-month detail TTL.

At month 23, three refreshable materialized views copy aggregate-only daily
metrics to no-TTL archive tables, leaving a one-month safety buffer before
detail deletion. Reporting views combine current detail-derived metrics with
the archive. Monitor `system.view_refreshes`; a failed archive refresh is a
retention incident. Before first activation, backfill any already-old dates in
an isolated change window and reconcile counts before allowing the raw TTL.

The ingestion role can insert sanitized event/expectation rows and read only
`event_id` plus `payload_hash` for conflict detection. Grafana receives only
the three security-definer reporting views and is explicitly denied both raw
and archive tables. The schema-owner/definer must be a non-login deployment
identity after installation. Neither raw table contains task text or proof URLs.

Passwords are provisioned through the platform identity process and stored in
Vault. They must never be added to SQL or Grafana dashboard files.
