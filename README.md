# Utility APIs

A small FastAPI project containing three endpoints: a URL short-code generator,
an image response, and a health check.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

See [How to call the API](docs/how_to_call_api.md) for request and response
examples.

## Documentation

- [How to run the server](docs/how_to_run_server.md)
- [How to run Redis](docs/how_to_run_redis.md)
- [How to run Temporal](docs/how_to_run_temporal.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)
