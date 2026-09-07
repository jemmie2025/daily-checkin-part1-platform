# Generated task fragment for job "daily-checkin-open", task "n8n-open".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-n8n-open"
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
    {{ with secret "kv/data/n8n/mattermost/checkin/dialog-shared" }}
    CHECKIN_DIALOG_STATE_SIGNING_KEY={{ .Data.data.state_signing_key | toJSON }}
    {{ end }}
    {{ with secret "kv/data/n8n/mattermost/checkin/open" }}
    CHECKIN_COMPLIANCE_SLA_READ_TOKEN={{ .Data.data.compliance_sla_read_token | toJSON }}
    CHECKIN_MATTERMOST_COMMAND_TOKEN={{ .Data.data.mattermost_command_token | toJSON }}
    CHECKIN_MATTERMOST_OPEN_BOT_TOKEN={{ .Data.data.mattermost_bot_token | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
