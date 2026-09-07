# Production Rollout Runbook

## Entry gate

- Every local check passes from a clean checkout.
- All environment evidence matrices are signed by their named owners.
- Part 2 passes the versioned event, snapshot, DLQ-context, and replay contracts.
- Backup restore, credential rotation, outage recovery, and event conflict tests
  pass in isolated staging.
- Dashboards reconcile and remain unpublished until the pilot is approved.

## Progressive rollout

1. Enable one pod with ten test users for three clean working days.
2. Review open p95/p99, rejection rate, SLA outcomes, DLQ count, event lag, and
   user feedback daily.
3. Add pods in approved batches while retaining a per-batch rollback boundary.
4. After two weeks with zero lost submissions, enable weekly lead rollups.
5. Require 95% on-time submission for four consecutive weeks before declaring
   the organizational rollout successful.

## Immediate abort conditions

- Any accepted submission is lost.
- A rejection writes Baserow or posts to a pod channel.
- Open p95 reaches two seconds during a sustained window.
- A raw task, proof URL, DLQ input, or credential enters telemetry or logs.
- A duplicate check-in, canonical post, violation, DLQ row, or event is created.
- A workload reads another workload's Vault object.

Rollback the affected component to its last reviewed artifact; do not disable
security controls to continue the pilot.
