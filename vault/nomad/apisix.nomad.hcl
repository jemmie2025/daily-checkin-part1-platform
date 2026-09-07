# Generated task fragment for job "daily-checkin-gateway", task "apisix".
# Merge only into that dedicated task; do not place at group or job scope.

vault {
  cluster      = "default"
  role         = "daily-checkin-apisix"
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
    {{ with secret "kv/data/n8n/mattermost/checkin/apisix" }}
    CHECKIN_REDIS_PASSWORD={{ .Data.data.redis_password | toJSON }}
    CHECKIN_TELEMETRY_AUTH_HEADER={{ .Data.data.telemetry_auth_header | toJSON }}
    {{ end }}
  EOT

  destination          = "secrets/daily-checkin.env"
  perms                = "0400"
  env                  = true
  error_on_missing_key = true
  change_mode          = "restart"
  splay                = "30s"
}
