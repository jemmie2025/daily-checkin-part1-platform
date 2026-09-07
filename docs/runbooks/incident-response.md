# Incident Response Runbook

## First five minutes

1. Declare the incident, timestamp it in UTC, and assign incident commander,
   operations lead, and communications lead.
2. Protect submission durability first, then restore the open path, compliance,
   and analytics in that order.
3. Freeze deployments and credential changes unrelated to mitigation.
4. Use correlation, request, execution, event, violation, and DLQ IDs. Never
   copy raw tasks, proof links, tokens, or DLQ text into the incident channel.

## Open Handler

Check APISIX upstream latency, n8n task health, Mattermost response status, and
rate-limit/allowlist changes. If p95 approaches 1.8 seconds, remove synchronous
enrichment and roll back the latest gateway/workflow version. Do not relax TLS,
source restrictions, authentication, or the body limit.

## Submission durability

If a submission is neither stored nor present in a retained failed execution,
stop the Submit workflow and page the data owner immediately. Preserve n8n
execution storage, restore the dependency, and reconcile by correlation ID.
Never ask users to resubmit until the original state is known.

## Event ID conflict

Quarantine the producer path for the conflicting ID, compare only canonical
payload hashes and sanitized fields, and determine whether the producer reused
an ID or mutated a retry. Do not overwrite the existing event. Resume after the
producer fixes its deterministic-ID behavior.

## Credential exposure

Revoke at the downstream system, stop the affected workload, rotate the exact
Vault object, verify the old credential is rejected, scan retained artifacts,
and restart only the isolated task. Follow the Vault rotation runbook.

## Closure

Reconcile accepted submissions, violations, DLQ rows, posts, and events. Record
impact, detection, timeline, root cause, corrective actions, owners, and due
dates. Close only after alerts are clear and a regression test exists.
