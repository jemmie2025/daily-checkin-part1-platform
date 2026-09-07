# Phase 4 Acceptance Matrix

## Local implementation evidence

| Control | Automated proof | State |
|---|---|---|
| IANA timezone due-time conversion | Fixed-clock and DST tests | Pass |
| User-local cycle date | Expectation contract tests | Pass |
| Approved leave suppression | Positive and negative leave tests | Pass |
| Global and pod holiday suppression | Scope tests | Pass |
| Inactive staff suppression | Denominator/action tests | Pass |
| SLA minus 60-minute nudge | Boundary fake-clock tests | Pass |
| PI-6 at SLA | Deterministic violation tests | Pass |
| Repeated scheduler safety | Stable action/violation ID tests | Pass |
| Late-arrival reconciliation | Resolution-without-checkin-write test | Pass |
| SLA plus 24-hour escalation | One-digest-per-pod test | Pass |
| Weekly pod rollup | Expected/submitted reconciliation tests | Pass |
| Importable n8n workflows | Deterministic export tests | Pass |

## Environment evidence still required

| Check | Required sanitized proof |
|---|---|
| Snapshot sources | Versioned roster, SLA, leave, and holiday metadata |
| Mattermost nudge | One isolated test-user DM with timestamp |
| Violation upsert | One row after two identical breach executions |
| Late resolution | Same violation resolved by one canonical check-in ID |
| Escalation | One pod-lead digest after a fake SLA plus 24 hours |
| Weekly rollup | Source fixture totals matching the posted summary |
| Scheduler health | Two weeks without a missed five-minute run |
