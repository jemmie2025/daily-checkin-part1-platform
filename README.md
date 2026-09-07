# Daily Check-in Platform — Part 1

[![Contract validation](https://img.shields.io/badge/contracts-validated-1f883d)](#local-validation)
[![Phase](https://img.shields.io/badge/phases%201--4-locally%20validated-0969da)](docs/phase-plan.md)
[![Secrets](https://img.shields.io/badge/secrets-Vault%20only-8250df)](SECURITY.md)

Phase 1–4 implementation checkpoint for Task #5585: contracts, APISIX gateway,
Vault runtime security, and compliance automation for the Mattermost Daily
Check-in system. Local validation is complete; company-environment deployment
and live evidence require the access listed in
[`docs/access-required.md`](docs/access-required.md).

This repository is contract-first. Part 1 and Part 2 can be implemented and
tested independently against versioned interfaces; neither workstream needs to
edit the other workstream's implementation.

## Part 1 ownership

Part 1 owns:

- APISIX routing, allowlisting, per-user throttling, and request-size controls.
- Vault policies and runtime secret delivery.
- SLA reminders, violation detection, escalation, and weekly compliance rollups.
- Durable retry, dead-letter capture, replay, and failed-submission notification.
- ClickHouse event ingestion and Superset analytics.
- Operational telemetry, security controls, production tests, and runbooks.

Part 1 does **not** write to `checkins`, open the Mattermost dialog, validate
FMT-1–FMT-8, or create canonical channel posts. Those operations remain behind
the Part 2 boundary defined in [`contracts/ownership.yaml`](contracts/ownership.yaml).

## Non-negotiable invariants

| ID | Invariant |
|---|---|
| INV-01 | `/webhook/checkin/open` returns HTTP 200 within 2 seconds. |
| INV-02 | The Open Handler performs no application-database writes. |
| INV-03 | Only the Submit Handler writes `checkins`. |
| INV-04 | Only the Compliance Worker writes `checkin_violations`. |
| INV-05 | Only the Submit Error Workflow writes `checkin_dlq`. |
| INV-06 | Rejected submissions never reach Baserow and never post to a pod channel. |
| INV-07 | Telemetry contains no raw tasks, proof URLs, usernames, or verbatim submissions. |
| INV-08 | Every replay is idempotent and traceable to its original failed execution. |

## Architecture decisions already resolved

Nine ambiguous areas in the master plan are resolved explicitly, including:

1. Missing submissions exist only in `checkin_violations`; no synthetic
   `checkins` row is created.
2. `checkin.opened` is produced asynchronously from APISIX access telemetry,
   preserving the Open Handler's no-write and latency guarantees.
3. n8n's execution store is the durable first failure boundary; the Baserow
   `checkin_dlq` table is the operational audit and replay surface. This avoids
   losing submissions when Baserow itself is unavailable.
4. Separate Baserow identities preserve the three exclusive writer boundaries.
5. Analytics events are versioned and exclude raw work content.
6. Vault runtime resolution is distinguished from dynamically issued credentials.
7. Six distinct Nomad task identities enforce real Vault isolation; separate
   policy names inside one n8n process are explicitly insufficient.
8. DLQ replay resumes at the failed side effect and a scheduled reconciliation
   pass mirrors failures that occurred while Baserow was unavailable.
9. ClickHouse rejects conflicting event IDs, deduplicates at ingest and query
   time, expires detail after 24 months, and retains aggregate-only history.

See [`docs/adr`](docs/adr) for the full rationale and consequences.
The folder-by-folder ownership map is in
[`docs/folder-structure.md`](docs/folder-structure.md).

## Repository map

```text
.
├── config/                 Non-secret system defaults
├── apisix/                 Custom gateway plugin and installation guidance
├── baserow/                Part 1 field map and uniqueness requirements
├── checkin_platform/       Executable compliance/reliability reference models
├── contracts/              Versioned ownership, data, and event contracts
│   ├── baserow/            Logical record schemas
│   ├── compliance/         Snapshot and expectation contracts
│   ├── events/             ClickHouse event schema and examples
│   └── reliability/        Failure and replay contracts
├── n8n/                    Reviewed code, templates, and importable workflows
├── analytics/              ClickHouse DDL and Superset native export
├── observability/          Metric contract, recording rules, and alerts
├── load/                   k6 performance and gateway-control tests
├── security/               Passive ZAP scan plan
├── docs/                   Architecture, phases, ADRs, and runbooks
│   └── adr/                Architecture decision records
├── vault/                  Generated policies, roles, inventory, and task fragments
├── release/                Immutable manifest and readiness evidence index
├── scripts/                Renderers, deployers, packagers, and validation
├── tests/                  Automated contract, runtime, security, and policy tests
└── .github/workflows/      Least-privilege CI quality gate
```

## Local validation

Use Python 3.11+ and Node.js 20+ (Node runs the n8n Code-node fixtures). The
only Python development dependency is pinned YAML parsing.

```bash
python3 -m pip install -r requirements-dev.txt
make validate
```

The command validates JSON, YAML, and HCL; tests events and operational records;
checks privacy and ownership; verifies deterministic APISIX and Vault renders;
executes n8n JavaScript fixtures; verifies ClickHouse/Superset and hardening
assets; scans the tree and Git history for credentials; and verifies the release
manifest. Generated assets are reproducible from reviewed sources.

To build the deterministic one-folder WSL archive after validation:

```bash
make release
```

For a Windows-laptop handoff, follow
[`docs/wsl-vscode-setup.md`](docs/wsl-vscode-setup.md). The short access request
for Friendy is in [`docs/message-to-friendy.md`](docs/message-to-friendy.md).

## Configuration policy

Copy `.env.example` only for local development. Values committed to Git are
references and safe defaults—not credentials. Runtime secrets resolve from six
isolated KV v2 objects below `kv/n8n/mattermost/checkin` and must never be
stored in n8n workflow JSON, APISIX configuration, screenshots, logs, or CI
variables in plaintext.

## Delivery status

| Phase | State | Exit evidence |
|---|---|---|
| 1. Foundation and contracts | Locally validated | Contracts validate; ADRs and ownership boundaries recorded |
| 2. APISIX gateway | Locally validated | Policy tests pass; staging deployment and latency evidence remain |
| 3. Vault security | Locally validated | Policy/render tests pass; live isolation and rotation evidence remain |
| 4. Compliance automation | Locally validated | Deterministic timezone, suppression, idempotency, escalation, and rollup tests pass |
| 5–7. Reliability, analytics, hardening | Not accepted in this checkpoint | Prepared assets remain future work and require their own validation and approval |

“Locally validated” means reproducible tests passed without company credentials.
It does not claim deployment to APISIX, Vault, Nomad, n8n, Baserow, Mattermost,
or any production environment. Staging tests and named approvals remain open in
[`release/production-readiness-checklist.md`](release/production-readiness-checklist.md).
The detailed gates are in [`docs/phase-plan.md`](docs/phase-plan.md).
