# URL Shortening API

Generates a base-62 short code for a URL. Every generated value uses the `go/`
prefix.

## Request

```text
GET /tinyUrl?url=<URL>
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
  "short_code": "go/3FzaP09xY"
}
```

The endpoint generates a UUID and encodes its integer value using base 62.
Each request generates a different code. A missing `url` parameter
produces a `422 Unprocessable Entity` response.

## How base-62 encoding works

The encoder uses 62 characters as digits:

```text
0-9 = values 0-9
a-z = values 10-35
A-Z = values 36-61
```

It repeatedly divides the UUID's integer value by 62. Each remainder selects a
character, and that character is added to the beginning of the result. The process
stops when the quotient reaches zero.

For example, encoding the number `3844` works as follows:

| Calculation | Quotient | Remainder | Character |
| --- | ---: | ---: | --- |
| `3844 ÷ 62` | 62 | 0 | `0` |
| `62 ÷ 62` | 1 | 0 | `0` |
| `1 ÷ 62` | 0 | 1 | `1` |

Reading the characters in reverse calculation order produces `100`. The API
then adds the prefix, resulting in `go/100`.

In the implementation, `divmod(number, 62)` returns the quotient and remainder
in one operation.

The endpoint currently generates codes only. Resolving a code back to its
original URL requires storing the mapping in a database.
