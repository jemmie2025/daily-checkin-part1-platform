# Production Input Register

Development begins with mocks and placeholders. These inputs are required only
before environment integration or production release.

The complete permission-by-permission request list is maintained in
[`access-required.md`](access-required.md).

| Input | Purpose | Required by | Safe evidence |
|---|---|---|---|
| APISIX admin endpoint and scoped credential | Install routes and plugins | Phase 2 deploy | Redacted route listing |
| Mattermost egress CIDR | Source allowlist | Phase 2 deploy | Approved CIDR reference |
| n8n upstream service address | Gateway routing | Phase 2 deploy | Health-check result |
| Vault address, namespace, auth role | Runtime secrets | Phase 3 deploy | Policy names; no tokens |
| Baserow table and field IDs | Violations and DLQ | Phases 4–5 | Redacted schema export |
| Baserow unique constraints on `violation_id` and `dlq_id` | Cross-worker idempotency | Phases 4–5 | Redacted constraint listing |
| Private Baserow replay view ID | Exclude resolved/abandoned rows from the bounded DLQ scan | Phase 5 | View name and sanitized filter listing |
| Active roster, pods, user timezone | Expected submissions | Phase 4 | Sanitized fixture counts |
| Approved Compliance Source API | Roster, SLA, leave, holiday, and accepted-checkin snapshots | Phase 4 | Contract version and freshness timestamp |
| Leave and holiday source | False-positive prevention | Phase 4 | Calendar version |
| Mattermost bot and lead-channel IDs | DMs and escalation | Phase 4 | Test-channel evidence |
| ClickHouse endpoint/database/user | Event ingestion | Phase 6 | Redacted connection test |
| ClickHouse refreshable-materialized-view support | Aggregate retention | Phase 6 | Version and `system.view_refreshes` status |
| Superset workspace access | Dashboard import | Phase 6 | Dashboard screenshot |
| Nomad namespace, job IDs, and task names | JWT claim binding | Phase 3 | Redacted job plan |
| Nomad JWKS URL and CA PEM | Vault JWT verification | Phase 3 | Sanitized auth config |
| Scoped Vault policy/role deployer | Apply security resources | Phase 3 | Audit request IDs |
| Six workload JWTs in isolated staging | Negative access testing | Phase 3 | Sanitized denial counts |
| Read-only n8n execution API credential | DLQ reconciliation | Phase 5 | Scope listing; no token value |
| External credential-owner approval | Safe rotation and revocation | Phase 3 | Rotation change record |

Credentials themselves must be delivered through Vault or the approved secure
channel, never through Git, Redmine comments, chat screenshots, or this file.
Disposable staging JWTs are credentials: use files mode `0600`, never attach
them as evidence, and destroy them immediately after the isolation test.
