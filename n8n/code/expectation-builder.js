const input = $input.first().json;
const cycleDate = input.cycle_date;
const roster = input.roster ?? [];
const slaRules = input.sla_rules ?? [];
const leaveRecords = input.leave_records ?? [];
const holidays = input.holidays ?? [];

function validDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  if (!match) return false;
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return parsed.getUTCFullYear() === Number(match[1])
    && parsed.getUTCMonth() === Number(match[2]) - 1
    && parsed.getUTCDate() === Number(match[3]);
}
if (!validDate(cycleDate)) throw new Error('cycle_date must be a real YYYY-MM-DD date');
if (typeof input.roster_source_version !== 'string' || !input.roster_source_version.length
  || input.roster_source_version.length > 128) {
  throw new Error('roster_source_version is invalid');
}
for (const [name, value] of Object.entries({ roster, slaRules, leaveRecords, holidays })) {
  if (!Array.isArray(value)) throw new Error(`${name} must be an array`);
}

function zonedTimeToUtc(dateText, timeText, timeZone) {
  const [year, month, day] = dateText.split('-').map(Number);
  const [hour, minute] = timeText.split(':').map(Number);
  if (![year, month, day, hour, minute].every(Number.isInteger) || hour > 23 || minute > 59) {
    throw new Error('local_due_time must use HH:MM');
  }
  const target = Date.UTC(year, month - 1, day, hour, minute, 0);
  let guess = target;
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  });
  for (let pass = 0; pass < 3; pass += 1) {
    const parts = Object.fromEntries(
      formatter.formatToParts(new Date(guess)).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
    );
    const represented = Date.UTC(
      Number(parts.year),
      Number(parts.month) - 1,
      Number(parts.day),
      Number(parts.hour),
      Number(parts.minute),
      Number(parts.second),
    );
    guess += target - represented;
  }
  const finalParts = Object.fromEntries(
    formatter.formatToParts(new Date(guess)).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  );
  const roundTrip = Date.UTC(
    Number(finalParts.year),
    Number(finalParts.month) - 1,
    Number(finalParts.day),
    Number(finalParts.hour),
    Number(finalParts.minute),
    Number(finalParts.second),
  );
  if (roundTrip !== target) throw new Error('local due time does not exist in timezone');
  return new Date(guess).toISOString().replace('.000Z', 'Z');
}

function between(day, start, end) {
  return day >= start && day <= end;
}

function attendanceState(member) {
  const activeFrom = member.active_from ?? '1900-01-01';
  const activeUntil = member.active_until ?? '9999-12-31';
  if (!validDate(activeFrom) || !validDate(activeUntil) || activeFrom > activeUntil) {
    throw new Error('roster active dates are invalid');
  }
  if (member.active === false || !between(cycleDate, activeFrom, activeUntil)) return 'inactive';
  if (leaveRecords.some((record) => (
    record.user_id === member.user_id
    && record.status === 'approved'
    && between(cycleDate, record.start_date, record.end_date)
  ))) return 'approved_leave';
  if (holidays.some((holiday) => (
    holiday.date === cycleDate
    && (holiday.scope === 'global' || (holiday.scope === 'pod' && holiday.pod_id === member.pod_id))
  ))) return 'holiday';
  return 'expected';
}

for (const record of leaveRecords) {
  if (typeof record.user_id !== 'string' || !record.user_id.length
    || !['approved', 'requested', 'rejected', 'cancelled'].includes(record.status)
    || !validDate(record.start_date) || !validDate(record.end_date)
    || record.start_date > record.end_date) {
    throw new Error('leave record is invalid');
  }
}
for (const holiday of holidays) {
  if (!validDate(holiday.date) || !['global', 'pod'].includes(holiday.scope)
    || (holiday.scope === 'pod' && (typeof holiday.pod_id !== 'string' || !holiday.pod_id.length))) {
    throw new Error('holiday record is invalid');
  }
}

const seen = new Set();
const expectationIds = new Set();
const expectations = [];
for (const member of roster) {
  for (const field of ['user_id', 'user_name', 'pod_id', 'timezone', 'mattermost_dm_channel_id', 'pod_lead_channel_id']) {
    if (typeof member[field] !== 'string' || !member[field].length) throw new Error(`roster member missing ${field}`);
  }
  if (typeof member.active !== 'boolean') throw new Error('roster member active must be boolean');
  if (seen.has(member.user_id)) throw new Error('duplicate roster user_id');
  seen.add(member.user_id);
  const state = attendanceState(member);
  for (const rule of slaRules) {
    if (!['SOD', 'EOD'].includes(rule.checkin_type)) throw new Error('invalid SLA checkin_type');
    if (rule.pod_id && rule.pod_id !== member.pod_id) continue;
    if (typeof rule.sla_code !== 'string' || !rule.sla_code.length || rule.sla_code.length > 128) {
      throw new Error('invalid SLA code');
    }
    if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(rule.local_due_time ?? '')) {
      throw new Error('local_due_time must use HH:MM');
    }
    const expectationId = [member.user_id, cycleDate, rule.checkin_type, rule.sla_code].join('|');
    if (expectationIds.has(expectationId)) throw new Error('duplicate SLA expectation');
    expectationIds.add(expectationId);
    expectations.push({
      expectation_id: expectationId,
      user_id: member.user_id,
      user_name: member.user_name,
      mattermost_dm_channel_id: member.mattermost_dm_channel_id,
      pod_id: member.pod_id,
      pod_lead_channel_id: member.pod_lead_channel_id,
      timezone: member.timezone,
      cycle_date: cycleDate,
      checkin_type: rule.checkin_type,
      sla_code: rule.sla_code,
      sla_due_at: zonedTimeToUtc(cycleDate, rule.local_due_time, member.timezone),
      attendance_state: state,
      roster_source_version: input.roster_source_version,
    });
  }
}

expectations.sort((left, right) => left.expectation_id.localeCompare(right.expectation_id));
return [{ json: { ...input, expectations } }];
