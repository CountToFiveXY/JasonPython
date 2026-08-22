# Utility APIs

A small FastAPI project containing three endpoints: a URL short-code generator,
an image response, and a health check.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

Start with [How to run the server](docs/how_to_run_server.md). It covers the
complete local environment: Redis, Temporal Server, the Temporal worker, and
FastAPI.

First-time setup:

```bash
brew install redis temporal  # Install the local Redis and Temporal services.
python3 -m venv .venv  # Create the project's Python environment.
source .venv/bin/activate  # Activate the Python environment in this terminal.
python -m pip install -r requirements.txt  # Install the Python dependencies.
```

Then start the complete local environment with:

```bash
./scripts/run_local.sh  # Start every local service required by the application.
```

## Documentation

- [How to run the server](docs/how_to_run_server.md) — start here
- [Redis reference](docs/depdency/redis_reference.md)
- [Temporal reference](docs/depdency/temporal_reference.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)
