# Ranking Image API

`POST /v1/ranking` renders a 304 × 506 PNG image.

## Request

```json
{
  "total": 28916,
  "type": "CH",
  "car": "Galaxy"
}
```

- `total` must be a positive integer.
- `type` must be `SE`, `SP`, or `CH`.
- `car` is the name displayed in the top-right header (1–16 characters).

The response body is an `image/png` attachment, so a browser downloads it. The
server also saves a timestamped copy to the current user's `Desktop` directory.
Its filename uses `{CAR}_{TYPE}_{YYYYMMDD_HHMMSS}.png`, for example
`Galaxy_SE_20260823_031100.png`.
Save the response to a specific path with curl:

```bash
curl -X POST http://127.0.0.1:8080/v1/ranking \
  -H 'Content-Type: application/json' \
  -d '{"total":28916,"type":"CH","car":"Galaxy"}' \
  --output ranking.png
```

The image timestamp uses the server's local timezone. Counts are rounded to the
nearest whole participant, with exact halves rounded up.

Text is rendered in Arial, using Arial Bold where emphasized. A compatible
sans-serif font is used as a fallback when Arial is unavailable.
