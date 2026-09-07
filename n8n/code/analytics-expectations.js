const input = $input.first().json;
const rows = input.expectations ?? input.results ?? [];
const allowedStates = new Set(['expected', 'approved_leave', 'holiday', 'inactive']);
const allowedTypes = new Set(['SOD', 'EOD']);
const now = new Date().toISOString();
return rows.map((row) => {
  if (!allowedStates.has(row.attendance_state) || !allowedTypes.has(row.checkin_type)) {
    throw new Error('invalid expectation contract');
  }
  for (const field of ['expectation_id', 'user_id', 'pod_id', 'timezone', 'cycle_date', 'sla_code', 'sla_due_at', 'roster_source_version']) {
    if (!row[field]) throw new Error(`expectation missing ${field}`);
  }
  return {
    json: {
      expectation_id: row.expectation_id,
      user_id: row.user_id,
      pod_id: row.pod_id,
      timezone: row.timezone,
      cycle_date: row.cycle_date,
      checkin_type: row.checkin_type,
      sla_code: row.sla_code,
      sla_due_at: row.sla_due_at,
      attendance_state: row.attendance_state,
      roster_source_version: row.roster_source_version,
      updated_at: now,
    },
  };
});
