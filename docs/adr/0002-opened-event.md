# ADR-0002: Emit `checkin.opened` Outside the Open Handler

- Status: Accepted
- Date: 2026-09-04

## Context

The Open Handler must perform no writes and return inside two seconds, while the
observability contract requires a `checkin.opened` event.

## Decision

APISIX emits sanitized request telemetry asynchronously. The telemetry adapter
creates `checkin.opened` only for an authenticated open request that receives
the agreed successful upstream outcome. The Open Handler does not call
ClickHouse or any event store.

## Consequences

- Analytics cannot delay or fail the dialog path.
- Gateway telemetry must carry a correlation ID and sanitized success signal.
- Telemetry is delivery-at-least-once and deduplicated by `event_id`.
