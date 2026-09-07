const source = $('Guard Duplicate DM').item.json;
return [{
  json: {
    row_id: source.row_id,
    dlq_id: source.record.dlq_id,
    dm_notified_at: new Date().toISOString(),
  },
}];
