# Part 1 Published Interface

This is the independent integration boundary for Task #5585. Part 2 can satisfy
these contracts without editing Part 1 implementation, and Part 1 does not need
write access to Part 2's `checkins` table.

## 1. Event submission

Producers send one object conforming to
`events/checkin-event.v1.schema.json` with `Content-Type: application/json` and
the shared producer credential in `Authorization: Bearer …`. Delivery is
at-least-once. A producer must reuse `event_id` for the same logical event and
must never reuse it for different content.

| Result | HTTP | Retry rule |
|---|---:|---|
| Accepted | 202 | Stop |
| Identical duplicate | 200 | Stop |
| Invalid v1 contract | 400 | Correct producer; do not retry unchanged |
| Authentication failure | 401 | Rotate/fix credential; do not retry unchanged |
| Conflicting payload for existing ID | 409 | Stop and page producer/data owners |
| Backpressure/unavailable | 429/503 | Bounded retry with the same event ID |

Events may contain stable IDs, cycle metadata, counts, states, timings, and rule
IDs only. Raw tasks, proof URLs, usernames, dialog state, nonces, and failed
submissions are forbidden recursively.

## 2. Gateway success signal

The Open Handler returns HTTP 200 with body `{}`. After `dialogs/open` succeeds,
it also sets `X-Checkin-Outcome: opened`. APISIX strips that internal header from
the public response and uses it only for asynchronous, sanitized
`checkin.opened` telemetry. The Open Handler performs no analytics call and no
application-database write.

## 3. Correlation

- APISIX creates or accepts one `correlation_id` per command invocation.
- The same value follows open, submit, failure, replay, and telemetry records.
- n8n `execution_id` is a separate diagnostic identity and never replaces it.
- DLQ replay keeps the original correlation ID, execution ID, replay key,
  canonical check-in ID, canonical post identity, and event ID.

## 4. Compliance snapshot

The configured snapshot endpoint returns one object conforming to
`compliance/compliance-snapshot.v1.schema.json`. It supplies the cycle date,
versioned roster, IANA timezones, SLA rules, leave, holidays, accepted check-ins,
existing PI-6 violations, and committed action IDs. It is read-only to Part 1.

The source must fail closed when roster, calendar, SLA, or check-in data is
stale or incomplete. It must not silently treat an unavailable leave source as
an empty leave list.

## 5. Submit failure handoff

Immediately before each downstream submit side effect, Part 2 persists an n8n
item property named `checkin_context` whose value conforms exactly to
`reliability/submit-failure-context.v1.schema.json`. The item may contain other
working fields, but `checkin_context` itself is closed to unknown fields.

Part 2 configures `Daily Check-in — DLQ Capture and Reconciliation v1` as the
Submit workflow's error workflow. After exactly three total attempts (wait one
second, then four seconds), the failed execution remains saved for 30 days. The
isolated Part 1 DLQ worker retrieves that execution with `execution:read`,
extracts the context, creates the deterministic DLQ row, and records the user-DM
receipt. Its five-minute reconciliation trigger repairs a mirror missed during
a Baserow outage. Part 2 never writes `checkin_dlq` directly.

The source execution must retain the exact raw UTF-8 input, not normalized or
reconstructed Markdown. The 64 KiB byte ceiling still applies.

## 6. Replay endpoint

Part 2 exposes the internal endpoint configured as `CHECKIN_REPLAY_URL`. It
accepts `reliability/replay-request.v1.schema.json`, authenticates the DLQ worker,
and validates these headers:

- `Idempotency-Key`: the original `replay_key`.
- `X-Correlation-ID`: the original `correlation_id`.

The endpoint executes only the ordered `replay_steps`, using upsert/ensure
semantics for every side effect. It returns
`reliability/replay-response.v1.schema.json` only after the canonical check-in,
post, and event are confirmed. A replay is recovery of the original submission,
never an ADHOC amendment.

| Failed stage | Required replay sequence |
|---|---|
| `baserow_checkins_write` | `upsert_checkin`, `ensure_canonical_post`, `ensure_event` |
| `mattermost_canonical_post` | `verify_checkin`, `ensure_canonical_post`, `ensure_event` |
| `event_dispatch` | `verify_checkin`, `verify_canonical_post`, `ensure_event` |

## 7. Persistence constraints

- `checkin_violations.violation_id` is unique.
- `checkin_dlq.dlq_id` is unique.
- `BASEROW_DLQ_REPLAY_VIEW_ID` resolves to a private view containing only
  `pending` and `replaying` DLQ rows; the worker applies the due/lease checks.
- Part 2 supplies the deployed `checkins` table identifier as configuration;
  it does not supply a writer credential to Compliance or DLQ.
- The Compliance worker is the only writer to `checkin_violations`.
- The Submit Error workflow is the only writer to `checkin_dlq`.

## 8. Compatibility

Optional additive fields require a reviewed schema update before any producer
sends them. Renaming, removal, type/meaning changes, or new mandatory fields
require contract v2. Unknown v1 fields fail closed. Every producer must run the
consumer fixtures before rollout.
