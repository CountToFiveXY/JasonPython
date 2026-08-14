# Project Reference

## Files

```text
.
├── main.py
├── requirements.txt
├── README.md
└── docs/
    ├── how_to_run_server.md
    ├── how_to_call_api.md
    └── project_reference.md
```

## Endpoint

| Method | Path | Input | Description |
| --- | --- | --- | --- |
| `GET` | `/` | `text` query parameter | Appends a new UUID to the supplied text. |

## Implementation

The application is defined in `main.py`. Python's standard-library `uuid4()`
function generates the UUID, and FastAPI serializes the returned dictionary as
JSON.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8080/docs>
- OpenAPI schema: <http://127.0.0.1:8080/openapi.json>
