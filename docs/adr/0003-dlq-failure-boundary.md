# ADR-0003: Keep the Durable DLQ Boundary Outside Baserow

- Status: Accepted
- Date: 2026-09-04

## Context

A failed Baserow `checkins` write must be preserved in `checkin_dlq`. During a
complete Baserow outage, writing the DLQ row to the same service is impossible.

## Decision

After three bounded attempts, the n8n execution database retains the complete
failed execution as the durable source. The error workflow immediately attempts
the required user DM and creates the Baserow DLQ audit row when Baserow is
available. A reconciliation job mirrors any unrecorded failures after recovery.
The job runs every five minutes, reads only failed Submit executions through an
`execution:read` internal API identity, and extracts the closed
`submit-failure-context.v1` object saved immediately before the failed side
effect. Deterministic `dlq_id` plus a Baserow uniqueness constraint makes the
immediate and scheduled paths converge on one row.

## Consequences

- A Baserow outage cannot erase the user's input.
- Baserow remains the operator-facing replay and audit surface.
- n8n execution retention must exceed the maximum outage and replay window.
- Raw input is excluded from ordinary logs and ClickHouse.
