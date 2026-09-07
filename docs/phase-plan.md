# Part 1 Phase 1–4 Checkpoint

This v0.4.0 checkpoint implements and validates Phases 1–4 locally. It does not
claim company-environment deployment. Live completion depends on approved
endpoints, identities, permissions, network paths, and evidence supplied by the
company environment.

## Phase 1 — Foundation and contracts

Deliverables:

- Repository structure, ownership boundary, schemas, ADRs, security policy,
  access register, risk register, and CI validation.
- Deterministic idempotency, privacy, and writer-authority rules.

Status: **locally validated**. Contract-review approval remains an environment
gate.

## Phase 2 — APISIX gateway

Deliverables:

- Separate POST-only Open and Submit routes.
- Mattermost source CIDR allowlist, 64 KiB body limit, TLS upstream, Redis-backed
  10 requests/minute per-user limit, sanitized logging, and asynchronous
  `checkin.opened` telemetry.
- Deterministic policy rendering, dry-run deployment, and smoke-test tooling.

Status: **locally validated**. Plugin loading, live source-IP/body/rate tests,
rollback, and `/ci` latency evidence require staging APISIX access.

## Phase 3 — Vault and Nomad security

Deliverables:

- Exact-path KV v2 policies, claim-bound workload roles, isolated identities,
  runtime templates, deployment preflights, and rotation runbook.
- Repository and Git-history credential scanning.

Status: **locally validated**. Live JWT exchange, cross-role denial, audit,
restart, rotation, revocation, and restore evidence require Vault/Nomad access.

## Phase 4 — Compliance automation

Deliverables:

- Versioned, minimized Compliance Source API contract for roster, pod, timezone,
  SLA, holiday, leave, and accepted-submission snapshots.
- SLA −60-minute nudges, PI-6 breach upserts, SLA +24-hour pod-lead digests,
  late-arrival reconciliation, and weekly pod rollups.
- Timezone, suppression, freshness, duplicate, and idempotency tests.

Status: **locally validated**. Live schedules, DMs, Baserow writes, source
freshness, and two-week scheduler evidence require company integrations.

## Phases 5–7 — outside this checkpoint

Reliability/DLQ, ClickHouse/Superset analytics, and production-hardening assets
may exist in the working tree as prepared future work. They are not claimed as
accepted or deployed by v0.4.0 and require separate phase gates.

## Checkpoint exit

Run `make validate` with zero failures, review the Phase 1–4 evidence files, and
then execute the staging acceptance matrices only after the required company
access has been granted.
