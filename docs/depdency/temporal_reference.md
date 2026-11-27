# Temporal Reference

All three workflows use the same Temporal Service at `127.0.0.1:7233` by default.
Each uses its own namespace.

| Workflow | Namespace | Task queue | Started by |
| --- | --- | --- | --- |
| `HelloWorkflow` | `default` | `utility-api` | FastAPI |
| `OrderWorkflow` | `order` | `order-queue` | FastAPI |
| `PayoutWorkflow` | `payout` | `payout-queue` | Order workflow via Nexus, or a Temporal client |

For the complete local startup sequence, follow
[How to run the server](../how_to_run_server.md). This page explains the
application's Temporal configuration and components.

## Components

- Temporal Server stores workflow event histories and creates tasks.
- `src.temporal.worker` runs one worker per workflow namespace. Each polls its
  configured task queue.
- FastAPI starts hello and order workflows through separate clients. The Pub/Sub
  subscriber sends order status signals in the same namespace used to start orders.

The Temporal Server and Python worker are separate processes. Starting the
server does not automatically start the worker.

## Run and inspect a workflow

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
# Write the order document, then start OrderWorkflow with the order UUID.
```

The order ID and workflow ID are identical. Search for that ID in the Temporal
Web UI under `order` at <http://127.0.0.1:8233> to inspect its one-hour timer, Pub/Sub-delivered
signal, payout operation, completion activity, and final result. After the
`SUCCESS` signal, the order awaits `PayoutWorkflow` in the `payout` namespace
via the `payout-nexus` endpoint and passes the order ID. The Nexus handler starts
the payout with workflow ID `<order_id>_payout` when that field is present.
Before starting the workflow, `payout_service` creates `payouts/{payout_id}`
with status `INITIATED`. The workflow runs two activities:

1. `payout.start` sets the payout document to `STARTED`, writes `payout_id`
   and `payout_status: PAYOUT_STARTED` to the order document, and signals the
   order before printing the existing payout message.
2. `payout.complete` sets the payout document to `COMPLETED`, writes
   `payout_status: PAYOUT_COMPLETED` to the order, and sends the completion
   signal. The order then marks itself complete.

If the one-hour signal wait times out, the order skips payout. If the payout
Nexus operation fails or times out, the order workflow fails before marking
the order complete.

## Configuration

The API, workers, and local launcher share these settings.

| Variable | Default |
| --- | --- |
| `TEMPORAL_ADDRESS` | `127.0.0.1:7233` |
| `TEMPORAL_NAMESPACE` (hello) | `default` |
| `TEMPORAL_ORDER_NAMESPACE` | `order` |
| `TEMPORAL_PAYOUT_NAMESPACE` | `payout` |
| `PAYOUT_NEXUS` | `payout-nexus` |
| `TEMPORAL_TASK_QUEUE` (hello) | `utility-api` |
| `TEMPORAL_ORDER_TASK_QUEUE` | `order-queue` |
| `TEMPORAL_PAYOUT_TASK_QUEUE` | `payout-queue` |

Set the same namespace values across the API, Temporal workers, and Pub/Sub
subscriber. For a remote Temporal address, provision the configured namespaces
before starting the application. The local launcher creates them automatically
for the local server along with the payout Nexus endpoint. For a remote
server or manual startup, create the payout endpoint before starting orders:

```bash
temporal operator nexus endpoint create --name payout-nexus \
  --target-namespace payout --target-task-queue payout-queue
```

The local launcher updates the existing endpoint to match the configured
payout namespace and task queue. For remote or manual setups, update the existing
endpoint with the same target flags.

Before deploying, let in-flight order and payout executions finish on their
current workers. Their task queues and recorded workflow commands may refer to
the old configuration.

## Troubleshooting

- A connection error for `127.0.0.1:7233` means Temporal Server is not
  reachable at `TEMPORAL_ADDRESS`.
- A workflow request that waits indefinitely usually means the worker is not
  running or its namespace or task queue does not match FastAPI.
- A completed workflow and its full event history remain visible in the
  Temporal Web UI even after the worker stops.
