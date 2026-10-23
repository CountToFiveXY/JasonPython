# Firestore Reference

The order workflow writes to the `orders` collection in the `jasonapp-xm0830`
Firebase project by default through the reusable `write_firestore_document`
activity. The [Gauntlet API](../apis/gauntlet.md) stores maps, tracks,
and lap times in the `maps` collection of the same project.

## Local authentication

Each laptop uses its own service account and key; create them with
[How to run the server, step 3](../how_to_run_server.md#3-create-this-laptops-google-cloud-service-account).
The key lives at `~/.config/jasonapp/service-account.json`, which
`scripts/run_local.sh` uses automatically. To use a key elsewhere:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
./scripts/run_local.sh
```

Never commit the service-account JSON file. In a Google-hosted production
environment, use Application Default Credentials from the assigned service
account instead of a downloaded key.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `FIREBASE_PROJECT_ID` | `jasonapp-xm0830` | Firebase project receiving orders |
| `FIRESTORE_ORDER_COLLECTION` | `orders` | Collection containing order documents |
| `FIRESTORE_MAP_COLLECTION` | `maps` | Collection containing Gauntlet maps |

The service account needs permission to create documents in Cloud Firestore.
Order documents use the `expires_at` timestamp for automatic cleanup. A native
Firestore TTL policy on the `orders` collection group's `expires_at`
field is the sole deletion mechanism; Firestore schedules removal after the
stored expiration time.
