# Vault Deployment, Verification, and Rotation Runbook

## Purpose and safety boundary

This runbook deploys only ACL policies, Nomad JWT roles, and optionally the JWT
auth configuration. It never creates or updates secret values. `VAULT_TOKEN`
is accepted only through the process environment and is never printed.

Run all live steps first in an isolated staging namespace. Do not use the
example file unchanged and do not put credentials in Git, shell arguments,
n8n exports, tickets, screenshots, or evidence files.

## 1. Required approvals and inputs

- Vault 1.18+ address, namespace, KV v2 mount, and scoped deployer identity.
- Nomad 1.10+ namespace and six dedicated job/task boundaries.
- HA Nomad JWKS URL reachable from every Vault server over verified TLS.
- CA PEM path for that JWKS endpoint.
- Owners for each external service credential and an agreed rotation window.
- Two functioning Vault audit devices with default HMAC treatment of sensitive
  string values.

Stop if Open, Submit, Compliance, DLQ, and Analytics share one n8n process or worker. Vault
cannot enforce workflow-level isolation inside a shared process.

## 2. Prepare a non-committed environment configuration

Copy `config/vault.security.example.yaml` outside the repository or to an
ignored `.env`-specific path. Set `environment`, `vault.address`, namespace,
JWKS URL, Nomad namespace, and the real job/task claims. Do not add values to
any `binding`; bindings contain coordinates only.

Confirm that the auth mount is an existing JWT mount. Enabling a new auth mount
is a one-time Vault-administrator action and is deliberately outside the deploy
script. Do not reuse a human OIDC auth mount.

## 3. Provision the eight KV objects securely

An authorized secrets operator or approved pipeline creates these objects:

| Object | Consumers | Required keys |
|---|---|---|
| `kv/n8n/mattermost/checkin/apisix` | APISIX | `redis_password`, `telemetry_auth_header` |
| `kv/n8n/mattermost/checkin/dialog-shared` | Open, Submit | `state_signing_key` |
| `kv/n8n/mattermost/checkin/event-shared` | Submit, Analytics | `event_ingest_token` |
| `kv/n8n/mattermost/checkin/open` | Open | `mattermost_command_token`, `mattermost_bot_token`, `compliance_sla_read_token` |
| `kv/n8n/mattermost/checkin/submit` | Submit | `mattermost_submit_signature`, `mattermost_bot_token`, `baserow_checkins_token` |
| `kv/n8n/mattermost/checkin/compliance` | Compliance | `mattermost_bot_token`, `baserow_violations_token`, `roster_read_token`, `calendar_read_token` |
| `kv/n8n/mattermost/checkin/dlq` | DLQ | `mattermost_bot_token`, `baserow_dlq_token`, `replay_token`, `n8n_execution_read_token` |
| `kv/n8n/mattermost/checkin/analytics` | Analytics | `clickhouse_ingest_user`, `clickhouse_ingest_key`, `roster_read_token` |

Use independent Mattermost bot accounts and separate Baserow tokens so a Vault
path split corresponds to real downstream authorization. Do not duplicate one
broad token under several names.

Provide values through the approved secret-injection channel. Avoid CLI
`key=value` arguments because they can enter shell history and process listings.

## 4. Render and review

```bash
make vault
python3 scripts/deploy_vault.py \
  --config /secure/path/vault.security.staging.yaml
```

The second command must print twelve planned writes and `DRY-RUN`. Review:

- every policy contains only exact `kv/data/...` paths and `read`;
- every role binds namespace, job ID, task, and audience `vault.io`;
- no role includes the Vault default policy;
- the auth config has no `default_role`;
- no secret value appears in the plan.

## 5. Apply to staging

Use a short-lived, audited deployer token. `VAULT_CACERT` must name the Vault
server CA when it is not in the system trust store. The Nomad JWKS CA is a
separate public certificate file.

```bash
export VAULT_TOKEN="$(approved-credential-helper)"
export VAULT_CACERT=/secure/path/vault-ca.pem
export VAULT_NOMAD_JWKS_CA_PEM_FILE=/secure/path/nomad-ca.pem

python3 scripts/deploy_vault.py \
  --config /secure/path/vault.security.staging.yaml \
  --include-auth-config \
  --apply \
  --confirm-environment staging

unset VAULT_TOKEN
```

`--include-auth-config` updates a shared trust endpoint and therefore requires
explicit use. Omit it when the platform team already manages the JWT auth
configuration. Before any write, the script verifies the active Vault node,
two configured audit devices, KV v2 mount, and JWT auth mount, then saves
current roles, policies, and the auth configuration when changed under
`build/vault-backups/<UTC timestamp>/` with restrictive permissions.

If an apply stops, do not blindly rerun it. Compare the snapshot, current state,
and deterministic desired files, then complete or restore the exact resources.

## 6. Attach the Nomad task fragments

Merge each file in `vault/nomad/` only into the named dedicated task. Do not put
the `vault`, `identity`, or `template` block at group or job scope.

The fragments:

- use `vault_default` identity with one `vault.io` audience and one-hour TTL;
- keep `VAULT_TOKEN` out of the workload environment and filesystem;
- render credentials into the task secrets directory with mode `0400`;
- fail when a declared key is missing;
- restart with a 30-second splay when values change.

For n8n, route each workflow class exclusively to its declared worker task.
Inspect the final Nomad plan before registration and confirm there is no
environment override that contains a literal credential.

## 7. Run the staging isolation test

Create disposable one-hour workload JWT files from isolated staging allocations
for the six exact claims and store them as `<workload>.jwt` in a temporary
directory with mode `0600`. Centralizing them is permitted only in this isolated
test runner; destroy the directory immediately afterward.

```bash
python3 scripts/smoke_vault.py \
  --config /secure/path/vault.security.staging.yaml \
  --jwt-dir /secure/tmp/checkin-jwts \
  --evidence-output evidence/private/vault-access-before.json \
  --confirm-staging
```

The script validates six own-role logins, thirty foreign-role denials, every
approved path, every foreign path, exact key sets, token renewability, and KV v2
versions. Evidence contains coordinates, versions, statuses, and counts only.
It is written mode `0600`; keep live evidence in the ignored private directory.

## 8. Prove rotation without a workflow edit

1. Save hashes of the reviewed n8n exports and current sanitized access evidence.
2. Issue a replacement credential in the downstream service with equal or
   narrower rights.
3. Update only the corresponding Vault KV object through the approved channel.
4. Observe the Nomad template change and controlled task restart.
5. Confirm a health check and one safe operation using the replacement.
6. Revoke the previous credential at the downstream service.
7. Confirm the previous credential is rejected without recording its value.
8. Re-export n8n and prove the hashes are unchanged.
9. Rerun the smoke test with the baseline and expected object, for example:

```bash
python3 scripts/smoke_vault.py \
  --config /secure/path/vault.security.staging.yaml \
  --jwt-dir /secure/tmp/checkin-jwts-after \
  --baseline-evidence evidence/private/vault-access-before.json \
  --expect-rotated-path submit \
  --evidence-output evidence/private/vault-access-after.json \
  --confirm-staging
```

The after-run must show a higher KV version for every declared rotated object.
A KV version increase alone is not sufficient: downstream revocation and an
unchanged workflow export are separate required evidence.

## 9. Emergency revocation

1. Disable or revoke the exposed downstream credential first.
2. Stop the affected Nomad task if active misuse is possible.
3. Replace the Vault value and allow only the affected task to restart.
4. Search audit records by role, entity, path, and time range without exporting
   request or response bodies.
5. Re-run path-isolation and service health checks.
6. Record the incident timeline and delete disposable JWT material.

Never delete KV version history during response unless the security owner has
approved irreversible destruction and retention requirements are satisfied.
