const inputs = $input.all().map((item) => item.json);
const executions = [];
for (const input of inputs) {
  if (Array.isArray(input.data)) executions.push(...input.data);
  else if (Array.isArray(input.results)) executions.push(...input.results);
  else executions.push(input);
}

const required = [
  'correlation_id', 'user_id', 'pod_id', 'cycle_date', 'checkin_type',
  'failure_stage', 'error_code', 'raw_submission', 'mattermost_dm_channel_id',
];
const output = new Map();

function collect(value, found, seen) {
  if (!value || typeof value !== 'object' || seen.has(value)) return;
  seen.add(value);
  if (!Array.isArray(value) && value.checkin_context && typeof value.checkin_context === 'object') {
    found.push(value.checkin_context);
  }
  for (const child of Array.isArray(value) ? value : Object.values(value)) collect(child, found, seen);
}

for (const execution of executions) {
  const executionId = String(execution.id ?? execution.execution?.id ?? '');
  if (!executionId) continue;
  const contexts = [];
  collect(execution.data ?? execution, contexts, new Set());
  for (const context of contexts) {
    if (required.some((field) => context[field] === undefined || context[field] === null)) continue;
    const identity = `${executionId}|${context.failure_stage}`;
    output.set(identity, {
      json: {
        execution: {
          id: executionId,
          error: execution.data?.resultData?.error ?? execution.execution?.error ?? execution.error ?? null,
        },
        checkin_context: Object.fromEntries(required.map((field) => [field, context[field]])),
      },
    });
  }
}

return [...output.values()].sort((left, right) => (
  `${left.json.execution.id}|${left.json.checkin_context.failure_stage}`
    .localeCompare(`${right.json.execution.id}|${right.json.checkin_context.failure_stage}`)
));
