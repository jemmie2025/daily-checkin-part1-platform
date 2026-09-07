const existing = $input.first().json;
const incoming = $('Validate and Flatten Event').item.json.incoming;
const rows = existing.data ?? existing.rows ?? existing;
const first = Array.isArray(rows) ? rows[0] : null;
if (!first) return [{ json: { disposition: 'new', incoming } }];
if (first.payload_hash !== incoming.payload_hash) {
  return [{ json: { disposition: 'conflict', event_id: incoming.event_id } }];
}
return [{ json: { disposition: 'duplicate', event_id: incoming.event_id } }];
