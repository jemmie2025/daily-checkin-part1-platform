# Generated task fragment for job "daily-checkin-dlq", task "n8n-dlq".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-n8n-dlq"
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
    {{ with secret "kv/data/n8n/mattermost/checkin/dlq" }}
    CHECKIN_BASEROW_DLQ_TOKEN={{ .Data.data.baserow_dlq_token | toJSON }}
    CHECKIN_MATTERMOST_DLQ_BOT_TOKEN={{ .Data.data.mattermost_bot_token | toJSON }}
    CHECKIN_N8N_EXECUTION_READ_TOKEN={{ .Data.data.n8n_execution_read_token | toJSON }}
    CHECKIN_REPLAY_TOKEN={{ .Data.data.replay_token | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
