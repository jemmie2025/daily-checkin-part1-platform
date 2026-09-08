# Baserow Part 1 tables

This directory defines only the two tables written by Part 1. The Part 2 owner
provisions `checkins` and supplies its table identifier through the published
interface.

## Invariants

- `n8n-compliance` is the only writer to `checkin_violations`.
- `n8n-dlq` is the only writer to `checkin_dlq`.
- `violation_id` and `dlq_id` must have Baserow uniqueness constraints; the
  workflows also filter before creation so normal retries avoid constraint
  conflicts.
- `raw_submission` is restricted to DLQ operators and is never copied to logs,
  ClickHouse, Grafana, Redmine, or screenshots.
- Resolved DLQ rows receive `retention_delete_after`; deletion is performed by
  the approved retention job after the 30-day recovery window.
- Create a private grid view named `checkin_dlq_replay_pending` that includes
  only `pending` and `replaying` rows. Bind its ID as
  `BASEROW_DLQ_REPLAY_VIEW_ID`; the replay worker still enforces due time and
  lease age itself. This prevents old resolved rows from starving the queue.

Use `field-map.yaml` during schema review. Record the resulting table and field
IDs in the deployment secret/configuration channel, never in this repository.
Fail the staging gate if either uniqueness constraint or the filtered replay
view is absent.
