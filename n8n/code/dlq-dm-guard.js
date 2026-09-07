const stored = $input.first().json;
const built = $('Build DLQ Record').item.json;
const row = Array.isArray(stored.results) ? stored.results[0] : stored;
if (!row?.id) throw new Error('DLQ row identity is missing after upsert');
if (row.dm_notified_at) return [];
return [{ json: { ...built, row_id: row.id } }];
