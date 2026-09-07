# Phase 3 Acceptance Matrix

## Local implementation evidence

| Control | Automated proof | State |
|---|---|---|
| Canonical Vault mount is KV v2 | Configuration fail-closed test | Pass |
| One logical prefix is split into six objects | Inventory and reader-boundary test | Pass |
| Six workloads have six policies and roles | Artifact-count and uniqueness tests | Pass |
| Policies are exact-path and read-only | Capability/wildcard tests | Pass |
| Roles bind namespace, job, task, Vault role, and one audience | JWT-role tests | Pass |
| Tokens are renewable, 30-minute service tokens | Role TTL tests | Pass |
| Vault default policy is excluded | Role policy test | Pass |
| Vault token is not exposed to the task | Nomad template tests | Pass |
| Missing keys fail allocation startup | `error_on_missing_key` test | Pass |
| Secret changes restart tasks with splay | Template rotation test | Pass |
| APISIX consumes KV-v2-rendered variables | Cross-configuration test | Pass |
| Deployment defaults to no-write dry run | Deployment behavior test | Pass |
| Apply preflight rejects fewer than two audit devices | Mocked API test | Pass |
| Unreviewed JWKS configuration drift fails closed | Mocked API test | Pass |
| Tree/history leak scan is in the CI gate | Secret scanner tests | Pass |
| Canonical generated files are reproducible | Directory comparison test | Pass |

## Environment evidence still required

Local tests prove the configuration's intent, not that company infrastructure
enforces it. Phase 3 becomes environment-verified only after all checks below
have sanitized evidence attached.

| Check | Required proof |
|---|---|
| Installed versions | Vault 1.18+ and Nomad 1.10+ version output |
| KV engine | `kv/` tune output showing version 2, with values omitted |
| JWT auth trust | Reachable HA JWKS URL over verified TLS and approved CA |
| Audit durability | At least two healthy audit devices; HMAC defaults retained |
| Dedicated execution | Six distinct Nomad task identities; no mixed n8n worker |
| Correct-role login | Each workload identity authenticates to its own role |
| Foreign-role denial | All 30 cross-role exchanges return HTTP 400/403 |
| Path isolation | Approved reads succeed; all foreign reads return HTTP 403 |
| Secret completeness | Each object has exactly its declared keys, no extras |
| Rotation | Target KV version advances and its task restarts within the window |
| External revocation | Previous upstream credential is rejected after cutover |
| Workflow immutability | Before/after n8n export hashes are identical |
| Recovery | Saved policy/role snapshot can restore staging configuration |

Never attach JWTs, Vault tokens, secret values, rendered environment files, or
raw audit records as evidence.
