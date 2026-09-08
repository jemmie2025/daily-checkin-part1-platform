# ADR-0010: Reuse Existing Platforms and Centralize Analytics in ClickHouse

- Status: Accepted by project direction
- Date: 2026-09-07

## Context

The company already operates Nomad, Consul, Vault, Loki, Grafana, and APISIX.
The Part 1 proposal must describe how Task #5585 is configured on those services,
not propose new installations. Project direction also removes Superset, avoids
Airflow, and requires the final privacy-safe analytical record in ClickHouse.

## Decision

Part 1 will deliver configuration overlays for existing services. n8n remains
the lightweight orchestration DAG. Baserow remains the operational persistence
layer required by the task, while ClickHouse receives check-in telemetry,
expectations, violation facts, and DLQ lifecycle facts. Grafana reads only
ClickHouse reporting views. Superset and Airflow are not used.

## Consequences

- Existing platform ownership and change controls are preserved.
- No duplicate APISIX, Vault, Nomad, Consul, Loki, or Grafana deployment is
  introduced.
- ClickHouse becomes the single analytics and audit destination.
- Raw task content, proof URLs, usernames, and raw DLQ submissions remain out of
  ClickHouse.
- Baserow-to-ClickHouse consistency needs reconciliation and lag monitoring.
- Removal of Superset must be recorded against the original acceptance text.
