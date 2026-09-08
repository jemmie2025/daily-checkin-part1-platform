# Daily Check-in Operational Handbook

| Responsibility | Primary guide |
|---|---|
| APISIX configuration | `docs/runbooks/apisix-deployment.md` |
| Vault integration and rotation | `docs/runbooks/vault-deployment-and-rotation.md` |
| Compliance and PI-6 | `docs/runbooks/compliance-operations.md` |
| DLQ recovery | `docs/runbooks/dlq-operations.md` |
| ClickHouse and Grafana | `docs/runbooks/analytics-deployment.md` |
| Incident response | `docs/runbooks/incident-response.md` |
| Backup and restore | `docs/runbooks/disaster-recovery.md` |
| Progressive rollout | `docs/runbooks/production-rollout.md` |

The on-call order is: preserve submissions, restore `/ci` open, restore
compliance, restore analytics, reconcile, and communicate. The repository is
the reviewed configuration source; live credentials and private evidence never
belong in it.
