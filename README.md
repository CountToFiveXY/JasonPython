# Utility APIs

A small FastAPI project containing three endpoints: a URL short-code generator,
an image response, and a health check.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

Start with [How to run the server](docs/how_to_run_server.md). It covers the
complete local environment: Redis, Temporal Server, the Temporal worker, and
FastAPI.

## Documentation

- [How to run the server](docs/how_to_run_server.md) — start here
- [Redis reference](docs/depdency/redis_reference.md)
- [Temporal reference](docs/depdency/temporal_reference.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)
