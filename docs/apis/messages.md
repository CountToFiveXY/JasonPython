# Messages API

`POST /v1/messages` accepts one typed event envelope and responds after Kafka
acknowledges the record. `EventType` selects and validates `detailed_payload`,
then routes the message to its dedicated topic.

The HTTP router delegates publishing to `MessageService`, which owns the Kafka
topic, message key, serialization, and acknowledgement handling.

## Request

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"EventType":"ORDER","detailed_payload":{"id":"ecb3a6c9-f17b-4bac-8e3a-ffc4431599d4","status":"SUCCESS"}}'
```

## Response

The endpoint responds with HTTP `202 Accepted`:

```json
{
  "EventType": "ORDER",
  "detailed_payload": {
    "id": "12345678-1234-1234-1234-123456789abc",
    "status": "SUCCESS"
  },
  "topic": "order-status",
  "partition": 0,
  "offset": 1
}
```

The order worker consumes the event independently and sends `update_status` to
the matching `OrderWorkflow`. See the
[Kafka reference](../depdency/kafka_reference.md) for runtime configuration.

## Control the local scheduler

The same `POST /v1/messages` endpoint accepts `SCHEDULING` events and publishes
them to the dedicated `scheduler-control` Kafka topic. A consumer inside FastAPI
applies the command directly within one second. Redis is not involved; each
backend restart starts with the scheduler asleep until a new `START` arrives.

Stop the heartbeat:

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"EventType":"SCHEDULING","detailed_payload":{"action":"STOP"}}'
```

Start it again:

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"EventType":"SCHEDULING","detailed_payload":{"action":"START"}}'
```

Both calls return `202 Accepted` after Kafka acknowledges the command. Repeating
the same command is safe.
