# How to Call the API

## Request

Send a `GET` request to `/` with a required `text` query parameter:

```text
GET /?text=hello
```

### Web browser

Open <http://127.0.0.1:8080/?text=hello>.

### curl

```bash
curl --get --data-urlencode "text=hello world" http://127.0.0.1:8080/
```

### Python

Install `requests` if needed, then call the endpoint:

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

## Response

The API appends a newly generated UUID to the supplied text:

```json
{"message": "hello-550e8400-e29b-41d4-a716-446655440000"}
```

Each request generates a different UUID.

If `text` is missing, FastAPI returns a `422 Unprocessable Entity` validation
response.
