# Temporal Reference

All three workflows use the same Temporal Service at `127.0.0.1:7233` by default.
Each uses its own namespace.

| Workflow | Namespace | Started by |
| --- | --- | --- |
| `HelloWorkflow` | `default` | FastAPI |
| `OrderWorkflow` | `order` | FastAPI |
| `GreetingWorkflow` | `payout` | Temporal CLI or another Temporal client |

For the complete local startup sequence, follow
[How to run the server](../how_to_run_server.md). This page explains the
application's Temporal configuration and components.

## Components

- Temporal Server stores workflow event histories and creates tasks.
- `src.temporal.worker` runs one worker per workflow namespace. Each polls its
  namespace’s `utility-api` task queue.
- FastAPI starts hello and order workflows through separate clients. The Pub/Sub
  subscriber sends order status signals in the same namespace used to start orders.

The Temporal Server and Python worker are separate processes. Starting the
server does not automatically start the worker.

## Run and inspect a workflow

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
# Create an order and start OrderWorkflow with the order UUID.
```

The order ID and workflow ID are identical. Search for that ID in the Temporal
Web UI under `order` at <http://127.0.0.1:8233> to inspect its one-hour timer, Pub/Sub-delivered
signal, completion activity, and final result.

## Configuration

Both the API and worker recognize these environment variables:

| Variable | Default |
| --- | --- |
| `TEMPORAL_ADDRESS` | `127.0.0.1:7233` |
| `TEMPORAL_NAMESPACE` (hello) | `default` |
| `TEMPORAL_ORDER_NAMESPACE` | `order` |
| `TEMPORAL_PAYOUT_NAMESPACE` | `payout` |
| `TEMPORAL_TASK_QUEUE` | `utility-api` |

Set the same namespace values across the API, Temporal workers, and Pub/Sub
subscriber. For a remote Temporal address, provision the configured namespaces
before starting the application. The local launcher creates them automatically
for the local server.

For an existing deployment, stop starting order and greeting workflows in the
old namespace and let those executions finish with the old workers and signal
routing before switching to this version. Existing workflow executions and their
histories stay in the namespace where they started.

## Troubleshooting

- A connection error for `127.0.0.1:7233` means Temporal Server is not
  reachable at `TEMPORAL_ADDRESS`.
- A workflow request that waits indefinitely usually means the worker is not
  running or its namespace or task queue does not match FastAPI.
- A completed workflow and its full event history remain visible in the
  Temporal Web UI even after the worker stops.
