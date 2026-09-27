# Kafka Reference

The API uses an asynchronous Kafka producer and two topics. A separate worker
polls `order-status` and signals the matching Temporal order workflow when it
consumes `{ "id": "ORDER_ID", "status": "SUCCESS" }`:

```bash
python -m src.messaging.worker
```

FastAPI itself polls `scheduler-control` so a `START` or `STOP` command can
change its in-process heartbeat scheduler without Redis. `scripts/run_local.sh`
installs and starts a local Kafka broker, creates both topics if necessary, and
starts the order worker automatically.

The scheduler controller starts disabled on every FastAPI launch. Only a new
`START` command on `scheduler-control` wakes it; previous Kafka records are not
replayed to restore control state.

Consumer offsets are committed only after a message is validated and its
Temporal signal is accepted. Transient handling failures retry the same message.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | `127.0.0.1:9092` | Comma-separated Kafka brokers |
| `KAFKA_ORDER_TOPIC` | `order-status` | Temporal order events |
| `KAFKA_SCHEDULER_TOPIC` | `scheduler-control` | Scheduler `START`/`STOP` commands |
| `KAFKA_ORDER_CONSUMER_GROUP` | `utility-api-order-worker` | Temporal order worker group |
| `KAFKA_SCHEDULER_CONSUMER_GROUP` | `utility-api-scheduler` | FastAPI scheduler-control group |

For an external Kafka cluster, set `KAFKA_BOOTSTRAP_SERVERS` before starting
the API and worker. Create both configured topics in that cluster separately.
