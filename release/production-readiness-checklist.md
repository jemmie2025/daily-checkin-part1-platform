# Production Readiness Checklist

## Phase 1–4 locally validated

- [x] Ownership boundaries and versioned contracts are validated.
- [x] APISIX routes fail closed on method, source, size, quota, and TLS.
- [x] Six workloads have isolated Vault identities and exact read policies.
- [x] Compliance and weekly-rollup workflows are deterministic and imported
  inactive.
- [x] No recognized credential or confidential work payload is committed.

## Prepared but not accepted in this checkpoint

- [ ] Phase 5 DLQ and reliability gate.
- [ ] Phase 6 ClickHouse and Superset gate.
- [ ] Phase 7 production-hardening gate.

## Must be completed in company staging

- [ ] APISIX source CIDR, TLS, 64 KiB, 10/minute, and p95 latency evidence.
- [ ] Six-by-six Vault login/path isolation matrix and credential rotation.
- [ ] Compliance Source API freshness, suppression, Baserow violation, and
  Mattermost nudge/digest smoke tests.
- [ ] Two-week duplicate-free compliance scheduler evidence.

## Must be completed before full rollout

- [ ] One-pod/ten-user pilot passes for three clean working days.
- [ ] Zero lost submissions is sustained for two weeks.
- [ ] On-time submission reaches 95% for four consecutive weeks.
- [ ] Platform, Security, Compliance, Data, Product, and Part 2 owners sign the
  immutable release manifest.

Do not convert an unchecked environment item into a pass without attaching its
sanitized evidence and named approval.
