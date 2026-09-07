const replay = $input.first().json;
const planned = $('Plan Stage-Safe Replay').item.json;
const leased = $('Acquire Replay Lease').item.json;
const required = ['status', 'checkin_id', 'correlation_id', 'replay_key'];
if (!replay || typeof replay !== 'object' || Array.isArray(replay)
  || Object.keys(replay).some((field) => !required.includes(field))
  || required.some((field) => !Object.prototype.hasOwnProperty.call(replay, field))) {
  throw new Error('replay response does not match replay-response.v1');
}
if (replay.status !== 'resolved') throw new Error('replay response status is not resolved');
if (typeof replay.checkin_id !== 'string' || replay.checkin_id.length < 8 || replay.checkin_id.length > 300) {
  throw new Error('replay response checkin_id is invalid');
}
if (replay.correlation_id !== planned.correlation_id || replay.replay_key !== planned.replay_key) {
  throw new Error('replay response identity does not match request');
}
const rowId = Number(leased.id ?? planned.id);
if (!Number.isInteger(rowId) || rowId < 1) throw new Error('leased DLQ row identity is invalid');
const resolvedAt = new Date();
const deleteAfter = new Date(resolvedAt.getTime() + 30 * 24 * 60 * 60 * 1000);
return [{
  json: {
    row_id: rowId,
    patch: {
      status: 'resolved',
      resolved_at: resolvedAt.toISOString(),
      resolved_checkin_id: replay.checkin_id,
      next_retry_at: null,
      retention_delete_after: deleteAfter.toISOString(),
    },
  },
}];
