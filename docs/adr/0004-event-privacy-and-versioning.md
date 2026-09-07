# ADR-0004: Version and Minimize Analytics Events

- Status: Accepted
- Date: 2026-09-04

## Context

Analytics needs user, pod, cycle, latency, status, and count dimensions. It does
not require task text, proof URLs, dialog state, or a person's display name.

## Decision

All events conform to `checkin-event.v1`, contain `event_version=1`, and use a
strict field allowlist. Breaking changes create a new integer version. Raw task
content, proof links, usernames, state, nonces, and tokens are forbidden.

## Consequences

- Event producers and ingestion validate against the same schema.
- Optional additive fields are allowed only after the schema is updated first.
- Dashboards use stable machine fields and avoid unnecessary personal data.
