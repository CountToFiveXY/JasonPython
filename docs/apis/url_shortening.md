# URL Shortening API

Returns an eight-character base-62 short code for a URL. The response contains
only the code and does not include a redirect-route prefix.

## Request

```text
POST /v1/shorten
```

Send the long URL in a JSON request body:

```json
{
  "url": "https://example.com/a/long/path"
}
```

### curl

```bash
curl -X POST http://127.0.0.1:8080/v1/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/a/long/path"}'
```

### Python

```python
import requests

response = requests.post(
    "http://127.0.0.1:8080/v1/shorten",
    json={"url": "https://example.com/a/long/path"},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

## Response

```json
{
  "shortKey": "3FzaP09x"
}
```

The endpoint first looks up the URL in Redis. If the URL has already been
shortened, it returns the existing code. Otherwise, it generates a UUID,
encodes its integer value using base 62, limits it to the eight-character
base-62 range, and pads shorter results with leading zeroes. It atomically
stores both the code-to-URL and URL-to-code mappings. A missing `url` parameter
produces a `422 Unprocessable Entity` response.

## Follow a short URL

Open the returned path on the same API server:

```text
http://127.0.0.1:8080/3FzaP09x
```

The code must contain exactly eight base-62 characters. Validation happens
before Redis is queried. An invalid code produces a client error, and an
unknown or expired valid code produces `404 Not Found`.

When the code exists, the response page attempts to open the original URL in a
new browser tab. If the browser blocks automatic popups, it redirects the
current tab instead and displays a clickable fallback link.

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

Reading the characters in reverse calculation order produces `100`. For an
eight-character code, the API pads it to `00000100`.

In the implementation, `divmod(number, 62)` returns the quotient and remainder
in one operation.

Eight base-62 characters provide `62⁸`, or `218,340,105,584,896`, possible
codes. Collisions are still possible because the code is generated randomly.
The API uses an atomic Redis script to claim a code and store its reverse
lookup. If a code collision occurs, it generates another code.
