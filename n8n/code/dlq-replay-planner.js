const input = $input.first().json;
const now = new Date(input.now ?? new Date().toISOString());
if (Number.isNaN(now.getTime())) throw new Error('now must be RFC3339');

const rows = input.results ?? input.rows ?? [];
if (!Array.isArray(rows)) throw new Error('DLQ candidate response must contain an array');
const steps = {
  baserow_checkins_write: ['upsert_checkin', 'ensure_canonical_post', 'ensure_event'],
  mattermost_canonical_post: ['verify_checkin', 'ensure_canonical_post', 'ensure_event'],
  event_dispatch: ['verify_checkin', 'verify_canonical_post', 'ensure_event'],
};
const selectValue = (value) => (
  value && typeof value === 'object' && !Array.isArray(value) ? value.value : value
);
const parseOptionalDate = (value, field) => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error(`${field} must be RFC3339`);
  return parsed;
};
const requiredText = (value, field, maximum = 300) => {
  if (typeof value !== 'string' || !value.length || value.length > maximum) {
    throw new Error(`${field} is invalid`);
  }
  return value;
};
const output = [];

for (const row of rows) {
  const status = selectValue(row.status);
  if (!['pending', 'replaying'].includes(status)) continue;
  const nextRetry = parseOptionalDate(row.next_retry_at, 'next_retry_at');
  if (nextRetry && now < nextRetry) continue;

  const replayStarted = parseOptionalDate(row.replay_started_at, 'replay_started_at');
  if (status === 'replaying') {
    if (!replayStarted) throw new Error('replaying row is missing replay_started_at');
    if (now.getTime() - replayStarted.getTime() < 15 * 60 * 1000) continue;
  }

  const failureStage = selectValue(row.failure_stage);
  if (!steps[failureStage]) throw new Error('invalid DLQ failure_stage');
  const rowId = Number(row.id);
  if (!Number.isInteger(rowId) || rowId < 1) throw new Error('DLQ row id is invalid');
  const replayKey = requiredText(row.replay_key, 'replay_key');
  const correlationId = requiredText(row.correlation_id, 'correlation_id', 128);
  if (typeof row.raw_submission !== 'string' || !row.raw_submission.length
    || Buffer.byteLength(row.raw_submission, 'utf8') > 65536) {
    throw new Error('raw_submission byte limit violated');
  }

  output.push({
    json: {
      ...row,
      id: rowId,
      status: 'replaying',
      failure_stage: failureStage,
      replay_key: replayKey,
      correlation_id: correlationId,
      replay_started_at: now.toISOString(),
      replay_owner: `n8n-dlq-${$execution.id}`,
      replay_attempt_count: Number(row.replay_attempt_count ?? 0) + 1,
      replay_steps: steps[failureStage],
    },
  });
}
return output;
