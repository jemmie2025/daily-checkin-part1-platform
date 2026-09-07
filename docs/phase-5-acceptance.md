# Phase 5 Acceptance Matrix

## Local implementation evidence

| Control | Automated proof | State |
|---|---|---|
| Exactly three total attempts | Retry policy tests | Pass |
| One/four-second bounded waits | Fake sleeper test | Pass |
| Retryable status taxonomy | HTTP classification tests | Pass |
| Sanitized failure summary | Credential redaction tests | Pass |
| Verbatim raw-input retention | Byte-equality test | Pass |
| Deterministic DLQ identity | Repeated-build test | Pass |
| Baserow identifier uniqueness | Field-map contract test | Pass |
| Resolved-row starvation prevention | Private filtered-view workflow assertion | Pass |
| Saved-execution reconciliation | Error-trigger plus five-minute scan assertions | Pass |
| Failure context minimization | Closed nested schema tests | Pass |
| Durable DM duplicate guard | Persisted `dm_notified_at` workflow assertions | Pass |
| Stage-aware replay | Three failure-stage plan tests | Pass |
| Active replay exclusion | Lease contention test | Pass |
| Stale replay recovery | Lease-expiry test | Pass |
| Original correlation/idempotency | Workflow export assertions | Pass |
| Resolved retention | 30-day timestamp test | Pass |
| Importable capture/replay workflows | Deterministic export tests | Pass |

## Environment evidence still required

| Check | Required sanitized proof |
|---|---|
| Baserow outage | Retained n8n execution and later single DLQ row |
| Replay view | View includes only pending/replaying rows and a pending fixture appears within one scan |
| n8n API scope | `execution:read` succeeds; edit/run/admin operations denied |
| User notification | One DM whose input hash matches the source execution |
| Recovery | One check-in, one post, and one event after replay |
| Lease contention | Two workers produce one active replay |
| Retention | Resolved test row removed only after approved window |
| Zero loss | Two continuous weeks with no unmatched failed execution |
