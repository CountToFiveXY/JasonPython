# File Transfer API

Shares `~/Documents/JasonApp/FileTransfer` with every device on the same LAN as
a web page. Two switches control what devices can do, both off by default:
**allow uploads** and **require code** (see [Access](#access)). The API starts
and stops a separate transfer server; other devices open the returned `url` in
a browser.

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
  -H 'Content-Type: application/json' -d '{"allow_uploads": true, "require_code": true}'
```

`start` takes an optional body with `allow_uploads` and `require_code`, both
`false` when left out. Calling `start` again while sharing changes the
switches without restarting the share, so send both every time.

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
  "require_code": true,
  "access_code": "0427",
  "folders": ["Photos"],
  "files": [{"name": "report.pdf", "size": 48213}]
}
```

`start` creates the folder if it is missing and is safe to call again while
running. `host_name` is `null` when the name could not be announced; `url`
then falls back to `ip_url`. Both are `null` when the server is stopped or
this computer has no network address. The download server uses port `80`, or
a free port (added to the URLs) when that one is busy.

## What the transfer server shares

Visible files and folders inside the shared folder, at any depth. Devices
browse into a folder at its address ending in `/`, such as
`http://jason.local/Photos/Trip/`, with a back link and a path at the top;
a file's address is its path, such as `/Photos/Trip/beach.jpg`.

Hidden files and folders (such as `.DS_Store`) and symlinks are never listed
or served. Every part of a requested path must be an ordinary visible name,
so `..`, backslashes, and empty parts are refused, and the final path must
still lie inside the shared folder.

Folders are created only on the host Mac. Devices upload files into the
folder they are viewing (`POST /upload?folder=Photos/Trip&name=…`); a folder
that does not exist returns `404`, and folders themselves cannot be uploaded.

The status lists the top-level `folders` beside `files`.

## Access

| Require code | Allow uploads | What devices can do |
|---|---|---|
| off | off | download (the default) |
| off | on | download and upload |
| on | off | see the file list; download after entering the code |
| on | on | see the file list; download and upload after entering the code |

With the code required, devices can still browse folders, but files are
listed without links and the page asks for the code; downloading a file
without it returns `401`. After the code, the page returns to the folder it
was entered in.

The code is fixed and kept in Firestore, so every Mac uses the same one:

| Collection | Document | Field | Type |
|---|---|---|---|
| `config` | `file_transfer` | `upload_code` | string, exactly 4 digits, e.g. `"0427"` |

Change it by hand in the Firebase console. Store it as a **string**: a number
field drops leading zeros, so it is refused. The code is read when
`require_code` is turned on, so a new code applies the next time it is. If the
document is missing, the code is invalid, or Firestore credentials are not
set, `start` with `require_code: true` returns `503` with the reason and
nothing changes. `access_code` in the status is that code while it is
required.

A correct code sets an `HttpOnly`, `SameSite=Strict` cookie, so each device
enters it once per sharing session. Turning `require_code` off, or stopping
the share, signs every device out. Each wrong attempt waits one second.

## Uploads

Uploaded files:

- keep their name; an existing file is never replaced, and a clash is saved as
  `name (1).ext`
- are written to a hidden temporary file first, so an interrupted upload
  leaves nothing behind
- can be up to 10 GB, and are refused when the Mac would have under 1 GB free

The code travels over plain HTTP, so anyone watching the Wi-Fi traffic
could read it. That is acceptable on a home network but not on public Wi-Fi.

## Configuration

| Variable             | Default                               |
|----------------------|---------------------------------------|
| `FILE_TRANSFER_DIR`  | `~/Documents/JasonApp/FileTransfer`   |
| `FILE_TRANSFER_PORT` | `80`                                  |
| `FILE_TRANSFER_HOST_NAME` | `jason.local`                    |
| `FILE_TRANSFER_MAX_UPLOAD_GB` | `10`                         |
