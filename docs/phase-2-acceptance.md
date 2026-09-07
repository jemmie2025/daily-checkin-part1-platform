# Phase 2 Acceptance Matrix

## Local evidence

| Control | Automated proof | State |
|---|---|---|
| Separate Open and Submit routes | Route contract test | Pass |
| POST only | Method contract test | Pass |
| 64 KiB maximum body | Renderer and plugin contract tests | Pass |
| Mattermost source CIDR required | CIDR and production-placeholder tests | Pass |
| 10 requests/60 seconds/user | Shared Redis policy test | Pass |
| Multi-node counter consistency | Redis policy with TLS verification | Pass |
| Fail closed when rate store fails | `allow_degradation=false` test | Pass |
| Open upstream timeout below 2 seconds | Timeout contract test | Pass |
| No request/response body logging | Logger privacy test | Pass |
| Vault-only plugin credentials | Vault-rendered runtime-reference test | Pass |
| Reproducible configuration | Deterministic render test | Pass |
| Dry-run-first deployment | Deployment tool default behavior | Pass |

## Environment evidence still required

These checks require the company staging environment and cannot be represented
as passed by local configuration tests:

| Check | Required proof |
|---|---|
| Actual Nomad/Mattermost egress CIDR | Approved network value and denied-source test |
| Installed APISIX version/plugin schemas | Redacted preflight output |
| APISIX-to-n8n trust boundary | Approved private-network or verified-proxy evidence |
| Custom Lua plugin runtime | Clean canary startup and request tests |
| Actual eleventh request | HTTP 429 response in isolated staging |
| Actual oversized request | HTTP 413 response in isolated staging |
| Open-path latency | Minimum 30 real `/ci` samples; p95 below 2 seconds |
| Asynchronous telemetry | Sanitized log received with no request/response body |
| Rollback | Snapshot restored in staging |

Phase 2 is implementation-complete after local validation. It becomes
environment-verified only when every second-table item has attached evidence.
