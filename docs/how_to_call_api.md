# How to Call the APIs

The examples below assume the server is running at `http://127.0.0.1:8080`.

## UUID message API

Send a `GET` request to `/` with a required `text` query parameter:

```bash
curl --get --data-urlencode "text=hello world" http://127.0.0.1:8080/
```

Example response:

```json
{"encoded message": "hello world-550e8400-e29b-41d4-a716-446655440000"}
```

Each request generates a different UUID. If `text` is missing, FastAPI
returns a `422 Unprocessable Entity` validation response.

## Message API

```bash
curl http://127.0.0.1:8080/message
```

Response:

```json
"Hello from FastAPI!"
```

## Health check API

```bash
curl http://127.0.0.1:8080/health
```

Response:

```json
{"status": "OK"}
```

## Python example

```python
import requests

response = requests.get(
    "http://127.0.0.1:8080/",
    params={"text": "hello world"},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

Interactive documentation for all endpoints is available at
<http://127.0.0.1:8080/docs>.
