# Temporal Reference

The API connects to Temporal at `127.0.0.1:7233` and uses the `default`
namespace unless environment variables override those values.

For the complete local startup sequence, follow
[How to run the server](../how_to_run_server.md). This page explains the
application's Temporal configuration and components.

## Components

- Temporal Server stores workflow event histories and creates tasks.
- `temporal.worker` polls the `utility-api` task queue and executes the
  registered workflows and activities.
- FastAPI starts workflows through its Temporal client.

The Temporal Server and Python worker are separate processes. Starting the
server does not automatically start the worker.

## Run and inspect a workflow

```bash
curl -X POST http://127.0.0.1:8080/workflows/greeting \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jason"}'
# Start a greeting workflow through FastAPI and wait for its result.
```

The response includes the workflow ID. Search for that ID in the Temporal Web
UI at <http://127.0.0.1:8233> to inspect its event history.

## Configuration

Both the API and worker recognize these environment variables:

| Variable | Default |
| --- | --- |
| `TEMPORAL_ADDRESS` | `127.0.0.1:7233` |
| `TEMPORAL_NAMESPACE` | `default` |
| `TEMPORAL_TASK_QUEUE` | `utility-api` |

The API and worker must use the same namespace and task queue.

Set configuration values before starting each Python process. For example:

```bash
export TEMPORAL_ADDRESS=127.0.0.1:7233  # Select the Temporal Server used by this process.
export TEMPORAL_NAMESPACE=default  # Select the namespace containing the workflows.
export TEMPORAL_TASK_QUEUE=utility-api  # Select the queue shared by FastAPI and the worker.
```

## Troubleshooting

- A connection error for `127.0.0.1:7233` means Temporal Server is not
  reachable at `TEMPORAL_ADDRESS`.
- A workflow request that waits indefinitely usually means the worker is not
  running or its namespace or task queue does not match FastAPI.
- A completed workflow and its full event history remain visible in the
  Temporal Web UI even after the worker stops.
