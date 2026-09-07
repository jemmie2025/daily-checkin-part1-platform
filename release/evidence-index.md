# Evidence Index

| Gate | Local evidence | Private environment evidence |
|---|---|---|
| Foundation | `evidence/phase-1-validation.md` | Contract review approval |
| APISIX | `evidence/phase-2-validation.md` | `evidence/private/apisix-*` |
| Vault | `evidence/phase-3-validation.md` | `evidence/private/vault-*` |
| Compliance | `evidence/phase-4-validation.md` | `evidence/private/compliance-*` |
| DLQ | Prepared future work; not accepted in v0.4.0 | Required in a later checkpoint |
| Analytics | Prepared future work; not accepted in v0.4.0 | Required in a later checkpoint |
| Hardening | Prepared future work; not accepted in v0.4.0 | Required in a later checkpoint |

`evidence/private/` is ignored. Private evidence may contain sanitized IDs,
counts, timings, versions, hashes, and status codes only. Never attach tokens,
JWTs, secret values, raw task text, proof URLs, usernames, or DLQ submissions.
