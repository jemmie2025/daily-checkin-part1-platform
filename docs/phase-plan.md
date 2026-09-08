# Part 1 Configuration Delivery Plan

Task #5585 reuses the company-managed platform. Each phase delivers configuration
and verification for that platform; it does not provision APISIX, Vault, Nomad,
Consul, Loki, Grafana, or ClickHouse. Work begins with Phases 1–4.

## Phase 1 — Foundation and contracts

Deliverables:

- Existing-platform connection map, ownership boundary, schemas, ADRs, security
  policy, access register, risk register, and CI validation.
- ClickHouse analytical-copy contracts for check-in, expectation, violation,
  and DLQ lifecycle facts, with Grafana as the reporting surface.
- Deterministic idempotency, privacy, and writer-authority rules.

Status: **locally validated**. Contract-review approval remains an environment
gate.

## Phase 2 — APISIX gateway

Deliverables:

- Separate POST-only Open and Submit routes.
- Mattermost source CIDR allowlist, 64 KiB body limit, TLS upstream, Redis-backed
  10 requests/minute per-user limit, sanitized logging, and asynchronous
  `checkin.opened` telemetry.
- Deterministic configuration rendering, change preview, rollback, and smoke-test tooling.

Status: **locally validated**. Plugin loading, live source-IP/body/rate tests,
rollback, and `/ci` latency evidence require staging APISIX access.

## Phase 3 — Vault and Nomad security

Deliverables:

- Exact-path KV v2 policy overlays, claim-bound workload-role bindings, isolated
  identities, runtime templates, integration preflights, and rotation runbook.
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

Reliability/DLQ, ClickHouse/Grafana analytics, and production-hardening assets
may exist in the working tree as prepared future work. They are not claimed as
accepted or applied by v0.5.0 and require separate phase gates.

## Checkpoint exit

Run `make validate` with zero failures, review the Phase 1–4 evidence files, and
then execute the staging acceptance matrices only after the required company
access has been granted.
