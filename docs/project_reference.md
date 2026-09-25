# Project Reference

## Files

```text
.
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── dependencies.py
│   ├── entity/
│   │   ├── __init__.py
│   │   ├── leaderboard.py
│   │   ├── order.py
│   │   └── ranking.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── cache_watcher.py
│   │   └── clients.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── hello.py
│   │   ├── leaderboard.py
│   │   ├── messages.py
│   │   ├── order.py
│   │   ├── ranking.py
│   │   └── url_shortening.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── hello.py
│   │   ├── image.py
│   │   ├── leaderboard.py
│   │   ├── messages.py
│   │   ├── order.py
│   │   ├── ranking.py
│   │   └── url_shortening.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── url_shortening.py
│   │   ├── image.py
│   │   ├── leaderboard.py
│   │   ├── messages.py
│   │   ├── ranking.py
│   │   ├── health.py
│   │   ├── hello.py
│   │   └── order.py
│   ├── temporal/
│   │   ├── __init__.py
│   │   ├── worker.py
│   │   ├── activities/
│   │   │   ├── __init__.py
│   │   │   ├── firestore.py
│   │   │   ├── greeting.py
│   │   │   ├── hello.py
│   │   │   └── order.py
│   │   └── workflows/
│   │       ├── __init__.py
│   │       ├── greeting.py
│   │       ├── hello.py
│   │       └── order.py
│   └── messaging/
│       ├── __init__.py
│       ├── config.py
│       ├── events.py
│       └── worker.py
├── requirements.txt
├── README.md
├── scripts/
│   └── run_local.sh
├── assets/
│   └── metroidzm_map.jpg
└── docs/
    ├── how_to_run_server.md
    ├── depdency/
    │   ├── redis_reference.md
    │   ├── temporal_reference.md
    │   ├── firestore_reference.md
    │   └── kafka_reference.md
    ├── how_to_call_api.md
    ├── project_reference.md
    └── apis/
        ├── leaderboard.md
        ├── ranking.md
        ├── order.md
        ├── messages.md
        ├── url_shortening.md
        ├── image.md
        ├── health.md
        └── hello.md
```

## Endpoints

| Method | Path | Input | Description | Documentation |
| --- | --- | --- | --- | --- |
| `POST` | `/v1/shorten` | JSON `url` field | Creates a unique eight-character key for a URL. | [Guide](apis/url_shortening.md) |
| `GET` | `/go/{shortKey}` | Eight-character short key | Opens the stored URL in a new browser tab, with a current-tab fallback. | [Guide](apis/url_shortening.md) |
| `GET` | `/display` | None | Returns a JPEG image. | [Guide](apis/image.md) |
| `POST` | `/v1/ranking` | JSON `total`, `type`, and `car` fields | Renders a ranking PNG. | [Guide](apis/ranking.md) |
| `GET` | `/v1/ranking/leaderboards` | None | Loads normalized event leaderboards from Galaxy Lens. | [Guide](apis/ranking.md) |
| `GET` | `/health` | None | Returns the application's health status. | [Guide](apis/health.md) |
| `POST` | `/workflows/hello` | None | Starts `HelloWorkflow` and returns its result. | [Guide](apis/hello.md) |
| `POST` | `/v1/order` | JSON `user_id` field | Creates an order and starts a signal-waiting `OrderWorkflow`. | [Guide](apis/order.md) |
| `POST` | `/v1/messages` | JSON `id` and `status` fields | Publishes an order status for the Kafka worker. | [Guide](apis/messages.md) |
| `GET` | `/v1/leaderboard/maps` | None | Lists the maps, ordered by name. | [Guide](apis/leaderboard.md) |
| `GET` | `/v1/leaderboard/cars` | None | Lists every car holding a time, for the car selector. | [Guide](apis/leaderboard.md) |
| `POST` | `/v1/leaderboard/maps` | JSON `name` and two `tracks` names | Creates a map and its fixed pair of tracks. | [Guide](apis/leaderboard.md) |
| `GET` | `/v1/leaderboard/maps/{map_id}` | Map identifier | Returns every recorded time on each track, fastest first. | [Guide](apis/leaderboard.md) |
| `GET` | `/v1/leaderboard/tracks` | None | Lists every track with its map, for a selector. | [Guide](apis/leaderboard.md) |
| `POST` | `/v1/leaderboard/tracks/lookup` | JSON `names` list | Returns the leaderboards for named tracks, across maps. | [Guide](apis/leaderboard.md) |
| `PUT` | `/v1/leaderboard/maps/{map_id}/tracks/{track_id}/times` | JSON `car` and `seconds` fields | Replaces a car's time on a track. | [Guide](apis/leaderboard.md) |
| `DELETE` | `/v1/leaderboard/maps/{map_id}/tracks/{track_id}/times/{car}` | Map, track, and car | Removes a car's time from a track. | [Guide](apis/leaderboard.md) |
| `POST` | `/v1/text-recognition` | Image bytes as the body | Reads the words out of an image. | [Guide](apis/text_recognition.md) |

## Implementation

The FastAPI application is defined in `src/main.py`. Each API is implemented in
a separate module under `src/routers/` and registered with `app.include_router()`.
Persistent domain models live under `src/entity/`. HTTP request and response
schemas live under `src/schemas/`, messaging contracts remain under
`src/messaging/`, and Temporal input models remain beside their consumers.
Application use cases live under `src/services/`; routers receive these services
through providers in `src/dependencies.py` rather than depending directly on
infrastructure clients. Routers are responsible for HTTP validation, response
formatting, and translating service errors into HTTP status codes.
Python's `secrets` module generates eight random letters and digits. Redis
stores each code-to-URL mapping with an atomic `SET ... NX` command so an
existing code cannot be overwritten.
`src/infrastructure/clients.py` manages the asynchronous Redis and Kafka clients for
the FastAPI lifespan. It also connects FastAPI to Temporal Server and Firestore,
and starts `src/infrastructure/cache_watcher.py`, which listens to Firestore and
clears cached leaderboard reads when their documents change.
`src/temporal/worker.py` registers the capability-specific workflows and
activities under `src/temporal/workflows/` and `src/temporal/activities/`.
`src/messaging/worker.py` consumes Kafka status events and signals the matching
order workflow. The leaderboard API is the one feature that reads and writes
Firestore directly from a request: `LeaderboardService` receives the client
from `get_firestore` and runs the blocking Firestore calls on worker threads.

## Interactive API documentation

While the server is running, FastAPI provides:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>
