# Requirements Traceability

| Requirement | Owner | Implementation | Verification |
|---|---|---|---|
| SUB-1 APISIX policies | Part 1 | `config/apisix.gateway.example.yaml`, custom plugin, deterministic renderer | Policy, fail-closed, and latency-plan tests |
| SUB-1 Vault bindings | Part 1 | Six exact-path policies/roles/tasks over eight KV v2 objects | Policy, isolation, rotation, and secret-scan tests |
| Open route has no writes | Part 2 behavior; Part 1 enforcement | Isolated route and async access telemetry | Architecture and rendered-route tests |
| 10 requests/minute/user | Part 1 | Distributed verified-user throttle | Eleventh-request policy/k6 test |
| Mattermost Nomad CIDR only | Part 1 | Source allowlist before identity extraction | Denied-source policy/k6 test |
| 64 KiB body cap | Part 1 | Gateway client control | 65,537-byte policy/k6 rejection test |
| Compliance SLA −60 DM | Part 1 | `checkin-compliance-v1` deterministic action | Fake-clock boundary tests |
| PI-6 breach record | Part 1 | Unique `violation_id` plus read-before-create | Stable-ID and repeated-run tests |
| SLA +24 hour digest | Part 1 | One deterministic action per pod/date/type | Pod-grouping fixture test |
| Weekly pod rollup | Part 1 | `checkin-weekly-rollup-v1` | Expected/submitted reconciliation tests |
| Failed-write DLQ | Part 1 | Error trigger plus five-minute saved-execution reconciliation | Deterministic record, recovery, and workflow tests |
| Verbatim-input failure DM | Part 1 | Byte-preserved fenced DM and persisted receipt | Exact-body and duplicate-guard tests |
| Stage-aware replay | Part 1 orchestration; Part 2 endpoint | 15-minute lease and ordered replay contract | Three-stage and stale-lease tests |
| `checkin.*` telemetry | Part 1 ingestion; Part 2/APISIX producers | Authenticated strict-v1 ingestion | Runtime 400/401 plus four-event contract tests |
| Superset metrics | Part 1 | Three reporting datasets and six-chart dashboard | Source-to-chart reconciliation and asset tests |
| 24-month detail retention | Part 1 analytics | Monthly TTL plus day-23 aggregate archive | DDL TTL/archive/refresh inspection |
| Aggregate retention thereafter | Part 1 analytics | Aggregate-only refreshable views and reporting unions | Privacy and reporting-view tests |
| Secrets from Vault only | Part 1 | KV v2 runtime templates; no Vault token in tasks | Tree/history scan plus live path isolation |
| Proof-link sanitization | Part 2 behavior; Part 1 security gate | Contract acceptance evidence | Malicious-URL test evidence |
| FMT-1–FMT-8 | Part 2 | Outside Part 1 implementation | Consumed rejection events |
| Canonical threaded post | Part 2 | Outside Part 1 implementation | Downstream integration evidence |
