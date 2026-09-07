# ADR-0008: Deduplicate Events at Ingest and Query Boundaries

- Status: Accepted
- Date: 2026-09-04

## Context

Part 2 and APISIX deliver events at least once. A retry can repeat the same
event, while reuse of one `event_id` for different content is a producer defect
that must never be silently accepted. Materialized counters built directly from
raw inserts would be inflated before background merges complete.

## Decision

The ingestion workflow authenticates the producer, validates the strict v1
contract, removes nested content, computes a canonical SHA-256 payload hash,
and queries `event_id` before insert. The same ID and hash returns HTTP 200. A
new ID is inserted with `insert_deduplication_token` and returns HTTP 202. The
same ID with a different hash returns HTTP 409 and pages the data owner.

ClickHouse stores rows in `ReplicatedReplacingMergeTree`, while every Superset
dataset reads a query-time `argMax` deduplicated view. No aggregate is computed
directly from the raw insert stream.

Detail rows expire after 24 months. At month 23, refreshable materialized views
append aggregate-only daily snapshots to ReplacingMergeTree archives without a
TTL. Security-definer reporting views expose recent metrics plus archive
history while the Superset identity remains denied on all physical tables.

## Consequences

- Retries do not inflate dashboard metrics.
- Event-ID conflicts are visible and fail closed.
- Keeper and replica health are production dependencies.
- The raw table remains unavailable to the Superset role.
