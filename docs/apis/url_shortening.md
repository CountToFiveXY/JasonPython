# URL Shortening API

Generates a lowercase base-26 short code for a URL.

## Request

```text
GET /tinyUrl?url=URL
```

The `url` query parameter is required.

### curl

```bash
curl --get --data-urlencode "url=https://example.com/a/long/path" http://127.0.0.1:8080/tinyUrl
```

### Python

```python
import requests

response = requests.get(
    "http://127.0.0.1:8080/tinyUrl",
    params={"url": "https://example.com/a/long/path"},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

## Response

```json
{
  "original_url": "https://example.com/a/long/path",
  "short_code": "bcdefghijk"
}
```

The endpoint generates a UUID and encodes its integer value using lowercase
base 26. Each request generates a different code. A missing `url` parameter
produces a `422 Unprocessable Entity` response.

The endpoint currently generates codes only. Resolving a code back to its
original URL requires storing the mapping in a database.
