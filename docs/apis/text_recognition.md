# Text Recognition API

`POST /v1/text-recognition` reads the words out of an image through Cloud
Vision. It was added to lift track names off a screenshot of an in-game
line-up, but it is not specific to that: it returns whatever text it finds.

## Request

The image is the raw request body, so a client posts the bytes it already has
instead of base64-encoding them or building a multipart form. The
`Content-Type` must start with `image/`.

```bash
curl -X POST http://127.0.0.1:8000/v1/text-recognition \
  -H 'Content-Type: image/png' \
  --data-binary @tracks.png
```

Images above 8 MB are refused with HTTP `413`. A body that is not an image
gives HTTP `415`, and an empty one HTTP `400`.

## Response

```json
{
  "text": "WATERSLIDE WHIRL\nLEAP OF FAITH\nNOTRE DAME",
  "lines": [
    {"text": "WATERSLIDE WHIRL", "confidence": 0.98},
    {"text": "LEAP OF FAITH", "confidence": 0.97},
    {"text": "NOTRE DAME", "confidence": 0.96}
  ]
}
```

Confidence comes from Cloud Vision's document text detection. Plain text
detection returns the same words but leaves every confidence at zero, so
document detection is used even though the input is not a document.

`text` is everything Cloud Vision read as one block. `lines` is the same words
split up and returned in reading order: paragraphs are grouped into rows by
vertical proximity, then sorted left to right within each row. That ordering is
what makes a horizontal strip of captions come back in the order they appear on
screen rather than by height. Rows are found by proximity rather than by
bucketing the top coordinate, because captions sitting side by side rarely
align to the pixel and fixed buckets split two that straddle a boundary.

## Enabling Cloud Vision

The endpoint uses the same service account as Firestore, so no extra
credentials are needed, but the API has to be switched on for the project once:

<https://console.developers.google.com/apis/api/vision.googleapis.com/overview?project=761679938145>

Until it is, the endpoint answers HTTP `503` and repeats Google's message,
which names the project and links the page above. The first 1000 images each
month are free.
