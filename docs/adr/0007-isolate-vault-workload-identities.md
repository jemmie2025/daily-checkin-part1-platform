# ADR-0007: Isolate Vault Access at the Nomad Task Boundary

- Status: Accepted
- Date: 2026-09-04

## Context

Vault policies apply to workload tokens, not to individual n8n workflows. If
Open, Submit, Compliance, and DLQ workflows execute inside one n8n process,
every workflow can access every credential injected into that process. Naming
four policies without separating the runtime would provide cosmetic rather
than real least privilege.

The required `kv/n8n/mattermost/checkin` location also cannot be one KV object.
Vault authorizes paths, not individual keys inside a KV object. A reader of one
key can read every key returned from that object.

## Decision

Use six dedicated Nomad task boundaries and six claim-bound Vault roles:

1. `apisix`
2. `n8n-open`
3. `n8n-submit`
4. `n8n-compliance`
5. `n8n-dlq`
6. `n8n-analytics`

Bind every JWT role to the exact Nomad namespace, job ID, task name, and Vault
role claim. Split
the logical Vault prefix into eight KV v2 objects: `apisix`, `open`, `submit`,
`compliance`, `dlq`, `analytics`, `dialog-shared`, and `event-shared`. Only
Open and Submit may read `dialog-shared`, which contains only the dialog-state
signing key. Only Submit and Analytics may read `event-shared`, which contains
only the event-ingestion token.

Policies use exact `kv/data/...` paths with `read` only. They have no wildcard,
list, metadata, create, update, delete, or sudo capability. Secret rotation is
performed by an operator or approved pipeline, never by a workload.

## Consequences

- A monolithic n8n deployment is not acceptable evidence of least privilege.
- Queue routing or separate n8n deployments must keep each workflow class on
  its declared task and credential set.
- Compromise of one task does not grant another task's Baserow identity.
- The one intentionally shared signing key is visible in the access inventory.
- Runtime topology is a Phase 3 production preflight, not an implementation
  detail that can be deferred.
