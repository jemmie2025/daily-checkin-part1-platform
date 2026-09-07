-- Licensed for the Task #5585 Daily Check-in implementation.
-- Extracts a bounded Mattermost user key after the source-IP plugin runs.

local core = require("apisix.core")

local plugin_name = "checkin-context"

local schema = {
    type = "object",
    additionalProperties = false,
    properties = {
        payload_type = {
            type = "string",
            enum = {"open", "submit"},
        },
        max_body_size = {
            type = "integer",
            minimum = 1,
            maximum = 65536,
        },
        user_header = {
            type = "string",
            default = "X-Checkin-User-Id",
        },
        correlation_header = {
            type = "string",
            default = "X-Checkin-Correlation-Id",
        },
    },
    required = {"payload_type", "max_body_size"},
}

local _M = {
    version = 0.1,
    priority = 2999,
    name = plugin_name,
    schema = schema,
}

local internal_response_headers = {
    "X-Checkin-Outcome",
    "X-Checkin-User-Id",
    "X-Checkin-Pod-Id",
    "X-Checkin-Cycle-Date",
    "X-Checkin-Type",
    "X-Checkin-Sla-Code",
    "X-Checkin-Gateway-Verified",
}

local function failure(status, code)
    return status, {
        error = code,
    }
end

local function normalized_content_type(headers)
    local value = headers["content-type"] or headers["Content-Type"] or ""
    return string.lower(string.match(value, "^[^;]+") or "")
end

local function read_bounded_body(max_body_size)
    local content_length = tonumber(ngx.var.http_content_length)
    if content_length and content_length > max_body_size then
        return nil, "payload_too_large"
    end

    ngx.req.read_body()
    local body = ngx.req.get_body_data()

    if not body then
        local body_file = ngx.req.get_body_file()
        if body_file then
            local handle = io.open(body_file, "rb")
            if not handle then
                return nil, "payload_unavailable"
            end
            body = handle:read(max_body_size + 1)
            handle:close()
        end
    end

    if not body or body == "" then
        return nil, "payload_required"
    end
    if #body > max_body_size then
        return nil, "payload_too_large"
    end
    return body, nil
end

local function form_user_id()
    local args, err = ngx.req.get_post_args(100)
    if err == "truncated" then
        return nil, "too_many_form_fields"
    end
    if not args then
        return nil, "invalid_form_payload"
    end
    return args.user_id, nil
end

local function json_user_id(body)
    local payload, err = core.json.decode(body)
    if not payload then
        return nil, err or "invalid_json_payload"
    end
    return payload.user_id, nil
end

local function valid_identifier(value)
    if type(value) ~= "string" or #value < 1 or #value > 128 then
        return false
    end
    return string.match(value, "^[A-Za-z0-9_-]+$") ~= nil
end

function _M.check_schema(conf)
    return core.schema.check(schema, conf)
end

function _M.access(conf, ctx)
    local body, body_err = read_bounded_body(conf.max_body_size)
    if body_err == "payload_too_large" then
        return failure(413, body_err)
    end
    if body_err then
        return failure(400, body_err)
    end

    local headers = ngx.req.get_headers(100)
    local content_type = normalized_content_type(headers)
    local user_id
    local parse_err

    if conf.payload_type == "open" then
        if content_type ~= "application/x-www-form-urlencoded" then
            return failure(415, "open_content_type_not_supported")
        end
        user_id, parse_err = form_user_id()
    else
        if content_type ~= "application/json" then
            return failure(415, "submit_content_type_not_supported")
        end
        user_id, parse_err = json_user_id(body)
    end

    if parse_err or not valid_identifier(user_id) then
        return failure(400, "invalid_user_id")
    end

    local user_header = conf.user_header or "X-Checkin-User-Id"
    local correlation_header = conf.correlation_header or "X-Checkin-Correlation-Id"
    local correlation_id = headers[string.lower(correlation_header)] or headers[correlation_header]

    if not valid_identifier(correlation_id) then
        return failure(500, "gateway_correlation_unavailable")
    end

    ngx.req.clear_header(user_header)
    ngx.req.clear_header("X-Checkin-Gateway-Verified")
    ngx.req.set_header(user_header, user_id)
    ngx.req.set_header(correlation_header, correlation_id)
    ngx.req.set_header("X-Checkin-Gateway-Verified", "1")

    ctx.checkin_user_id = user_id
    ctx.checkin_correlation_id = correlation_id
end

function _M.header_filter(conf, ctx)
    for _, header_name in ipairs(internal_response_headers) do
        ngx.header[header_name] = nil
    end
end

return _M
