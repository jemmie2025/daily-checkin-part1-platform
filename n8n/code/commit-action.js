const input = $input.first().json;
const action = $('Plan Compliance Actions').item.json;
const state = $getWorkflowStaticData('global');
const current = new Set(state.action_ids ?? []);
current.add(action.action_id);
state.action_ids = [...current].sort().slice(-10000);
return [{ json: { action_id: action.action_id, status: 'committed', downstream: input } }];
