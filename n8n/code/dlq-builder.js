const crypto = require('crypto');
const input = $input.first().json;
const context = input.checkin_context;
if (!context || typeof context !== 'object' || Array.isArray(context)) {
  throw new Error('checkin_context is required; raw input was not logged');
}
const required = [
  'correlation_id', 'user_id', 'pod_id', 'cycle_date', 'checkin_type',
  'failure_stage', 'error_code', 'raw_submission', 'mattermost_dm_channel_id',
];
if (Object.keys(context).some((field) => !required.includes(field))) throw new Error('checkin_context has unknown fields');
for (const field of required) {
  if (context[field] === undefined || context[field] === null) throw new Error(`checkin_context missing ${field}`);
}

for (const field of ['user_id', 'pod_id', 'mattermost_dm_channel_id', 'error_code']) {
  if (typeof context[field] !== 'string' || !context[field].length || context[field].length > 128) {
    throw new Error(`checkin_context ${field} is invalid`);
  }
}
if (typeof context.correlation_id !== 'string' || context.correlation_id.length < 8 || context.correlation_id.length > 128) {
  throw new Error('checkin_context correlation_id is invalid');
}
if (!['SOD', 'EOD', 'ADHOC'].includes(context.checkin_type)) throw new Error('invalid checkin_type');
const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(context.cycle_date);
const parsedDate = dateMatch
  ? new Date(Date.UTC(Number(dateMatch[1]), Number(dateMatch[2]) - 1, Number(dateMatch[3])))
  : null;
if (!dateMatch || parsedDate.getUTCFullYear() !== Number(dateMatch[1])
  || parsedDate.getUTCMonth() !== Number(dateMatch[2]) - 1
  || parsedDate.getUTCDate() !== Number(dateMatch[3])) {
  throw new Error('invalid cycle_date');
}

const failureStage = context.failure_stage;
if (!['baserow_checkins_write', 'mattermost_canonical_post', 'event_dispatch'].includes(failureStage)) {
  throw new Error('invalid failure_stage');
}
const executionId = String(input.execution?.id ?? context.source_execution_id ?? '');
if (!executionId) throw new Error('source execution id is required');
const digest = (...parts) => crypto.createHash('sha256').update(parts.join('|')).digest('hex').slice(0, 32);
const sanitize = (value) => String(value ?? 'Unspecified downstream failure')
  .replace(/(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+/gi, '$1[REDACTED]')
  .replace(/((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]')
  .replace(/[\r\n]+/g, ' ')
  .slice(0, 2000);
const createdAt = new Date().toISOString();
const nextRetryAt = new Date(Date.now() + 16000).toISOString();
const dlqId = `dlq_${digest(executionId, failureStage)}`;
if (typeof context.raw_submission !== 'string') throw new Error('raw_submission must be a string');
const raw = context.raw_submission;
if (!raw.length || Buffer.byteLength(raw, 'utf8') > 65536) throw new Error('raw_submission byte limit violated');
const longestFence = Math.max(0, ...([...raw.matchAll(/`+/g)].map((match) => match[0].length)));
const fence = '`'.repeat(Math.max(3, longestFence + 1));

const record = {
  dlq_id: dlqId,
  replay_key: `${executionId}|${failureStage}`,
  source_workflow: 'checkin_submit_v1',
  source_execution_id: executionId,
  correlation_id: context.correlation_id,
  user_id: context.user_id,
  pod_id: context.pod_id,
  cycle_date: context.cycle_date,
  checkin_type: context.checkin_type,
  failure_stage: failureStage,
  attempt_count: 3,
  status: 'pending',
  last_error_code: String(context.error_code ?? 'DOWNSTREAM_FAILURE').slice(0, 128),
  last_error_summary: sanitize(input.execution?.error?.message ?? context.error_summary),
  raw_submission: raw,
  created_at: createdAt,
  next_retry_at: nextRetryAt,
  dm_notified_at: null,
  resolved_at: null,
  resolved_checkin_id: null,
  replay_started_at: null,
  replay_owner: null,
  replay_attempt_count: 0,
  retention_delete_after: null,
};
const dmMessage = `Your Daily Check-in could not be safely stored after three attempts. Reference: \`${dlqId}\`. Your exact input is preserved below:\n\n${fence}\n${raw}\n${fence}\n\nOperations has queued it for controlled replay; please do not resubmit unless contacted.`;
return [{ json: { record, dm_channel_id: context.mattermost_dm_channel_id, dm_message: dmMessage } }];
