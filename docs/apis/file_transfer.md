# File Transfer API

Shares `~/Documents/JasonApp/FileTransfer` with every device on the same LAN as
a web page. Devices can always download; uploading is off unless the host turns
it on. The API starts and stops a separate download server;
other devices open the returned `url` in a browser.

The sharing Mac announces **`jason.local`** through Bonjour, so every device
uses `http://jason.local` no matter which Mac is hosting. Only one Mac can own
the name: starting a second share elsewhere returns `409 Conflict` naming the
Mac that already shares. Stopping withdraws the name so another Mac can take
over. Devices without `.local` support (some Android phones) use `ip_url`.

These endpoints only accept requests from this computer (`127.0.0.1` or `::1`)
and return `403 Forbidden` to anyone else, because FastAPI listens on every
interface.

## Requests

```text
GET  /v1/file-transfer
POST /v1/file-transfer/start
POST /v1/file-transfer/stop
```

### curl

```bash
curl -X POST http://127.0.0.1:8000/v1/file-transfer/start
curl -X POST http://127.0.0.1:8000/v1/file-transfer/start \
  -H 'Content-Type: application/json' -d '{"allow_uploads": true}'
```

`start` takes an optional body. `allow_uploads` defaults to `false`; calling
`start` again while sharing turns uploads on or off without restarting the
share.

## Response

All three endpoints return the current status:

```json
{
  "running": true,
  "folder": "/Users/me/Documents/JasonApp/FileTransfer",
  "port": 80,
  "host_name": "jason.local",
  "url": "http://jason.local",
  "ip_url": "http://192.168.1.23",
  "allow_uploads": true,
  "upload_code": "482913",
  "files": [{"name": "report.pdf", "size": 48213}]
}
```

`start` creates the folder if it is missing and is safe to call again while
running. `host_name` is `null` when the name could not be announced; `url`
then falls back to `ip_url`. Both are `null` when the server is stopped or
this computer has no network address. The download server uses port `80`, or
a free port (added to the URLs) when that one is busy.

## What the transfer server shares

Only visible, regular files directly inside the folder. Subfolders, hidden
files such as `.DS_Store`, and symlinks are not listed or served.

## Uploads

When `allow_uploads` is on, the page asks each device for the six-digit
`upload_code` shown on the host Mac. A correct code sets an `HttpOnly`,
`SameSite=Strict` cookie, so each device enters it once per sharing session.
Turning uploads off, or stopping the share, issues a new code next time and
signs every device out. After 10 wrong codes the code is replaced, and each
wrong attempt waits one second.

Uploaded files:

- keep their name; an existing file is never replaced, and a clash is saved as
  `name (1).ext`
- are written to a hidden temporary file first, so an interrupted upload
  leaves nothing behind
- can be up to 10 GB, and are refused when the Mac would have under 1 GB free

The upload code travels over plain HTTP, so anyone watching the Wi-Fi traffic
could read it. That is acceptable on a home network but not on public Wi-Fi.

## Configuration

| Variable             | Default                               |
|----------------------|---------------------------------------|
| `FILE_TRANSFER_DIR`  | `~/Documents/JasonApp/FileTransfer`   |
| `FILE_TRANSFER_PORT` | `80`                                  |
| `FILE_TRANSFER_HOST_NAME` | `jason.local`                    |
| `FILE_TRANSFER_MAX_UPLOAD_GB` | `10`                         |
