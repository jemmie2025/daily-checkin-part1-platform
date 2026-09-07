# Generated task fragment for job "daily-checkin-compliance", task "n8n-compliance".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-n8n-compliance"
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
    {{ with secret "kv/data/n8n/mattermost/checkin/compliance" }}
    CHECKIN_BASEROW_VIOLATIONS_TOKEN={{ .Data.data.baserow_violations_token | toJSON }}
    CHECKIN_CALENDAR_READ_TOKEN={{ .Data.data.calendar_read_token | toJSON }}
    CHECKIN_MATTERMOST_COMPLIANCE_BOT_TOKEN={{ .Data.data.mattermost_bot_token | toJSON }}
    CHECKIN_ROSTER_READ_TOKEN={{ .Data.data.roster_read_token | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
