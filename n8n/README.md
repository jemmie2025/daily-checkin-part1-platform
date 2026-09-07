# n8n workflow package

The six JSON files in `workflows/` are deterministic, importable templates for
n8n 2.36+. Import them inactive, map environment values, test with isolated
accounts, and activate only after the release gate passes.

## Workload placement

| Workflow | Dedicated task | Write authority |
|---|---|---|
| Compliance v1 | `n8n-compliance` | `checkin_violations` only |
| Weekly Rollup v1 | `n8n-compliance` | Mattermost posts only |
| DLQ Capture/Reconciliation v1 | `n8n-dlq` | `checkin_dlq` only |
| DLQ Replay v1 | `n8n-dlq` | `checkin_dlq`; invokes the Part 2 replay contract |
| Event Ingestion v1 | `n8n-analytics` | ClickHouse events only |
| Expectation Ingestion v1 | `n8n-analytics` | ClickHouse expectations only |

Open and Submit remain on their separate Part 2 tasks. Never import these
workflows into one shared worker because every Code node in a process can see
that process's environment.

## Safe import procedure

1. Run `make validate` and retain its clean output.
2. Import files from `n8n/workflows/`; do not edit the generated JSON directly.
3. Set non-secret endpoints and table/field IDs from an environment-specific
   configuration outside Git.
4. Deliver secret variables through the matching Vault/Nomad template.
5. Allow only Node's built-in `crypto` module. Do not allow external Code-node
   modules.
6. Keep failed executions for 30 days and disable successful execution-body
   retention for these workflows.
7. Give the DLQ task an n8n API key scoped to `execution:read` only, bind
   `N8N_SUBMIT_WORKFLOW_ID`, and deny that key outside the internal service path.
8. Bind `BASEROW_DLQ_REPLAY_VIEW_ID` to the private view containing only
   `pending` and `replaying` DLQ rows.
9. Run Compliance and DLQ scheduled workflows as single active schedulers;
   uniqueness constraints remain the cross-restart safety boundary.
10. Run the fixture tests and sanitized smoke tests before activation.
11. Export the workflows and prove their hashes match the reviewed files.

`scripts/render_n8n.py` embeds the reviewed files from `n8n/code/` into the
templates. To update a Code node, edit its source file, run `make render-n8n`,
review the generated workflow, and rerun the full gate.

## Part 2 replay requirement

Part 2 must persist the closed `submit-failure-context.v1` object under an item
property named `checkin_context` immediately before each submit side effect and
select the capture/reconciliation workflow as its error workflow. This lets the
DLQ worker retrieve the exact saved input without embedding it in error text or
logs. The five-minute scan repairs any mirror missed during a Baserow outage.

The DLQ replay workflow calls the Part 2 replay endpoint with the original
`correlation_id`, `replay_key`, failed stage, ordered remaining steps, and raw
submission. The endpoint must upsert by canonical `checkin_id`, reuse the
canonical post identity, reuse the original event ID, and return `checkin_id`.
It must never interpret a replay as an ADHOC amendment.

Event ingestion authenticates before validation, validates the complete nested
v1 contract, and returns 401, 400, 409, 200, or 202 explicitly. Invalid or
unauthenticated input never reaches ClickHouse.
