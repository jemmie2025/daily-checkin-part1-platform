# Generated task fragment for job "daily-checkin-submit", task "n8n-submit".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-n8n-submit"
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
    {{ with secret "kv/data/n8n/mattermost/checkin/event-shared" }}
    CHECKIN_EVENT_INGEST_TOKEN={{ .Data.data.event_ingest_token | toJSON }}
    {{ end }}
    {{ with secret "kv/data/n8n/mattermost/checkin/submit" }}
    CHECKIN_BASEROW_CHECKINS_TOKEN={{ .Data.data.baserow_checkins_token | toJSON }}
    CHECKIN_MATTERMOST_SUBMIT_BOT_TOKEN={{ .Data.data.mattermost_bot_token | toJSON }}
    CHECKIN_MATTERMOST_SUBMIT_SIGNATURE={{ .Data.data.mattermost_submit_signature | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
