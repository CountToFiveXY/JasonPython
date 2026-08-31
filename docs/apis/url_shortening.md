# URL Shortening API

Returns a short redirect path for a URL. The path uses the format
`go/<eight-character-code>`.

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
curl -X POST http://127.0.0.1:8000/v1/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/a/long/path"}'
```

### Python

```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/v1/shorten",
    json={"url": "https://example.com/a/long/path"},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

## Response

```json
{
  "shortUrl": "go/3FzaP09x"
}
```

The endpoint generates eight random letters and digits, then stores the
code-to-URL mapping in Redis. A missing `url` parameter produces a `422
Unprocessable Entity` response.

## Follow a short URL

Open the returned path on the same API server:

```text
http://127.0.0.1:8000/go/3FzaP09x
```

The code must contain exactly eight letters or digits. Validation happens
before Redis is queried. An invalid code produces a client error, and an
unknown or expired valid code produces `404 Not Found`.

When the code exists, the response page attempts to open the original URL in a
new browser tab. If the browser blocks automatic popups, it redirects the
current tab instead and displays a clickable fallback link.

Links using `127.0.0.1` are local to the server computer. To share generated
links with other people, run this API at a publicly reachable domain or IP and
configure JasonUI to use that public server address.

## How code generation works

The generator chooses each character independently from this 62-character
alphabet:

```text
0-9 = values 0-9
a-z = values 10-35
A-Z = values 36-61
```

Python's `secrets.choice()` is called eight times to produce a code such as
`3FzaP09x`. Eight characters provide `62⁸`, or `218,340,105,584,896`, possible
codes.

Redis stores the mapping with `SET ... NX`. The `NX` option means “only set the
key when it does not already exist.” The availability check and write therefore
happen as one atomic Redis command. If a generated code is already used, Redis
does not overwrite it and the API generates another code.
