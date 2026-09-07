# APISIX Gateway Deployment Runbook

## Compatibility target

The rendered resources target Apache APISIX 3.18.x. Do not deploy them to an
unknown version. First confirm that the installed schemas support every field
and that the custom priority does not collide with another plugin.

## 1. Prepare staging inputs

Copy the example configuration and replace only non-secret environment values:

```bash
cp config/apisix.gateway.example.yaml config/apisix.gateway.staging.yaml
```

Set `environment: staging`, the real Mattermost/Nomad egress CIDR, n8n and
telemetry HTTPS endpoints, Redis endpoint, and approved resource IDs. Keep all
credential fields as the exact `$ENV://CHECKIN_REDIS_PASSWORD` and
`$ENV://CHECKIN_TELEMETRY_AUTH_HEADER` references. The values are rendered from
Vault KV v2 by `vault/nomad/apisix.nomad.hcl`; they are not deployment-shell
variables and must not be copied into the APISIX resource JSON.

## 2. Install the custom plugin

Place `apisix/custom/apisix/plugins/checkin-context.lua` below the configured
`extra_lua_path`. Append `checkin-context` to the deployment's complete plugin
list. Never replace the existing list with the one-line example.

Use the APISIX Control API `/v1/schema` to verify this execution order:

```text
ip-restriction (3000) > checkin-context (2999) > limit-count
```

Roll the plugin through a canary gateway and confirm APISIX starts without a
schema or Lua load error.

## 3. Confirm required plugins

The deployment tool fails closed unless these plugins are available:

- `ip-restriction`
- `client-control`
- `request-id`
- `checkin-context`
- `limit-count`
- `response-rewrite`
- `http-logger`

`client-control` requires APISIX-Runtime. If it is unavailable, stop and have
the gateway owner approve an equivalent 64 KiB NGINX/APISIX control before
deployment; do not silently omit the cap.

APISIX 3.18 documents that it does not validate an HTTPS upstream's server
certificate. Confirm that the APISIX-to-n8n hop remains inside the restricted
Nomad trust boundary. If the approved threat model requires server
authentication, route that hop through the organization's verified-TLS or
service-mesh proxy; HTTPS scheme alone is not sufficient evidence.

## 4. Render and inspect

```bash
python3 scripts/render_apisix.py \
  --config config/apisix.gateway.staging.yaml \
  --output build/apisix-resources.staging.json

python3 scripts/deploy_apisix.py \
  --bundle build/apisix-resources.staging.json
```

The second command is a dry run and performs no external writes.

## 5. Apply to staging

Resolve `APISIX_ADMIN_TOKEN` at runtime through the approved Vault delivery
method, then run:

```bash
python3 scripts/deploy_apisix.py \
  --bundle build/apisix-resources.staging.json \
  --apply \
  --confirm-environment staging
```

The tool verifies plugins, snapshots existing resources, and applies the
upstream before the two routes. It stops on the first failure and never deletes
a resource automatically.

## 6. Run the staging checks

Point staging routes to a mock or authentication-rejection n8n upstream. The
smoke test consumes one full user rate-limit window and must never target a live
Mattermost dialog workflow.

```bash
python3 scripts/smoke_gateway.py \
  --base-url https://staging-checkin.example.internal \
  --confirm-staging
```

Capture only statuses, timing, route IDs, and redacted configuration. Never
capture tokens, body text, dialog state, or proof URLs.

## 7. Roll back safely

If staging verification fails, stop traffic to the new route revision and PUT
the snapshots from `build/apisix-backups/<UTC timestamp>/` back through the
Admin API. A resource that did not exist before deployment must be removed only
after its exact ID and snapshot manifest are reviewed by the gateway owner.

## 8. Production release

Repeat render, dry run, snapshot, canary apply, and smoke verification using a
production configuration. Production rendering rejects documentation CIDRs and
all non-HTTPS endpoints. Record change ticket, approver, APISIX version, route
revision, test results, rollback snapshot, and timestamps in the evidence index.
