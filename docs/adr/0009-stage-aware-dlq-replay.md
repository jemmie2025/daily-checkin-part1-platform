# ADR-0009: Resume DLQ Replay from the Failed Side Effect

- Status: Accepted
- Date: 2026-09-04

## Context

A submission can fail while creating its Baserow row, posting its canonical
Mattermost reply, or dispatching telemetry. Restarting every side effect after
each failure risks duplicate rows, duplicate posts, and duplicate events.

## Decision

DLQ identity is `source_execution_id|failure_stage`. Replay acquires a
15-minute lease, retains the original correlation and replay keys, and resumes
from a stage-specific ordered plan:

| Failed stage | Replay plan |
|---|---|
| Baserow write | Upsert check-in, ensure post, ensure event |
| Mattermost post | Verify check-in, ensure post, ensure event |
| Event dispatch | Verify check-in, verify post, ensure event |

Every ensure operation uses the original canonical identity. A successful
replay resolves the row and starts a 30-day recovery retention window. A stale
lease can be recovered; an active lease cannot be stolen.

## Consequences

- Replay is safe under worker restarts and at-least-once execution.
- Part 2 must expose the versioned replay endpoint defined in the interface.
- Raw input remains confined to the DLQ worker and endpoint during recovery.
