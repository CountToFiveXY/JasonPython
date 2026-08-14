# Project Reference

## Files

```text
.
├── main.py
├── database.py
├── requirements.txt
├── README.md
├── assets/
│   └── metroidzm_map.jpg
├── routers/
│   ├── __init__.py
│   ├── url_shortening.py
│   ├── messages.py
│   └── health.py
└── docs/
    ├── how_to_run_server.md
    ├── how_to_run_redis.md
    ├── how_to_call_api.md
    ├── project_reference.md
    └── apis/
        ├── url_shortening.md
        ├── message.md
        └── health.md
```

## Endpoints

| Method | Path | Input | Description | Documentation |
| --- | --- | --- | --- | --- |
| `GET` | `/tinyUrl` | `url` query parameter | Stores a URL in Redis and returns a base-62 short code. | [Guide](apis/url_shortening.md) |
| `GET` | `/go/{code}` | Path parameter | Redirects to a URL stored in Redis. | [Guide](apis/url_shortening.md) |
| `GET` | `/display` | None | Returns a JPEG image. | [Guide](apis/message.md) |
| `GET` | `/health` | None | Returns the application's health status. | [Guide](apis/health.md) |

## Implementation

The FastAPI application is defined in `main.py`. Each API is implemented in a
separate module under `routers/` and registered with `app.include_router()`.
Python's standard-library `uuid4()` function supplies a unique integer, which
the URL shortening router converts to base 62 and stores mappings in Redis.
`database.py` manages the asynchronous Redis client for the FastAPI lifespan.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8080/docs>
- OpenAPI schema: <http://127.0.0.1:8080/openapi.json>
