# Project Reference

## Files

```text
.
├── main.py
├── requirements.txt
├── README.md
├── routers/
│   ├── __init__.py
│   ├── url_shortening.py
│   ├── messages.py
│   └── health.py
└── docs/
    ├── how_to_run_server.md
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
| `GET` | `/tinyUrl` | `url` query parameter | Generates a base-62 short code for a URL. | [Guide](apis/url_shortening.md) |
| `GET` | `/message` | None | Returns a fixed string. | [Guide](apis/message.md) |
| `GET` | `/health` | None | Returns the application's health status. | [Guide](apis/health.md) |

## Implementation

The FastAPI application is defined in `main.py`. Each API is implemented in a
separate module under `routers/` and registered with `app.include_router()`.
Python's standard-library `uuid4()` function supplies a unique integer, which
the URL shortening router converts to base 62. FastAPI serializes returned
dictionaries as JSON.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8080/docs>
- OpenAPI schema: <http://127.0.0.1:8080/openapi.json>
