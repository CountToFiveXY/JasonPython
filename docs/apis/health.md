# Health Check API

Reports whether the application is running.

## Request

```text
GET /health
```

### curl

```bash
curl http://127.0.0.1:8080/health
```

## Response

```json
{"status": "OK", "redis": "connected"}
```

This endpoint does not require any parameters. It returns `503 Service
Unavailable` when FastAPI cannot reach Redis.
