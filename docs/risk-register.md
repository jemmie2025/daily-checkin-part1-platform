# Risk Register

| ID | Risk | Impact | Control | Residual risk |
|---|---|---|---|---|
| R-01 | Mattermost `trigger_id` expires before dialog opens | Dialog failure | Separate routes; 2-second budget; no synchronous enrichment | Low |
| R-02 | Unverified `user_id` bypasses per-user throttling | Abuse or spoofing | Verify authentication first; two-layer throttling fallback | Medium until gateway capability is confirmed |
| R-03 | Baserow outage also prevents DLQ insert | Lost submission | Durable n8n execution record plus later DLQ mirror | Low |
| R-04 | Scheduler repeats create duplicate PI-6 violations | Incorrect compliance totals | Deterministic violation ID and upsert | Low |
| R-05 | UTC date differs from user-local cycle date | False missing/late status | Store local `cycle_date`; calculate due time with IANA timezone | Low |
| R-06 | Leave or holiday data is stale | False escalation | Version roster input; suppress non-expected staff; reconciliation report | Medium |
| R-07 | Raw task text leaks through logs or telemetry | Privacy incident | Field allowlists, log redaction, telemetry schema tests | Low |
| R-08 | At-least-once delivery duplicates analytics | Inflated metrics | Stable `event_id`; ClickHouse deduplication view/table design | Low |
| R-09 | Part 2 sends incompatible payloads | Integration failure | Versioned JSON Schema and consumer validation in CI | Low |
| R-10 | Dashboard denominator excludes expected staff incorrectly | Misleading compliance rate | Expected-roster contract and source reconciliation | Medium |
| R-11 | APISIX direct Vault integration is incompatible with the chosen KV v2 engine | Gateway cannot resolve plugin credentials | Nomad KV v2 template renders scoped variables consumed through APISIX `$ENV://` references | Low after staging verification |
| R-12 | APISIX encrypts HTTPS upstream traffic but does not validate the upstream certificate | Potential internal MITM | Keep the hop inside the restricted Nomad network and require an approved verified-TLS/service-mesh proxy where the threat model demands server authentication | Medium until network design is confirmed |
| R-13 | Multiple n8n trust classes execute in one process | One workflow can read another writer's credential | Six dedicated Nomad tasks and claim-bound roles; fail Phase 3 if topology is shared | Medium until Nomad topology is confirmed |
| R-14 | Secret-bearing environment is exposed through task introspection or debug output | Credential disclosure | Isolated task identity, no Vault token exposure, secrets-dir mode `0400`, disabled debug dumps, and log leak tests | Low after runtime inspection |
| R-15 | Rotation updates Vault but leaves the old downstream credential active | Exposure persists despite a new KV version | Require downstream revocation plus negative old-credential check as separate evidence | Low with runbook execution |
| R-16 | Vault cannot write audit records | Vault requests become unavailable | Operate and monitor at least two independent audit devices | Low after platform sign-off |
| R-17 | DLQ reconciliation credential can read more n8n data than required | Workflow input or credential disclosure | Dedicated capture workload, read-only execution API credential, submit-workflow filter, closed `checkin_context`, and negative authorization test | Medium until the installed n8n API scope is verified |
| R-18 | Compliance input snapshot is stale or incomplete | False nudges, violations, or denominators | Versioned snapshot contract, source timestamps, deterministic suppression rules, and source reconciliation before each production run | Medium |
| R-19 | Aggregate archive refresh stops after detail TTL expiry | Permanent analytics gap | Refresh at month 23, monitor `system.view_refreshes`, reconcile archive counts, and alert before the 24-month detail TTL | Low after staging soak |
