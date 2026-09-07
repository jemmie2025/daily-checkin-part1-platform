# Phase 7 Acceptance Matrix

## Local implementation evidence

| Control | Automated proof | State |
|---|---|---|
| Five explicit SLOs | SLO schema tests | Pass |
| Critical SLO alert mapping | Alert-to-SLO tests | Pass |
| Submission durability target 100% | Fail-closed SLO test | Pass |
| Privacy-safe telemetry labels | Allow/deny-list tests | Pass |
| Open p95/p99 load thresholds | k6 script tests | Pass |
| Gateway quota/body/method tests | k6 control script tests | Pass |
| Passive security scan plan | ZAP plan tests | Pass |
| Pinned least-privilege CI | Workflow security tests | Pass |
| Backup/restore procedure | Runbook completeness tests | Pass |
| Incident and rollback procedure | Runbook completeness tests | Pass |
| Deterministic release manifest | Hash verification test | Pass |
| One-command full validation | Makefile/CI test | Pass |

## Environment evidence still required

| Check | Required sanitized proof |
|---|---|
| Performance | 30+ real open samples and k6 p95 below 1.8 seconds |
| Security | ZAP report reviewed with no unresolved high finding |
| Failure exercises | Gateway, Baserow, ClickHouse, and worker outage results |
| Restore | Quarterly isolated restore inside stated RPO/RTO |
| Pilot | One pod, ten users, three clean working days |
| Durability | Two weeks with zero lost submissions |
| Adoption | 95% on-time submissions for four consecutive weeks |
| Sign-off | Platform, security, data, compliance, and product approvals |
