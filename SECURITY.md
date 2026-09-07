# Security Policy

## Secrets

- Runtime secrets resolve from eight KV v2 objects below
  `kv/n8n/mattermost/checkin`; the prefix itself is never one broad object.
- Secret values must not be committed, exported inside n8n workflow JSON,
  included in screenshots, or written to application logs.
- `.env.example` contains names and references only.
- Tokens must be least-privilege, independently rotatable, and auditable.
- The DLQ recovery credential is limited to `execution:read`, restricted to the
  internal n8n API network path, and cannot edit or run workflows.
- Six Nomad tasks use six JWT roles bound to exact namespace, job, task, and
  `vault.io` audience claims.
- Workload policies are exact-path `read` only. Secret writers use a separate,
  human-approved operator identity.
- Nomad renders scoped credentials but does not expose its Vault token to the
  application task.

## Data classification

| Data | Classification | Permitted destination |
|---|---|---|
| Mattermost `user_id`, pod, cycle date | Internal | Baserow and pseudonymous telemetry |
| `user_name` | Internal personal data | Baserow operational tables only |
| Raw tasks and proof URLs | Confidential | `checkins`; DLQ only during unresolved failure |
| Verbatim failed submission | Restricted | `checkin_dlq`; never logs or ClickHouse |
| Tokens, signatures, Vault credentials | Secret | Vault only |

## Required controls

- APISIX extracts `user_id` only after the request passes the Mattermost egress
  allowlist and strict payload checks; this identity is used for abuse
  throttling, not authorization.
- n8n must verify the Mattermost token/signature before any business processing
  and confirm that the forwarded gateway identity matches the payload identity.
- Accept requests only from the confirmed Mattermost egress CIDR.
- Enforce a 64 KiB request-body ceiling and 10 requests per 60 seconds per
  verified user on both webhook routes.
- Redact authorization headers, tokens, dialog state, task text, proof links,
  and verbatim submissions from gateway, n8n, and ClickHouse logs.
- Reject `javascript:` and `data:` proof-link schemes and deny loopback,
  link-local, private, and cloud metadata destinations before rendering or
  retrieving a URL.
- Use TLS for every network hop. Production certificate verification cannot be
  disabled.
- Store a hash of the single-use nonce; never log the nonce itself.
- Keep Vault's default HMAC protection for sensitive string values and operate
  at least two healthy audit devices.
- Rotate static service credentials within 90 days and immediately after a
  suspected exposure; revoke the previous value at its source after cutover.

## Runtime isolation

Open, Submit, Compliance, DLQ, and Analytics must not execute in one n8n process. Vault
cannot restrict environment variables by workflow inside a shared process.
Each class runs on the dedicated task and policy declared in
`config/vault.security.example.yaml`. `dialog-shared` contains only the
dialog-state signing key for Open and Submit; `event-shared` contains only the
ingestion token for Submit and Analytics. No Baserow or ClickHouse credential
is shared across tasks.

## Incident response

If a secret or raw submission is exposed:

1. Disable the affected credential or workflow path.
2. Rotate the credential in Vault.
3. Search logs and exports for further exposure without copying the secret.
4. Remove exposed artifacts through the approved retention process.
5. Record impact, timeline, remediation, and prevention in an incident report.

Report security issues privately to the platform owner; do not open a public
issue containing credentials or personal data.
