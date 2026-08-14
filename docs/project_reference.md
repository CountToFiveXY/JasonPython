# Project Reference

## Files

```text
.
├── main.py
├── requirements.txt
├── README.md
├── routers/
│   ├── __init__.py
│   ├── uuid_messages.py
│   ├── messages.py
│   └── health.py
└── docs/
    ├── how_to_run_server.md
    ├── how_to_call_api.md
    └── project_reference.md
```

## Endpoints

| Method | Path | Input | Description |
| --- | --- | --- | --- |
| `GET` | `/` | `text` query parameter | Appends a new UUID to the supplied text. |
| `GET` | `/message` | None | Returns a fixed string. |
| `GET` | `/health` | None | Returns the application's health status. |

## Implementation

The FastAPI application is defined in `main.py`. Each API is implemented in a
separate module under `routers/` and registered with `app.include_router()`.
Python's standard-library `uuid4()` function generates UUID values, and
FastAPI serializes returned dictionaries as JSON.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8080/docs>
- OpenAPI schema: <http://127.0.0.1:8080/openapi.json>
