# Image API

Returns the Metroid map as a JPEG image that browsers display directly.

## Request

```text
GET /display
```

### curl

```bash
curl http://127.0.0.1:8000/display --output metroidzm_map.jpg
```

## Response

The response body contains JPEG image data with this content type:

```text
Content-Type: image/jpeg
```

Open <http://127.0.0.1:8000/display> in a browser to display the image. This
endpoint does not require any parameters.
