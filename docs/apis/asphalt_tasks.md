# Asphalt Tasks API

`POST /v1/asphalt-tasks` publishes a one-shot command to the Google
Cloud Pub/Sub topic `asphalt_tasks`. It uses the same Google credentials
and project as Firestore.

The request accepts exactly one field. Its allowed values are `RESET` and
`REFILL_ADS`:

```bash
curl -X POST http://127.0.0.1:8000/v1/asphalt-tasks \
  -H 'Content-Type: application/json' \
  -d '{"type":"RESET"}'
```

The API returns `202 Accepted` after Pub/Sub acknowledges the publish:

```json
{
  "type": "RESET",
  "topic": "projects/jasonapp-xm0830/topics/asphalt_tasks",
  "message_id": "1234567890"
}
```

The Pub/Sub message body itself remains the same one-field JSON object:

```json
{"type":"RESET"}
```

An unsupported type returns `422`. Missing Google credentials or a Pub/Sub
publish failure returns `503`.

## Credentials and permission

Local startup reads `~/.config/jasonapp/service-account.json` through
`GOOGLE_APPLICATION_CREDENTIALS`. Grant that file's `client_email` the
`Pub/Sub Publisher` (`roles/pubsub.publisher`) role on
`asphalt_tasks`. Do not grant subscriber access to the backend account.

The Windows worker should use a separate service account with subscriber
permission only on its pull subscription.
