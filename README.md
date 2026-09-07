# Utility APIs

A small FastAPI project containing utility APIs for URL shortening, image
responses (including a generated participant card), health checks, and Temporal
workflows. The order API persists orders to Cloud Firestore before starting a
workflow with the same ID.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

Start with [How to run the server](docs/how_to_run_server.md) for installation
and local startup instructions.

## Documentation

- [How to run the server](docs/how_to_run_server.md) — start here
- [Redis reference](docs/depdency/redis_reference.md)
- [Temporal reference](docs/depdency/temporal_reference.md)
- [Firestore reference](docs/depdency/firestore_reference.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)
