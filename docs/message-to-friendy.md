# Access Request to Friendy

Hi Friendy,

For my Task #5585 Part 1 scope, please grant or confirm the following staging
access: the official Git repository and Redmine update permissions; APISIX
route/plugin deployment plus logs and the approved Mattermost Nomad egress
CIDR; Vault/Nomad policy, role, workload-identity, audit, plan, and log access;
n8n workflow import/execute/activate and execution-log access; a read-only
approved Compliance Source API for roster, pod, timezone, SLA, leave, holiday,
and accepted-checkin snapshots; Baserow access limited to the
`checkin_violations` schema/table; and a Mattermost compliance bot with test DM
and pod-lead channel permissions. I also need the internal DNS/TLS/network paths,
Redis rate-limit connection through Vault, and permission to run the documented
staging acceptance tests.

For the later reliability, analytics, and hardening phases, I will need scoped
Baserow DLQ, read-only n8n failed-execution, ClickHouse migration/ingest/reporting,
Superset import, monitoring-rule, security/load-test, backup/restore, and change
approval access.

Please provide credentials only through the approved secure channel; no secret
values are needed in chat or Redmine. The exact least-privilege breakdown is in
`docs/access-required.md`.

Thank you.
