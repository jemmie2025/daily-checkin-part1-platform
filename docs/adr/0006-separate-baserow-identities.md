# ADR-0006: Use Separate Baserow Writer Identities

- Status: Accepted
- Date: 2026-09-04

## Context

The system has three Baserow write targets with mutually exclusive writers:
`checkins`, `checkin_violations`, and `checkin_dlq`. A single token scoped to
multiple tables would weaken those boundaries.

## Decision

Use three independently rotatable Baserow service identities:

- Submit Handler: create/read access to `checkins` only.
- Compliance Worker: create/read/update access to `checkin_violations` and
  read-only access to the minimum check-in fields required for comparison.
- Submit Error Workflow: create/read/update access to `checkin_dlq` only.

## Consequences

- A compromised workflow cannot write another component's table.
- Vault stores and rotates three separate credentials.
- Audit logs identify the responsible writer without inference.
