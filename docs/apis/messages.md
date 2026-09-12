# Messages API

`POST /v1/messages` publishes an order status event to Kafka and responds after
the broker acknowledges the record. A `SUCCESS` event signals the Temporal
workflow whose workflow ID matches `id`.

The HTTP router delegates publishing to `MessageService`, which owns the Kafka
topic, message key, serialization, and acknowledgement handling.

## Request

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"id":"ecb3a6c9-f17b-4bac-8e3a-ffc4431599d4","status":"SUCCESS"}'
```

## Response

The endpoint responds with HTTP `202 Accepted`:

```json
{
  "id": "12345678-1234-1234-1234-123456789abc",
  "status": "SUCCESS",
  "topic": "backend-messages",
  "partition": 0,
  "offset": 1
}
```

The message worker consumes the event independently and sends `update_status`
to the matching `OrderWorkflow`. See the
[Kafka reference](../depdency/kafka_reference.md) for runtime configuration.
