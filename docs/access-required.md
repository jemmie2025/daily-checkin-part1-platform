# Company Access Required for Task #5585 Part 1

These permissions, identifiers, and approvals must come from company owners.
They cannot be created or supplied by local development. Request staging access
first and production access only through the normal change process.

## Required now — Phases 1–4

| System | Minimum access or input | Used for |
|---|---|---|
| Official Git repository | Repository URL; create/push branch; open PR; read CI; protected-branch workflow | Publish reviewed code and retain an auditable change history |
| Redmine Task #5585 | Read; comment; attach sanitized evidence; update assigned fields/status | Record progress, decisions, blockers, and acceptance evidence |
| Master plan / SOP | Read access to the approved specification, PI-6 taxonomy, SLA definitions, and change owner | Confirm requirements and prevent contract drift |
| APISIX staging | Admin API endpoint; scoped route/upstream/plugin read-write; Control API read; logs/metrics read | Deploy and verify the Open/Submit routes, limits, rollback, and latency |
| APISIX plugin operations | Approval to install/reload the reviewed custom plugin in staging and run a canary | Enforce safe user-key extraction and sanitized telemetry |
| Mattermost network identity | Approved Nomad allocation egress CIDR(s), including NAT behavior | Build the exact APISIX IP allowlist |
| Redis rate-limit service | TLS endpoint, CA chain, database number, and a scoped credential delivered through Vault | Enforce a distributed 10 requests/minute per-user limit |
| Internal DNS/TLS/network | DNS names, trusted CA bundle, and allowed service paths between Mattermost, APISIX, n8n, the Compliance Source API, Baserow, and telemetry | Make live calls secure and reachable |
| Vault staging | Address, namespace, JWT auth mount, KV v2 mount, health/audit read, and permission or an operator to apply reviewed policies/roles | Deliver runtime secrets and prove least-privilege isolation |
| Nomad staging | Namespace; job/task names; plan/run/read-logs permission; workload identity/JWKS details and CA | Bind six isolated identities and verify secret rotation/restart behavior |
| Secret owners | Secure provisioning/rotation of required Mattermost, Baserow, Redis, telemetry, and source credentials | Populate `kv/n8n/mattermost/checkin/*` without exposing values in chat or Git |
| n8n staging | Import, edit, execute, activate/deactivate, schedule, and execution-log read for the Part 1 workflows; environment-reference configuration | Run and diagnose the compliance automation |
| Approved Compliance Source API | Read-only endpoint/token plus schema/version/freshness ownership for roster, pod, IANA timezone, SLA, leave, holidays, accepted-checkin snapshots, and weekly expectations | Calculate who is expected, when they are due, and who must be suppressed |
| Baserow staging | Workspace/database access; create/read/update on `checkin_violations`; table/field IDs; API token limited to that table; unique `violation_id` constraint | Persist PI-6 breaches idempotently without access to write `checkins` |
| Mattermost staging | Test workspace/channel membership; dedicated compliance bot token; permission to DM users and post to approved pod-lead channels; test user/channel IDs | Verify nudges, escalations, and weekly rollups |
| Observability | Read access to APISIX, n8n, Nomad, Vault-audit-health, Mattermost API, and Baserow integration logs/metrics | Produce sanitized evidence and diagnose failures |
| Staging test approval | Permission to run allowlist, 413, 429, timeout, rotation, denial, and scheduler-idempotency tests | Complete the Phase 2–4 environment acceptance gates |

## Required later — Phases 5–7

| System | Minimum access or input | Used for |
|---|---|---|
| Baserow DLQ | Create/read/update on `checkin_dlq`; scoped token; table/field IDs; unique `dlq_id`; private pending/replaying view ID | Capture, lease, replay, and retain failed submissions |
| n8n execution API | Read-only credential scoped to failed Submit executions and permission to configure the error workflow | Reconcile durable executions into the DLQ without broad n8n administration |
| ClickHouse staging | HTTPS endpoint, database, CA, migration/DDL role, scoped insert identity, reporting-view role, and system-table read needed for health checks | Install event tables/views, validate deduplication, retention, and access denial |
| ClickHouse topology owner | Version, Keeper/replica details, backup target, and approval for refreshable aggregate views | Prove resilience and aggregate-only archival |
| Superset staging | Dataset/dashboard import, edit, validate, and share permission; read-only ClickHouse reporting-role connection | Import and reconcile the compliance dashboard |
| Prometheus/Alertmanager | Read plus reviewed rule deployment or an owner who can apply the supplied rules | Activate SLO recording and alert rules |
| Security/load-test environment | Approved k6 and passive ZAP targets, source allowlist, test accounts, monitoring, and test window | Execute performance and security gates safely |
| Backup/restore sandbox | Snapshot location, restore permission, and operator support | Run recovery and integrity drills |
| Production change process | Named service owners, security review, change/canary approval, rollback authority, and final sign-offs | Promote a proven staging release without bypassing governance |

## Least-privilege rules

- Do not request production administrator access where a staging-scoped role or
  platform operator can apply reviewed resources.
- Do not send tokens, JWTs, passwords, CA private keys, raw check-ins, proof
  links, or DLQ payloads through chat, email, Redmine, screenshots, or Git.
- Evidence should contain only sanitized IDs, counts, timings, hashes, versions,
  status codes, and explicit PASS/FAIL outcomes.
- Part 1 must never receive permission to write `checkins`; the compliance
  identity writes only `checkin_violations`.
