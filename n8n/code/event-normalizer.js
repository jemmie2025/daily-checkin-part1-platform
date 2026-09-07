const crypto = require('crypto');
const envelope = $input.first().json;

function exactObject(value, required, optional = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('expected object');
  const actual = Object.keys(value).sort();
  const allowed = [...required, ...optional].sort();
  if (actual.some((key) => !allowed.includes(key))) throw new Error('unknown object field');
  if (required.some((key) => !Object.prototype.hasOwnProperty.call(value, key))) {
    throw new Error('missing object field');
  }
}

function stringField(value, name, minimum, maximum, pattern = null) {
  if (typeof value !== 'string' || value.length < minimum || value.length > maximum) {
    throw new Error(`${name} has invalid length`);
  }
  if (pattern && !pattern.test(value)) throw new Error(`${name} has invalid format`);
}

function integerField(value, name, minimum, maximum = Number.MAX_SAFE_INTEGER) {
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${name} must be an integer in range`);
  }
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day;
}

function validateAndFlatten(event) {
  exactObject(event, [
    'correlation_id', 'cycle', 'dialog_version', 'event_id', 'event_name', 'event_version',
    'occurred_at', 'outcome', 'pod', 'source', 'trace', 'user',
  ]);

  const forbidden = new Set([
    'user_name', 'tasks', 'tasks_md', 'tasks_json', 'proof_link', 'proof_links',
    'raw_submission', 'state', 'nonce', 'token',
  ]);
  function walk(value) {
    if (Array.isArray(value)) return value.forEach(walk);
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (forbidden.has(key)) throw new Error('event contains forbidden private fields');
      walk(child);
    }
  }
  walk(event);

  stringField(event.event_id, 'event_id', 36, 36, /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  if (!['checkin.opened', 'checkin.submitted', 'checkin.rejected', 'checkin.cancelled'].includes(event.event_name)) {
    throw new Error('unsupported event_name');
  }
  if (event.event_version !== 1 || event.dialog_version !== 'checkin_v1') {
    throw new Error('unsupported event version');
  }
  stringField(event.occurred_at, 'occurred_at', 20, 40, /(?:Z|[+-]\d{2}:\d{2})$/);
  if (Number.isNaN(Date.parse(event.occurred_at))) throw new Error('occurred_at must be RFC3339');
  stringField(event.correlation_id, 'correlation_id', 8, 128, /^[A-Za-z0-9._:-]+$/);
  if (!['apisix_telemetry', 'n8n_submit_handler'].includes(event.source)) throw new Error('unsupported source');

  exactObject(event.user, ['user_id']);
  stringField(event.user.user_id, 'user.user_id', 1, 128);
  exactObject(event.pod, ['pod_id']);
  stringField(event.pod.pod_id, 'pod.pod_id', 1, 128);
  exactObject(event.cycle, ['cycle_date', 'checkin_type', 'sla_code']);
  if (!validDate(event.cycle.cycle_date)) throw new Error('cycle.cycle_date must be a real date');
  if (!['SOD', 'EOD', 'ADHOC'].includes(event.cycle.checkin_type)) throw new Error('invalid checkin_type');
  stringField(event.cycle.sla_code, 'cycle.sla_code', 1, 128);

  exactObject(event.outcome, ['latency_ms'], [
    'sla_status', 'task_count', 'done_count', 'blocked_count', 'has_proof', 'rule_ids',
  ]);
  integerField(event.outcome.latency_ms, 'outcome.latency_ms', 0);
  if (event.outcome.sla_status !== undefined && !['on_time', 'late'].includes(event.outcome.sla_status)) {
    throw new Error('invalid sla_status');
  }
  for (const name of ['task_count', 'done_count', 'blocked_count']) {
    if (event.outcome[name] !== undefined) integerField(event.outcome[name], `outcome.${name}`, 0, 20);
  }
  if (event.outcome.has_proof !== undefined && typeof event.outcome.has_proof !== 'boolean') {
    throw new Error('outcome.has_proof must be boolean');
  }
  if (event.outcome.rule_ids !== undefined) {
    const ids = event.outcome.rule_ids;
    if (!Array.isArray(ids) || ids.length < 1 || ids.some((id) => typeof id !== 'string' || !/^(FMT-[1-8]|PI-[0-9]+)$/.test(id))) {
      throw new Error('outcome.rule_ids is invalid');
    }
    if (new Set(ids).size !== ids.length) throw new Error('outcome.rule_ids must be unique');
  }

  exactObject(event.trace, ['request_id'], ['execution_id']);
  stringField(event.trace.request_id, 'trace.request_id', 8, 128);
  if (event.trace.execution_id !== undefined) stringField(event.trace.execution_id, 'trace.execution_id', 1, 128);

  if (event.event_name === 'checkin.opened' && event.source !== 'apisix_telemetry') {
    throw new Error('opened events must come from APISIX telemetry');
  }
  if (event.event_name === 'checkin.submitted') {
    if (event.source !== 'n8n_submit_handler') throw new Error('submitted event source is invalid');
    for (const field of ['sla_status', 'task_count', 'done_count', 'blocked_count', 'has_proof']) {
      if (event.outcome[field] === undefined) throw new Error(`submitted outcome missing ${field}`);
    }
    if (event.outcome.done_count + event.outcome.blocked_count > event.outcome.task_count) {
      throw new Error('submitted outcome counts exceed task_count');
    }
    if (Object.keys(event.outcome).length !== 6) throw new Error('submitted outcome has invalid fields');
  }
  if (event.event_name === 'checkin.rejected') {
    if (event.source !== 'n8n_submit_handler') throw new Error('rejected event source is invalid');
    if (event.outcome.rule_ids === undefined) throw new Error('rejected outcome missing rule_ids');
    if (Object.keys(event.outcome).length !== 2) throw new Error('rejected outcome has invalid fields');
  }
  if (event.event_name === 'checkin.cancelled') {
    if (event.source !== 'n8n_submit_handler') throw new Error('cancelled event source is invalid');
    if (Object.keys(event.outcome).length !== 1) throw new Error('cancelled outcome has invalid fields');
  }
  if (event.event_name === 'checkin.opened' && Object.keys(event.outcome).length !== 1) {
    throw new Error('opened outcome has invalid fields');
  }

  const canonicalize = (value) => {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  };
  const payloadHash = crypto.createHash('sha256').update(JSON.stringify(canonicalize(event))).digest('hex');
  return {
    event_id: event.event_id,
    event_name: event.event_name,
    event_version: event.event_version,
    occurred_at: event.occurred_at,
    correlation_id: event.correlation_id,
    source: event.source,
    user_id: event.user.user_id,
    pod_id: event.pod.pod_id,
    cycle_date: event.cycle.cycle_date,
    checkin_type: event.cycle.checkin_type,
    sla_code: event.cycle.sla_code,
    dialog_version: event.dialog_version,
    latency_ms: event.outcome.latency_ms,
    sla_status: event.outcome.sla_status ?? null,
    task_count: event.outcome.task_count ?? null,
    done_count: event.outcome.done_count ?? null,
    blocked_count: event.outcome.blocked_count ?? null,
    has_proof: event.outcome.has_proof ?? null,
    rule_ids: event.outcome.rule_ids ?? [],
    request_id: event.trace.request_id,
    execution_id: event.trace.execution_id ?? null,
    payload_hash: payloadHash,
  };
}

const supplied = String(envelope.headers?.authorization ?? '').replace(/^Bearer\s+/i, '');
const expected = String($env.CHECKIN_EVENT_INGEST_TOKEN ?? '');
const suppliedBytes = Buffer.from(supplied);
const expectedBytes = Buffer.from(expected);
if (!expected || suppliedBytes.length !== expectedBytes.length || !crypto.timingSafeEqual(suppliedBytes, expectedBytes)) {
  return [{ json: { disposition: 'unauthorized', error_code: 'UNAUTHORIZED' } }];
}

try {
  const incoming = validateAndFlatten(envelope.body);
  return [{ json: { disposition: 'valid', incoming } }];
} catch (_error) {
  return [{ json: { disposition: 'invalid', error_code: 'INVALID_EVENT_CONTRACT' } }];
}
