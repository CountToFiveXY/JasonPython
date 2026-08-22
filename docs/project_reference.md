# Project Reference

## Files

```text
.
├── main.py
├── infrastructure/
│   ├── __init__.py
│   └── clients.py
├── requirements.txt
├── README.md
├── scripts/
│   └── run_local.sh
├── assets/
│   └── metroidzm_map.jpg
├── routers/
│   ├── __init__.py
│   ├── url_shortening.py
│   ├── messages.py
│   ├── ranking.py
│   ├── health.py
│   ├── hello.py
│   └── greeting.py
├── temporal/
│   ├── __init__.py
│   ├── activities.py
│   ├── workflows.py
│   └── worker.py
└── docs/
    ├── how_to_run_server.md
    ├── depdency/
    │   ├── redis_reference.md
    │   └── temporal_reference.md
    ├── how_to_call_api.md
    ├── project_reference.md
    └── apis/
        ├── ranking.md
        ├── url_shortening.md
        ├── message.md
        ├── health.md
        └── temporal_workflow.md
```

## Endpoints

| Method | Path | Input | Description | Documentation |
| --- | --- | --- | --- | --- |
| `POST` | `/v1/shorten` | JSON `url` field | Creates a unique eight-character key for a URL. | [Guide](apis/url_shortening.md) |
| `GET` | `/{shortKey}` | Eight-character short key | Opens the stored URL in a new browser tab, with a current-tab fallback. | [Guide](apis/url_shortening.md) |
| `GET` | `/display` | None | Returns a JPEG image. | [Guide](apis/message.md) |
| `POST` | `/v1/ranking` | JSON `total`, `type`, and `car` fields | Renders a ranking PNG. | [Guide](apis/ranking.md) |
| `GET` | `/health` | None | Returns the application's health status. | [Guide](apis/health.md) |
| `POST` | `/workflows/hello` | None | Starts `HelloWorkflow` and returns its result. | [Guide](apis/temporal_workflow.md) |
| `POST` | `/workflows/greeting` | JSON `name` field | Starts `GreetingWorkflow` and returns its result. | [Guide](apis/temporal_workflow.md) |

## Implementation

The FastAPI application is defined in `main.py`. Each API is implemented in a
separate module under `routers/` and registered with `app.include_router()`.
Python's `secrets` module generates eight random letters and digits. Redis
stores each code-to-URL mapping with an atomic `SET ... NX` command so an
existing code cannot be overwritten.
`infrastructure/clients.py` manages the asynchronous Redis client for the FastAPI
lifespan. It also connects FastAPI to Temporal Server.
`temporal/worker.py` registers the workflows and activities that
process Temporal tasks.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8080/docs>
- OpenAPI schema: <http://127.0.0.1:8080/openapi.json>
