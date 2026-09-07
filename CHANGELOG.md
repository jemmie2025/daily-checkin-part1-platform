# Changelog

All notable changes follow Keep a Changelog conventions. Versions use semantic
versioning for repository artifacts and explicit integer versions for data
contracts.

## [Unreleased]

Prepared Phase 5–7 assets remain outside the accepted v0.4.0 checkpoint and
must pass their separate company-environment gates before release.

## [0.4.0] - 2026-09-07

### Added

- Deterministic compliance engine for IANA timezones, local cycle dates,
  approved leave, global/pod holidays, SLA nudges, PI-6 breaches, late-arrival
  resolution, pod escalation digests, and weekly rollups.
- Three inactive, importable Phase 4 compliance workflows rendered from
  separately reviewed Code nodes.
- Platform-neutral Compliance Source API contracts for roster, timezone, SLA,
  calendar, and accepted-submission inputs.
- Complete least-privilege company-access register, Friendy request note, and
  one-command WSL bootstrap.

### Changed

- Phase 1–4 status now distinguishes local validation from live company
  deployment and environment evidence.
- SLA and compliance inputs use an approved platform-neutral source contract.

## Prepared after v0.4.0 — not released

### Added

- Deterministic compliance engine for IANA timezones, local cycle dates,
  approved leave, global/pod holidays, SLA nudges, PI-6 breaches, late-arrival
  resolution, pod escalation digests, and weekly rollups.
- Six inactive, importable n8n workflows rendered from separately reviewed Code
  nodes, including saved-execution DLQ reconciliation and stage-aware replay.
- Strict reliability contracts, three-attempt reference policy, deterministic
  DLQ identities, persisted failure-DM receipts, 15-minute replay leases, and
  30-day resolved retention markers.
- ClickHouse event and expectation schemas, ingest/query deduplication,
  security-definer views, 24-month detail TTLs, and aggregate-only archival.
- Deterministic Superset native-import package with two filters and six required
  charts.
- Five SLOs, Prometheus recording and alert rules, k6 plans, passive ZAP plan,
  incident/restore/rollout runbooks, acceptance matrices, and immutable release
  controls.
- Node.js runtime tests for authentication, nested event validation, privacy,
  and fail-closed ingestion responses.

### Changed

- Expanded to six isolated workload identities and eight exact-path Vault KV v2
  objects, including dedicated analytics and shared event-ingestion boundaries.
- Superset now reads reporting views only; raw and archive tables remain denied.
- Part 1/Part 2 integration requirements are published as versioned failure,
  replay, compliance, and event contracts.

### Security

- Event ingestion uses constant-time producer-token comparison and returns
  explicit 401/400 responses before ClickHouse access.
- DLQ reconciliation reads failed executions through a read-only internal n8n
  API credential delivered only to the isolated DLQ worker.
- Baserow deterministic identifiers are required to have uniqueness constraints.

## [0.3.0] - 2026-09-04

### Added

- Five least-privilege Vault policies and claim-bound Nomad JWT roles.
- Six-object KV v2 secret inventory below the required logical prefix.
- Deterministic Nomad runtime templates with no application-visible Vault token.
- Dry-run-first Vault deployment with health, audit, engine, auth-mount, TLS, and
  snapshot preflights.
- Sanitized live access/isolation/rotation harness and operational runbook.
- Working-tree and Git-history credential leak gate.
- Phase 3 architecture decision, acceptance matrix, and validation evidence.

### Changed

- APISIX credentials now use Vault-rendered `$ENV://` references, removing the
  KV v1 compatibility dependency from the APISIX 3.18 direct integration.
- Required dedicated n8n task boundaries are explicit and machine-validated.

## [0.2.0] - 2026-09-04

### Added

- APISIX 3.18.x resource renderer for isolated Open and Submit routes.
- 64 KiB body cap, source CIDR allowlist, distributed per-user throttling,
  correlation IDs, HTTPS upstream, and sanitized asynchronous access telemetry.
- `checkin-context` APISIX plugin for safe user-key extraction and internal
  header handling.
- Dry-run-first Admin API deployment tool with plugin preflight and snapshots.
- Explicit staging smoke-test harness and APISIX deployment runbook.
- Phase 2 policy, reproducibility, security, and fail-closed tests.

### Changed

- Clarified that APISIX applies abuse throttling after source allowlisting;
  Mattermost token/signature verification remains the first n8n processing step.

## [0.1.0] - 2026-09-04

### Added

- Phase 1 repository foundation for Task #5585 Part 1.
- Versioned event, violation, DLQ, and expected-check-in contracts.
- Independent Part 1/Part 2 ownership boundary.
- ADRs resolving missing-check-in, opened-event, and DLQ failure-boundary gaps.
- Requirement traceability, risk register, access register, and phase gates.
- Dependency-free contract validation and least-privilege CI workflow.
