# Utility APIs

A small FastAPI project containing utility APIs for URL shortening, image
responses (including a generated participant card), a lap-time leaderboard,
health checks, and Temporal workflows. The order API starts a workflow with the order ID, and that workflow
persists the order to Cloud Firestore through a reusable activity. It then waits
up to one hour for a success event published to Kafka before running its
completion activity.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

Start with [How to run the server](docs/how_to_run_server.md) for installation
and local startup instructions.

## Documentation

- [How to run the server](docs/how_to_run_server.md) — start here
- [Redis reference](docs/depdency/redis_reference.md)
- [Temporal reference](docs/depdency/temporal_reference.md)
- [Firestore reference](docs/depdency/firestore_reference.md)
- [Kafka reference](docs/depdency/kafka_reference.md)
- [Leaderboard API](docs/apis/leaderboard.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)
