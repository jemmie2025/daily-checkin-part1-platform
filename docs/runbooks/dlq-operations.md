# DLQ Operations Runbook

## Failure boundary

The Submit Handler performs three total attempts. It waits one second before
attempt two and four seconds before attempt three. After the third failure, its
n8n execution is the durable first copy; the DLQ workflow mirrors a
deterministic row, sends the submitter their exact input, and schedules the
first recovery scan after 16 seconds.

If Baserow itself is unavailable, the mirror may fail but the source execution
must remain retained. The same workflow scans saved failed Submit executions
every five minutes and creates any missing deterministic row after recovery.
Never mark an execution pruned until its deterministic DLQ row exists.

The Submit workflow must save `checkin_context` immediately before each
downstream side effect. The DLQ worker's n8n API key is `execution:read` only;
any edit/run/admin scope fails the security gate. Keep the capture workflow and
replay workflow at one active scheduler each.

The configured `BASEROW_DLQ_REPLAY_VIEW_ID` must point to the private
`checkin_dlq_replay_pending` view containing only `pending` and `replaying`
rows. Verify this filter after every schema migration. The worker fetches at
most 100 ordered candidates and independently rejects not-due or actively
leased rows.

## Operator replay

1. Confirm the downstream dependency is healthy.
2. Locate the row by `dlq_id`; do not paste `raw_submission` into a ticket.
3. Confirm `status` is `pending`, or that a `replaying` lease is older than 15
   minutes.
4. Confirm the stage-specific plan in ADR-0009.
5. Let the dedicated replay worker acquire the row; never replay by manually
   posting a message or inserting a check-in.
6. Verify the Part 2 endpoint returned the canonical `checkin_id`.
7. Confirm one check-in, one canonical post, and one event exist.
8. Confirm the DLQ row is `resolved` with a 30-day deletion timestamp.

If the source execution contains no valid `checkin_context`, stop: this is a
Part 2 contract breach. Do not reconstruct task text from logs or Mattermost.

## Outage drill

In isolated staging, deny Baserow for longer than all three attempts, submit a
unique fixture, restore Baserow, and run recovery. The drill passes only when
the original text is byte-identical, the user receives one DM, replay creates
no duplicate side effect, and the source execution maps to exactly one DLQ row.

## Abandonment

Use `abandoned` only after the system owner documents why recovery is unsafe or
impossible and the data owner approves the decision. Retention deletion must
follow the restricted-data policy; never delete an unresolved row to reduce an
alert count.
