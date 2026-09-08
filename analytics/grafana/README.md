# Existing Grafana Integration

This folder contains configuration to import into the company-managed Grafana
instance. It does not install Grafana.

## Connection

1. An administrator maps `DS_CHECKIN_CLICKHOUSE` to the approved ClickHouse
   datasource using the official Grafana ClickHouse datasource plugin.
2. The datasource authenticates as `checkin_grafana_reader`; the password is
   supplied from the company secret store and is never committed.
3. The role can read only the three security-definer reporting views.
4. Import `daily-checkin-compliance.json` unpublished, reconcile counts, and
   publish only after the phase acceptance gate succeeds.

The dashboard contains six panels: submission rate, median submit latency,
rejection rules, proof attachment rate, blocked-task trend, and on-time versus
late submissions.
