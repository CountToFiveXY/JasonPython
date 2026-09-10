# Kafka Reference

The API uses an asynchronous Kafka producer. A separate worker polls the same
topic as part of a consumer group and signals the matching Temporal order
workflow when it consumes `{ "id": "ORDER_ID", "status": "SUCCESS" }`:

```bash
python -m src.messaging.worker
```

`scripts/run_local.sh` installs and starts a local Kafka broker, creates the
topic if necessary, and starts the worker automatically.

Consumer offsets are committed only after a message is validated and its
Temporal signal is accepted. Transient handling failures retry the same message.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | `127.0.0.1:9092` | Comma-separated Kafka brokers |
| `KAFKA_TOPIC` | `backend-messages` | Produced and consumed topic |
| `KAFKA_CONSUMER_GROUP` | `utility-api-message-worker` | Worker consumer group |

For an external Kafka cluster, set `KAFKA_BOOTSTRAP_SERVERS` before starting
the API and worker. Create the configured topic in that cluster separately.
