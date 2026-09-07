# Primary Technical References

The implementation target and plugin fields were checked against the Apache
APISIX 3.18 documentation on 2026-09-04:

- [APISIX `limit-count`](https://apisix.apache.org/docs/apisix/plugins/limit-count/)
- [APISIX `ip-restriction`](https://apisix.apache.org/docs/apisix/plugins/ip-restriction/)
- [APISIX `client-control`](https://apisix.apache.org/docs/apisix/plugins/client-control/)
- [APISIX `http-logger`](https://apisix.apache.org/docs/apisix/plugins/http-logger/)
- [APISIX `request-id`](https://apisix.apache.org/docs/apisix/plugins/request-id/)
- [APISIX custom plugin development](https://apisix.apache.org/docs/apisix/plugin-develop/)
- [APISIX Secret references](https://apisix.apache.org/docs/apisix/terminology/secret/)
- [APISIX upstream-certificate limitation](https://apisix.apache.org/docs/apisix/FAQ/)

Before production, compare these contracts with the exact version installed in
the company environment. The runtime schema—not this reference date—is the final
compatibility authority.

The Vault/Nomad implementation was checked against the official HashiCorp
documentation on 2026-09-04:

- [Nomad Vault integration](https://developer.hashicorp.com/nomad/docs/secure/vault)
- [Nomad Vault ACL and workload identities](https://developer.hashicorp.com/nomad/docs/secure/vault/acl)
- [Nomad workload identity claims](https://developer.hashicorp.com/nomad/docs/concepts/workload-identity)
- [Nomad `identity` job block](https://developer.hashicorp.com/nomad/docs/job-specification/identity)
- [Nomad `vault` job block](https://developer.hashicorp.com/nomad/docs/job-specification/vault)
- [Nomad `template` job block and KV v2 syntax](https://developer.hashicorp.com/nomad/docs/job-specification/template)
- [Vault JWT authentication](https://developer.hashicorp.com/vault/docs/auth/jwt)
- [Vault KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2)
- [Vault policies](https://developer.hashicorp.com/vault/docs/concepts/policies)
- [Vault audit logging](https://developer.hashicorp.com/vault/docs/audit)

The workflow recovery design was checked against the official n8n
documentation on 2026-09-04:

- [n8n error workflows and Error Trigger payload](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully/)
- [n8n execution API](https://docs.n8n.io/api/api-reference/#tag/Execution)

The analytics security and archival design was checked against the official
ClickHouse documentation on 2026-09-04:

- [ClickHouse `CREATE VIEW`, definers, and SQL security](https://clickhouse.com/docs/en/sql-reference/statements/create/view)
- [Refreshable materialized views](https://clickhouse.com/docs/en/materialized-view/refreshable-materialized-view)

The n8n execution API capability and ClickHouse refreshable-view syntax must be
confirmed against the exact company versions during staging. Those checks are
release gates, not local assumptions.
