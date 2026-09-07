# Phase 3 Validation Evidence

- Task: #5585 — Daily Check-in System
- Workstream: Part 1 Platform
- Version: 0.4.0
- Validation date: 2026-09-07 UTC
- Result: LOCAL IMPLEMENTATION PASS

## Commands

```bash
make validate
python3 scripts/deploy_vault.py \
  --config config/vault.security.example.yaml
```

## Verified locally

- All repository JSON and YAML artifacts parsed successfully.
- All text artifacts, including HCL, passed hygiene validation.
- Twenty canonical Vault/Nomad artifacts reproduced byte-for-byte.
- Six dedicated workloads have six unique policies and JWT roles.
- Eight KV v2 objects preserve the required logical Vault prefix.
- Policies contain exact `kv/data/...` reads only: no wildcard, metadata, list,
  create, update, delete, or sudo capability.
- Roles bind one `vault.io` audience plus exact namespace, job ID, task, and
  Vault role claim.
- Roles issue renewable 30-minute service tokens with no default policy.
- Nomad templates keep the Vault token out of the application, use mode `0400`,
  fail on missing keys, and restart with splay after a secret change.
- APISIX Redis and telemetry credentials use only the two Vault-rendered runtime
  environment references declared for its task.
- Vault deployment rendered twelve planned policy/role writes and defaulted to a
  no-write dry run.
- Simulated live preflights reject a single audit device and unreviewed JWKS
  configuration drift.
- The working-tree credential scanner found no recognized secret material.
- The complete 167-test repository suite passed with zero failures; only
  Phase 1–4 is claimed by this checkpoint.

## Deliberately not claimed

No company Vault, Nomad, n8n, or downstream service access was available during
local validation. Live JWT exchange, thirty cross-role denials, path-level HTTP
403 results, audit-device health, task restart, KV version advancement, old
credential revocation, unchanged n8n export hashes, and snapshot restoration
remain environment-verification items in `docs/phase-3-acceptance.md`.

The Git-history scan was skipped because this delivered folder is not a Git
working tree. The scanner is part of `make validate` and will inspect history
automatically after the repository is initialized or imported.

This evidence contains no credentials, workload JWTs, production endpoints,
rendered environment files, raw audit records, or personal production data.
