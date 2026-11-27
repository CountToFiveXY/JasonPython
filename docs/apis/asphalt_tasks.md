# Asphalt Tasks API

`POST /v1/asphalt-tasks` publishes a one-shot command to the Google
Cloud Pub/Sub topic `asphalt_task_requests`. It uses the same Google credentials
and project as Firestore.

The `type` field accepts `RESET`, `START_GAME`, `CLOSE_GAME`, `WINDOW`, `MUTE`,
and `REFILL_ADS`. A refill also accepts an integer `repeat` from 1 through 99;
when omitted, it defaults to 8:

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
  "topic": "projects/jasonapp-xm0830/topics/asphalt_task_requests",
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

Refill, Start, and Window responses include a `task_id` in addition to the Pub/Sub `message_id`.
Query `GET /v1/asphalt-tasks/{task_id}` for the task's `type` and status.
Status can be `QUEUED`, `RUNNING`,
`SUCCEEDED`, `FAILED`, or `UNKNOWN`. A successful result means the Windows
script completed its requested runs. Failed or unknown results can include an
`error` message.

The Windows worker publishes updates to `asphalt_task_results`. JasonPython
consumes `asphalt_task_results_sub` in both startup modes and saves the status
in Firestore. The backend account needs subscriber access on that subscription
and write access to the Firestore collection `asphalt_tasks`. Each document
stores the task `type`, e.g. `REFILL_ADS`.

`GET /v1/asphalt-tasks` returns the last 10 requests in newest-first order.
Each entry includes the task type, request time, and status. Untracked
commands show `SUBMITTED` after Pub/Sub accepts them. Tracked status updates
continue to come from the worker.

Start game uses:

```json
{"type":"START_GAME"}
```

Close game uses:

```json
{"type":"CLOSE_GAME"}
```

Window uses:

```json
{"type":"WINDOW"}
```

Mute uses:

```json
{"type":"MUTE"}
```

An unsupported type returns `422`. Missing Google credentials or a Pub/Sub
publish failure returns `503`.

## Credentials and permission

Local startup reads `~/.config/jasonapp/service-account.json` through
`GOOGLE_APPLICATION_CREDENTIALS`. Grant that file's `client_email` the
`Pub/Sub Publisher` (`roles/pubsub.publisher`) role on
`asphalt_task_requests`. Scope its subscriber access to the result subscription.

The Windows worker uses a separate service account with
`roles/pubsub.subscriber` on `asphalt_task_requests_sub` and
`roles/pubsub.publisher` on `asphalt_task_results`.

## Task request and result flow

```mermaid
sequenceDiagram
    autonumber
    participant UI as JasonUI or WeChat mini program
    participant API as JasonPython HTTP API
    participant DB as Firestore default database
    participant Req as Pub/Sub requests
    participant Win as JasonJava Windows worker
    participant Res as Pub/Sub results
    participant Consumer as JasonPython result consumer

    UI->>API: POST /v1/asphalt-tasks with type and optional repeat
    API->>DB: Create asphalt_tasks/{task_id} with type, QUEUED, and timestamps
    API->>Req: Publish command to asphalt_task_requests
    Note over API,Req: Refill, Start, and Window carry task_id as a Pub/Sub attribute
    Req-->>API: Pub/Sub accepts the command and returns message_id
    opt Command without result tracking
        API->>DB: Record SUBMITTED
    end
    API-->>UI: 202 Accepted with message_id and task_id for tracked commands
    Note over UI,API: HTTP 202 confirms submission. Windows execution is asynchronous.

    Req->>Win: Deliver via asphalt_task_requests_sub
    alt Refill, Start, or Window
        alt First delivery
            Win->>Win: Create local claim for task_id
            Win->>Res: Try to publish RUNNING to asphalt_task_results
            Win->>Win: Run task script with repeat count for Refill
            Win->>Win: Save SUCCEEDED or FAILED locally
        else Redelivery
            Win->>Win: Load saved result or save UNKNOWN if only the claim exists
        end
        Win->>Res: Publish final result with task_id, status, and optional error
        alt Final result publish accepted
            Win-->>Req: ACK the request
        else Final result publish fails
            Win-->>Req: NACK so the saved result can be retried
        end
    else Command without result tracking
        Win->>Win: Run the task script
        Win-->>Req: ACK on success or NACK on failure
    end

    Note over Res,Consumer: Results are consumed in the background as they arrive
    loop Each tracked result event
        Res->>Consumer: Deliver via asphalt_task_results_sub
        Consumer->>DB: Apply status by task_id in a transaction
        alt Firestore processing succeeds
            DB-->>Consumer: Commit update or ignore duplicate or late event
            Consumer-->>Res: ACK the result
        else Firestore processing fails
            Consumer-->>Res: NACK the result for redelivery
        end
    end

    loop About every 2 seconds while tracking a task
        UI->>API: GET /v1/asphalt-tasks/{task_id}
        API->>DB: Read asphalt_tasks/{task_id}
        DB-->>API: Current saved status
        API-->>UI: Status and optional error
    end
    Note over UI: Stop polling on a final status or when the wait expires

    opt JasonUI Task History
        UI->>API: GET /v1/asphalt-tasks
        API->>DB: Query the 10 most recent requests
        API-->>UI: Return history rows and their latest statuses
    end
```

Firestore is the source of truth for the displayed status. The UI only talks
to JasonPython over HTTP. For commands without result tracking, `SUBMITTED`
means Pub/Sub accepted the request. For tracked commands, a worker result comes from
the worker. If only a local claim survives a worker crash, the worker reports
`UNKNOWN` on redelivery because the script may have run partially.
