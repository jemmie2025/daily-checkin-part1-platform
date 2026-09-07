# ADR-0005: Treat Vault KV as Runtime-Resolved, Rotatable Secrets

- Status: Accepted
- Date: 2026-09-04

## Context

The master plan calls `kv/n8n/mattermost/checkin` a dynamic secret source.
Vault KV stores versioned values; it does not dynamically issue Mattermost or
Baserow credentials because those systems control credential issuance.

## Decision

Store independently rotatable service credentials below the required logical
Vault prefix and resolve them at workload runtime using Nomad workload identity
and template rendering. Never copy values into n8n static workflow data. Use a
true dynamic secrets engine only for a service that supports dynamic credential
issuance.

The implementation target is KV v2. Nomad reads `kv/data/...` and renders
declared values into each task's secret environment file. APISIX consumes those
values through `$ENV://...` references. This avoids relying on APISIX 3.18's
direct HashiCorp Vault integration, which supports KV v1 rather than the chosen
KV v2 mount.

## Consequences

- Documentation distinguishes dynamic retrieval from dynamic credentials.
- Rotation changes Vault values without changing exported workflows.
- Credential lifetime and revocation still depend on the target service.
- Vault KV v2 and Nomad workload identity compatibility are deployment
  preflights.
- Secret objects and task identities are split as defined in ADR-0007.
