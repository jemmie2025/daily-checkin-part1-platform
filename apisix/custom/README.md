# Custom Plugin Installation

The `checkin-context` plugin performs the body parsing required to establish a
stable per-user APISIX rate-limit key for both Mattermost payload formats.

Install the directory so APISIX resolves:

```text
/opt/daily-checkin/apisix/plugins/checkin-context.lua
```

Merge the following path setting into the installed APISIX `conf/config.yaml`:

```yaml
apisix:
  extra_lua_path: "/opt/daily-checkin/?.lua;;"
```

The operator must then append `checkin-context` to the deployment's complete
existing `plugins:` list. A deliberately incomplete plugin-list snippet is not
provided here: defining `plugins:` replaces the defaults and could disable
required built-ins. Roll through a staging/canary instance before production.

The plugin priority is `2999`: immediately after `ip-restriction` (`3000`) and
before `limit-count`. Confirm there is no priority collision through the APISIX
Control API `/v1/schema` before rollout.
