# Firestore Reference

Orders and payouts use the `orders` and `payouts` collections in the
`workflows` database of the `jasonapp-xm0830` Firebase project. The
[Gauntlet API](../apis/gauntlet.md) uses the default database in the same project.

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

The service account needs read and write access to the `workflows` database.
New orders and payouts receive an `expires_at` timestamp three days after
creation. For automatic deletion, configure Firestore TTL on `expires_at`
for both collection groups in the `workflows` database.
