# Phase 6 Acceptance Matrix

## Local implementation evidence

| Control | Automated proof | State |
|---|---|---|
| Strict four-event contract | Contract and flattening tests | Pass |
| Explicit auth/contract failures | Runtime 401/400 branch tests | Pass |
| Forbidden telemetry fields | Recursive privacy tests | Pass |
| Canonical payload hash | Key-order test | Pass |
| Duplicate returns 200 | Event ledger test | Pass |
| Conflicting duplicate rejected | Event ledger and workflow test | Pass |
| Replicated insert deduplication | DDL/workflow assertions | Pass |
| Query-time deduplicated views | `argMax` view tests | Pass |
| 24-month detail retention | TTL tests | Pass |
| Aggregate retention thereafter | Three day-23 refresh and reporting-union tests | Pass |
| Expected-roster denominator | Metric reconciliation test | Pass |
| Six required charts | Superset asset tests | Pass |
| Read-only Superset identity | ClickHouse grant tests | Pass |
| Definer-view boundary | Explicit SQL security tests | Pass |
| Deterministic dashboard archive | Byte-for-byte package test | Pass |

## Environment evidence still required

| Check | Required sanitized proof |
|---|---|
| Keeper/replica health | Cluster health and replica lag summary |
| Four event types | First delivery 202, repeat 200, one deduplicated row |
| Conflict | Changed payload with same ID returns 409 and alerts |
| Retention | `system.tables` TTL inspection with no payload values |
| Aggregate refresh | Three healthy `system.view_refreshes` rows and reconciled archive fixture |
| Role denial | Superset denied on both raw tables |
| Dashboard reconciliation | All six chart totals match source fixtures |
| Lead self-service | Approved lead opens filtered weekly view unaided |
