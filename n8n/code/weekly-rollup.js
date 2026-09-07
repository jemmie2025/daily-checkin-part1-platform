const crypto = require('crypto');
const input = $input.first().json;
const expectations = input.expectations ?? [];
const checkins = input.checkins ?? [];
const start = input.period_start;
const end = input.period_end;

const parseDate = (value, field) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  if (!match) throw new Error(`${field} must use YYYY-MM-DD`);
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (parsed.getUTCFullYear() !== Number(match[1])
    || parsed.getUTCMonth() !== Number(match[2]) - 1
    || parsed.getUTCDate() !== Number(match[3])) {
    throw new Error(`${field} must be a real date`);
  }
  return parsed;
};
const startDate = parseDate(start, 'period_start');
const endDate = parseDate(end, 'period_end');
const dayCount = Math.round((endDate.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000));
if (dayCount < 0 || dayCount > 6) throw new Error('weekly period must span one to seven calendar days');
if (!Array.isArray(expectations) || !Array.isArray(checkins)) throw new Error('weekly rows must be arrays');

const digest = (...parts) => crypto.createHash('sha256').update(parts.join('|')).digest('hex').slice(0, 32);
const key = (row) => [row.user_id, row.cycle_date, row.checkin_type].join('|');
const within = (row) => row.cycle_date >= start && row.cycle_date <= end;
const pods = new Set(
  expectations.filter((row) => row.attendance_state === 'expected' && within(row)).map((row) => row.pod_id),
);
const output = [];

for (const podId of [...pods].sort()) {
  if (typeof podId !== 'string' || !podId.length) throw new Error('pod_id is invalid');
  const expected = new Set(
    expectations.filter((row) => row.pod_id === podId && row.attendance_state === 'expected' && within(row)).map(key),
  );
  const submittedMap = new Map(
    checkins.filter((row) => row.pod_id === podId && within(row) && expected.has(key(row))).map((row) => [key(row), row]),
  );
  const rows = [...submittedMap.values()];
  const expectedCount = expected.size;
  const submittedCount = rows.length;
  const proofCount = rows.filter((row) => Boolean(row.has_proof)).length;
  const blockedCount = rows.reduce((total, row) => {
    const count = Number(row.blocked_count ?? 0);
    if (!Number.isInteger(count) || count < 0 || count > 20) throw new Error('blocked_count is invalid');
    return total + count;
  }, 0);
  const channelId = input.pod_lead_channels?.[podId];
  if (typeof channelId !== 'string' || !channelId.length) throw new Error(`missing pod lead channel for ${podId}`);
  output.push({
    rollup_id: `rollup_${digest(podId, start, end)}`,
    pod_id: podId,
    channel_id: channelId,
    period_start: start,
    period_end: end,
    expected_count: expectedCount,
    submitted_count: submittedCount,
    missing_count: Math.max(expectedCount - submittedCount, 0),
    on_time_count: rows.filter((row) => row.sla_status === 'on_time').length,
    late_count: rows.filter((row) => row.sla_status === 'late').length,
    submission_rate: expectedCount ? submittedCount / expectedCount : 0,
    proof_attach_rate: submittedCount ? proofCount / submittedCount : 0,
    blocked_task_count: blockedCount,
  });
}

return output.map((rollup) => ({
  json: {
    ...rollup,
    message: `📊 Weekly Daily Check-in rollup (${start} to ${end})\nSubmission: ${(rollup.submission_rate * 100).toFixed(1)}% (${rollup.submitted_count}/${rollup.expected_count})\nOn time: ${rollup.on_time_count} | Late: ${rollup.late_count} | Missing: ${rollup.missing_count}\nProof attached: ${(rollup.proof_attach_rate * 100).toFixed(1)}% | Blocked tasks: ${rollup.blocked_task_count}`,
  },
}));
