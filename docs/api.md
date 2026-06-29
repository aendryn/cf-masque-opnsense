# API Documentation

All API endpoints require authentication (OPNsense session or API key). Base path: `/api/cloudflarezt/`.

## Service Controller

### Start all connections
`POST /api/cloudflarezt/service/start`

### Stop all connections
`POST /api/cloudflarezt/service/stop`

### Restart all connections
`POST /api/cloudflarezt/service/restart`

### Get overall status
`GET /api/cloudflarezt/service/status`

Response:
```json
"running (2/2 connections active)"
```

### Get per-connection status
`GET /api/cloudflarezt/service/allstatus`

Response:
```json
{
  "overall": "running",
  "connections": {
    "<uuid>": {
      "name": "Main WARP",
      "protocol": "warp_masque",
      "status": "connected",
      "pid": 1234,
      "client_ipv4": "100.96.0.5",
      "uptime": "1:23:45"
    }
  }
}
```

### Start a specific connection
`POST /api/cloudflarezt/service/startconn/<uuid>`

Response: `{"result": "ok", "pid": 1234}` or `{"result": "already_running", "pid": 1234}`

### Stop a specific connection
`POST /api/cloudflarezt/service/stopconn/<uuid>`

Response: `{"result": "ok"}` or `{"result": "not_running"}`

### Get connection status
`GET /api/cloudflarezt/service/connstatus/<uuid>`

Response:
```json
{
  "result": "ok",
  "uuid": "<uuid>",
  "name": "Main WARP",
  "protocol": "warp_masque",
  "status": "connected",
  "pid": 1234,
  "client_ipv4": "100.96.0.5",
  "client_ipv6": "fd01::5",
  "registration_status": "enrolled",
  "uptime": "1:23:45"
}
```

---

## Connection Controller

### List connections
`GET /api/cloudflarezt/connection/search`

Query params: `current` (page), `rowCount`, `searchPhrase`

Response: standard OPNsense grid response with `rows`, `rowCount`, `total`, `current`.

### Get connection
`GET /api/cloudflarezt/connection/getconn/<uuid>`

### Add connection
`POST /api/cloudflarezt/connection/addconn`

Body: connection fields (see model schema).

### Update connection
`POST /api/cloudflarezt/connection/setconn/<uuid>`

### Delete connection
`POST /api/cloudflarezt/connection/delconn/<uuid>`

### Register device
`POST /api/cloudflarezt/connection/register/<uuid>`

Optional body: `{"jwt": "<team-jwt>"}` for Zero Trust enrollment with browser auth.

Response:
```json
{
  "result": "ok",
  "device_id": "abc-123",
  "client_ipv4": "100.96.0.5",
  "client_ipv6": "fd01::5",
  "endpoint_v4": "162.159.198.1",
  "registration_status": "enrolled"
}
```

### Enroll MASQUE key
`POST /api/cloudflarezt/connection/enroll/<uuid>`

Re-enrolls a new ECDSA P-256 key for an already-registered device.

---

## Organization Controller

### List organizations
`GET /api/cloudflarezt/organization/search`

### Get organization
`GET /api/cloudflarezt/organization/getorg/<uuid>`

### Add organization
`POST /api/cloudflarezt/organization/addorg`

Body:
```json
{
  "organization": {
    "name": "Acme Corp",
    "account_id": "abc123",
    "team_name": "acme",
    "api_token": "secret-token-value"
  }
}
```

Note: `api_token` is intercepted and stored encrypted. It is never returned in GET responses.

### Update organization
`POST /api/cloudflarezt/organization/setorg/<uuid>`

### Delete organization
`POST /api/cloudflarezt/organization/delorg/<uuid>`

### Validate API token
`POST /api/cloudflarezt/organization/validatetoken/<uuid>`

Response: `{"result": "valid", "status": "active"}` or `{"result": "invalid", "message": "..."}`

---

## Wizard Controller

### Create org + connection + register in one step
`POST /api/cloudflarezt/wizard/setup`

Body:
```json
{
  "org_name": "Acme Corp",
  "account_id": "abc123",
  "team_name": "acme",
  "api_token": "secret",
  "protocol": "warp_masque",
  "connection_name": "Main WARP"
}
```

Response:
```json
{
  "result": "ok",
  "org_uuid": "<uuid>",
  "conn_uuid": "<uuid>",
  "registration": { "result": "ok", "client_ipv4": "100.96.0.5" }
}
```

---

## Diagnostics Controller

### Run diagnostics
`GET /api/cloudflarezt/diagnostics/run/<uuid>`

Use `all` as uuid to run for all connections.

Response: full diagnostics object including process status, registered IPs, interface stats, routes, and connectivity probes.

### Ping Cloudflare endpoints
`POST /api/cloudflarezt/diagnostics/ping`

Response:
```json
{
  "result": "ok",
  "probes": [
    {"target": "162.159.198.1:443/udp", "description": "MASQUE QUIC primary", "reachable": true, "latency_ms": 12.3},
    {"target": "162.159.198.2:443/tcp", "description": "MASQUE HTTP/2 fallback", "reachable": true, "latency_ms": 8.1}
  ]
}
```

### Get logs
`GET /api/cloudflarezt/diagnostics/logs/<uuid>?lines=100`

### Get statistics
`GET /api/cloudflarezt/diagnostics/stats/<uuid>`

---

## Error Responses

All endpoints return `{"result": "failed", "message": "..."}` on error. HTTP status codes follow OPNsense conventions (200 for API-level errors, 4xx for auth/routing failures).

---

## Authentication

Use OPNsense API keys: `Authorization: Basic base64(key:secret)`, or log in via the web UI and use the session cookie.

API keys are created at **System → Access → Users → Edit → API Keys**.
