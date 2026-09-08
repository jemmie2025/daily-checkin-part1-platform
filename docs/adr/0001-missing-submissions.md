# ADR-0001: Represent Missing Submissions as Violations

- Status: Accepted
- Date: 2026-09-04

## Context

The master plan says the Submit Handler is the sole writer to `checkins` and the
Compliance Worker writes only `checkin_violations`. It also asks the Compliance
Worker to mark a missing `checkins` row. A missing submission has no row to
update, and creating one would violate both boundaries.

## Decision

The Compliance Worker creates one idempotent PI-6 record in
`checkin_violations`. It never creates or modifies a `checkins` row. Reporting
derives missing status from expected submissions minus accepted check-ins.

## Consequences

- `checkins` remains an evidence table containing real user submissions only.
- Missing status is auditable without fabricated rows.
- ClickHouse reporting views must combine expected-roster, check-in, and violation data when
  calculating compliance.
