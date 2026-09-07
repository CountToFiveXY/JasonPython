# Temporal Workflow API

Starts the `HelloWorkflow` through FastAPI. Temporal records the workflow's
event history, and the Temporal worker executes an activity that prints
`Hello there` in the worker terminal.

Redis, Temporal Server, the Temporal worker, and FastAPI must be running. See
[How to run the server](../how_to_run_server.md) for the one-command startup.

## Request

```text
POST /workflows/hello
```

The request does not require a body or query parameters.

### curl

```bash
curl -X POST http://127.0.0.1:8000/workflows/hello
```

## Response

```json
{
  "workflow_id": "hello-7de7d320-4418-40be-bbd1-c856f1a67e83",
  "result": "Hello there"
}
```

The API generates a unique workflow ID, starts `HelloWorkflow` on the
`utility-api` task queue, waits for it to finish, and returns its result.

The worker terminal prints:

```text
Hello there
```

Open <http://127.0.0.1:8233> and search for the returned workflow ID to inspect
the workflow's event history.

## Order workflow

Creating an order starts `GreetingWorkflow` using the order UUID:

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
```

The workflow ID is the same as the order ID. The endpoint returns immediately
after starting the workflow rather than waiting for its greeting result.
