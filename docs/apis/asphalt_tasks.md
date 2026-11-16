# Asphalt Tasks API

`POST /v1/asphalt-tasks` publishes a one-shot command to the Google
Cloud Pub/Sub topic `asphalt_legend_topic`. It uses the same Google credentials
and project as Firestore.

The `type` field accepts `RESET` and `REFILL_ADS`. A refill also accepts an
integer `repeat` from 1 through 99; when omitted, it defaults to 8:

```bash
curl -X POST http://127.0.0.1:8000/v1/asphalt-tasks \
  -H 'Content-Type: application/json' \
  -d '{"type":"RESET"}'
```

```bash
curl -X POST http://127.0.0.1:8000/v1/asphalt-tasks \
  -H 'Content-Type: application/json' \
  -d '{"type":"REFILL_ADS","repeat":8}'
```

The API returns `202 Accepted` after Pub/Sub acknowledges the publish:

```json
{
  "type": "RESET",
  "topic": "projects/jasonapp-xm0830/topics/asphalt_legend_topic",
  "message_id": "1234567890"
}
```

Each API request publishes exactly one Pub/Sub message. Reset uses:

```json
{"type":"RESET"}
```

Refill includes its repeat count in that single message:

```json
{"type":"REFILL_ADS","repeat":8}
```

An unsupported type returns `422`. Missing Google credentials or a Pub/Sub
publish failure returns `503`.

## Credentials and permission

Local startup reads `~/.config/jasonapp/service-account.json` through
`GOOGLE_APPLICATION_CREDENTIALS`. Grant that file's `client_email` the
`Pub/Sub Publisher` (`roles/pubsub.publisher`) role on
`asphalt_legend_topic`. Do not grant subscriber access to the backend account.

The Windows worker should use a separate service account with subscriber
permission only on its pull subscription.
