# Compliance Operations Runbook

## Safety boundary

The compliance worker may read roster, SLA, leave, holiday, and accepted
check-in snapshots. It may write only `checkin_violations` and send Mattermost
messages. It never writes `checkins`, `checkin_dlq`, or ClickHouse.

## Activation

1. Confirm roster records contain unique Mattermost user IDs, IANA timezones,
   pod IDs, DM channel IDs, and pod-lead channel IDs.
2. Confirm SLA rules contain SOD/EOD, a versioned SLA code, and user-local
   `HH:MM` due time.
3. Reconcile approved leave and holiday versions with their source systems.
4. Import the Compliance and Weekly Rollup workflows into the dedicated
   `n8n-compliance` task.
5. Map Baserow violation table/field IDs outside Git and inject the scoped
   token from Vault.
6. Run a fake-clock fixture for one expected user, one leave user, one holiday,
   and one inactive user.
7. Verify one nudge at SLA minus 60, one PI-6 upsert at SLA, one late resolution,
   and one grouped digest at SLA plus 24 hours.
8. Rerun every trigger twice and verify counts do not increase.
9. Confirm only one active Compliance scheduler exists and both Baserow
   deterministic-ID fields have uniqueness constraints.

## Routine checks

- The worker completes within one five-minute schedule window.
- Snapshot source versions are non-empty and advance when source data changes.
- No suppressed user appears in a nudge, violation, digest, or denominator.
- Weekly totals reconcile exactly with the accepted `checkins` snapshot.
- Workflow success bodies are not retained; failures retain only the minimum
  operational context needed for recovery.

## Suppression reconciliation

Before every SLA window, compare approved leave, holiday scope, and inactive
dates with their recorded source versions. Any stale or conflicting source
fails the run; it must never default a person back into the expected set.

## Failure handling

If roster, calendar, or SLA data is unavailable or stale, fail the run and do
not create violations. If Baserow is unavailable, allow the execution to fail
and page the owner; do not redirect violation writes to another table. If the
Mattermost DM fails, retry three times and retain the deterministic action ID.

## Rollback

Deactivate the two workflows, restore the last reviewed workflow exports, and
reconcile the affected SLA window before reactivation. Waive an incorrect
violation only through the approved audit process; never delete it silently.
