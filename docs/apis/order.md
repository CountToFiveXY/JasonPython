# Order API

`POST /v1/order` creates an order in Cloud Firestore and starts a Temporal
`GreetingWorkflow`. A user ID is required.

## Request

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
```

## Response

The endpoint responds with HTTP `201 Created`:

```json
{
  "id": "12345678-1234-1234-1234-123456789abc",
  "user_id": "user-123",
  "created": "2026-09-07T18:30:00Z",
  "workflow_id": "12345678-1234-1234-1234-123456789abc"
}
```

The `orders/{id}` Firestore document contains `id`, `user_id`, and `created`.
The UUID is used as both the Firestore document ID and Temporal workflow ID.
The API starts the workflow but does not wait for it to finish.

See the [Firestore reference](../depdency/firestore_reference.md) for local
authentication and configuration.
