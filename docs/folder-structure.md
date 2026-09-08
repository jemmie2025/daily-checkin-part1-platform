# Repository Structure and Ownership

The archive extracts into one root folder: `daily-checkin-part1-platform`.

| Path | Purpose | Checkpoint status |
|---|---|---|
| `.github/workflows/` | Pull-request validation gate | Phase 1 |
| `config/` | Non-secret, reviewable environment templates | Phases 1–4 |
| `contracts/` | Ownership, Baserow, compliance, event, and reliability interfaces | Phase 1; later contracts are prepared only |
| `docs/adr/` | Architecture decisions and hard boundaries | Phase 1 |
| `apisix/` | Gateway plugin, rendered-policy inputs, and deployment guidance | Phase 2 |
| `vault/` | Generated policies, roles, auth configuration, and Nomad task templates | Phase 3 |
| `n8n/code/` | Reviewable JavaScript used by workflow Code nodes | Phase 4 and prepared later work |
| `n8n/templates/` | Source workflow templates | Phase 4 and prepared later work |
| `n8n/workflows/` | Deterministically generated, inactive imports | Phase 4 and prepared later work |
| `checkin_platform/` | Executable reference models for compliance and reliability | Phase 4 and prepared later work |
| `baserow/` | Logical field maps and uniqueness requirements | Phase 4 and prepared later work |
| `tests/` | Contract, policy, runtime, privacy, and idempotency tests | Validation support |
| `evidence/` | Sanitized local validation records | Phases 1–4 claimed |
| `scripts/` | Render, validate, deploy-dry-run, package, and WSL bootstrap tools | Validation support |
| `release/` | Manifest, evidence index, metadata, and readiness checklist | Checkpoint control |
| `analytics/` | ClickHouse and existing-Grafana configuration | Prepared Phase 6 assets |
| `observability/`, `load/` | Existing-platform monitoring and load-test configuration | Prepared Phase 7 assets |
| `security/` | Gitleaks, Strix, and passive ZAP security gates | Phase 1 and prepared Phase 7 assets |

Generated output belongs under `build/` and is excluded from Git and the release
manifest. Real environment evidence belongs under `evidence/private/`, which is
also excluded. Secrets belong only in Vault; `.env.example` contains names and
safe placeholders, never values.
