# Order Messages and Scheduling API

`POST /v1/messages` accepts an `EventType` and its `detailed_payload`.

## Order success

```json
{"EventType":"ORDER","detailed_payload":{"id":"ORDER_ID_FROM_RESPONSE","status":"SUCCESS"}}
```

The API publishes the same JSON to `projects/jasonapp-xm0830/topics/order_success`.
A `202 Accepted` response returns the event plus `topic` and Pub/Sub's
`message_id`. A publish failure returns `503`.

The worker pulls from
`projects/jasonapp-xm0830/subscriptions/order_success-sub` and signals the
Temporal workflow whose ID matches the order ID. It acknowledges messages
after a successful signal, discards invalid messages and signals for missing
workflows, and asks Pub/Sub to redeliver on other signal errors.

The service account needs `roles/pubsub.publisher` on the topic and
`roles/pubsub.subscriber` on the subscription.

## Local scheduler

```json
{"EventType":"SCHEDULING","detailed_payload":{"action":"START"}}
```

Send `STOP` to turn off the local heartbeat. The API applies the command to
its in-process scheduler and returns the event with `202 Accepted`.
