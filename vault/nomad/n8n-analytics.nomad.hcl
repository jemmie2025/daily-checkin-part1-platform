# Generated task fragment for job "daily-checkin-analytics", task "n8n-analytics".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-n8n-analytics"
  change_mode  = "restart"
  env          = false
  disable_file = true
}

identity {
  name = "vault_default"
  aud  = ["vault.io"]
  ttl  = "1h"
}

template {
  data = <<-EOT
    {{ with secret "kv/data/n8n/mattermost/checkin/analytics" }}
    CHECKIN_ANALYTICS_ROSTER_TOKEN={{ .Data.data.roster_read_token | toJSON }}
    CHECKIN_CLICKHOUSE_INGEST_KEY={{ .Data.data.clickhouse_ingest_key | toJSON }}
    CHECKIN_CLICKHOUSE_INGEST_USER={{ .Data.data.clickhouse_ingest_user | toJSON }}
    {{ end }}
    {{ with secret "kv/data/n8n/mattermost/checkin/event-shared" }}
    CHECKIN_EVENT_INGEST_TOKEN={{ .Data.data.event_ingest_token | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
