# Backup and Disaster Recovery Runbook

## Objectives

| Component | Maximum RPO | Target RTO | Protected data |
|---|---:|---:|---|
| n8n execution database | 5 minutes | 60 minutes | Failed executions and workflow state |
| Baserow check-in tables | 15 minutes | 2 hours | Violations and restricted DLQ rows |
| ClickHouse | 60 minutes | 4 hours | Rebuildable event and expectation facts |
| Configuration repository | Every accepted change | 30 minutes | Workflows, contracts, policies, DDL, dashboards |
| Vault configuration | Every approved change | 60 minutes | Policies, roles, auth configuration; not exported secrets |

Backups must be encrypted, access-controlled, lifecycle-managed, and restored
quarterly in an isolated environment. Raw DLQ data must not be copied into a
general-purpose configuration archive.

## Restore order

1. Restore network, DNS, TLS, Vault, and workload identity.
2. Restore n8n's database and confirm failed-execution retention.
3. Restore Baserow and validate deterministic IDs before enabling writers.
4. Start Open, Submit, Compliance, DLQ, and Analytics tasks separately.
5. Restore ClickHouse replicas and reapply views/access grants.
6. Import the reviewed Grafana dashboard and leave it private.
7. Replay events by stable ID, reconcile source counts, then resume schedules.

## Pass criteria

The quarterly exercise passes only when RPO/RTO are met, all six Vault
identities remain isolated, no duplicate check-in/post/event is created, DLQ
text remains restricted, dashboard totals reconcile, and the exercise evidence
contains no secret or confidential payload.
