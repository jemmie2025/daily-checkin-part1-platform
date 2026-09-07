const crypto = require('crypto');
const input = $input.first().json;
const now = new Date(input.now ?? new Date().toISOString());
if (Number.isNaN(now.getTime())) throw new Error('now must be RFC3339');

const expectations = input.expectations ?? [];
const checkins = input.checkins ?? [];
const violations = input.violations ?? [];
const state = $getWorkflowStaticData('global');
const existingActionIds = new Set([...(input.existing_action_ids ?? []), ...(state.action_ids ?? [])]);
const nudgeBeforeMs = 60 * 60 * 1000;
const escalationAfterMs = 24 * 60 * 60 * 1000;

const digest = (...parts) => crypto.createHash('sha256').update(parts.join('|')).digest('hex').slice(0, 32);
const checkinKey = (row) => [row.user_id, row.cycle_date, row.checkin_type].join('|');
const accepted = new Map(checkins.map((row) => [checkinKey(row), row]));
const violationByKey = new Map(
  violations.filter((row) => row.rule_id === 'PI-6').map((row) => [checkinKey(row), row]),
);
const actions = [];
const escalations = new Map();

for (const expectation of expectations) {
  if (expectation.attendance_state !== 'expected') continue;
  const key = checkinKey(expectation);
  const dueAt = new Date(expectation.sla_due_at);
  if (Number.isNaN(dueAt.getTime())) throw new Error('sla_due_at must be RFC3339');
  const acceptedRow = accepted.get(key);
  const existingViolation = violationByKey.get(key);

  if (acceptedRow) {
    if (existingViolation?.status === 'open') {
      const checkinId = acceptedRow.checkin_id ?? key;
      const actionId = `resolve_${digest(existingViolation.violation_id, checkinId)}`;
      if (!existingActionIds.has(actionId)) {
        actions.push({
          action_id: actionId,
          action_type: 'resolve_violation',
          violation_id: existingViolation.violation_id,
          baserow_row_id: existingViolation.id,
          resolved_at: now.toISOString(),
          resolved_by_checkin_id: checkinId,
        });
      }
    }
    continue;
  }

  const nudgeId = `nudge_${digest(expectation.expectation_id)}`;
  if (now >= new Date(dueAt.getTime() - nudgeBeforeMs) && now < dueAt && !existingActionIds.has(nudgeId)) {
    actions.push({
      action_id: nudgeId,
      action_type: 'nudge',
      channel_id: expectation.mattermost_dm_channel_id,
      message: `⏰ Daily Check-in reminder: your ${expectation.checkin_type} update is due at ${expectation.sla_due_at}. Use /ci to submit it.`,
    });
  }

  if (expectation.checkin_type !== 'EOD' || now < dueAt) continue;
  const violationId = `viol_${digest(expectation.user_id, expectation.cycle_date, 'EOD', 'PI-6')}`;
  const record = existingViolation ?? {
    violation_id: violationId,
    rule_id: 'PI-6',
    rule_name: 'EOD status update not submitted',
    user_id: expectation.user_id,
    user_name: expectation.user_name,
    pod_id: expectation.pod_id,
    cycle_date: expectation.cycle_date,
    checkin_type: 'EOD',
    sla_code: expectation.sla_code,
    sla_due_at: expectation.sla_due_at,
    detected_at: now.toISOString(),
    status: 'open',
    evidence_json: JSON.stringify({
      accepted_checkin_found: false,
      expected: true,
      expectation_id: expectation.expectation_id,
      roster_source_version: expectation.roster_source_version,
    }),
    workflow_execution_id: $execution.id,
    resolved_at: null,
    resolved_by_checkin_id: null,
    waiver_reason: null,
  };
  const actionId = `upsert_${violationId}`;
  if (!existingViolation && !existingActionIds.has(actionId)) {
    actions.push({ action_id: actionId, action_type: 'upsert_violation', record });
  }
  if (now >= new Date(dueAt.getTime() + escalationAfterMs) && record.status === 'open') {
    const group = [expectation.pod_id, expectation.cycle_date, expectation.checkin_type].join('|');
    if (!escalations.has(group)) escalations.set(group, []);
    escalations.get(group).push({ record, expectation });
  }
}

for (const [group, rows] of [...escalations.entries()].sort()) {
  const [podId, cycleDate, checkinType] = group.split('|');
  const actionId = `esc_${digest(podId, cycleDate, checkinType)}`;
  if (existingActionIds.has(actionId)) continue;
  const names = rows.map((row) => row.expectation.user_name).sort();
  actions.push({
    action_id: actionId,
    action_type: 'escalation_digest',
    channel_id: rows[0].expectation.pod_lead_channel_id,
    message: `🚨 Daily Check-in SLA digest — ${cycleDate} ${checkinType}\nMissing (${names.length}): ${names.join(', ')}`,
    violation_ids: rows.map((row) => row.record.violation_id).sort(),
  });
}

return actions.map((action) => ({ json: action }));
