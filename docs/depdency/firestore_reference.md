# Firestore Reference

The order API writes to the `orders` collection in the `jasonapp-xm0830`
Firebase project by default.

## Local authentication

Generate a service-account key from Firebase Console under **Project settings →
Service accounts**, store the JSON file outside this repository, and expose its
path before starting the API:

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

The service account needs permission to create documents in Cloud Firestore.
Order documents use the `expires_at` timestamp for automatic cleanup. A
dedicated Temporal cleanup workflow deletes each document after 24 hours. A
native Firestore TTL policy on the `orders` collection group's `expires_at`
field can also be enabled when the project administrator grants permission.
