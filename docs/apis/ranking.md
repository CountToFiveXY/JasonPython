# Ranking Image API

`POST /v1/ranking` renders a 304 × 506 PNG image.

## Galaxy Lens leaderboards

`GET /v1/ranking/leaderboards` reads the public Galaxy Lens leaderboard feed
and normalizes it for JasonApp. The response contains active and finished event
leaderboards, their participant totals, update timestamps, and ordered ranking
tiers. JasonUI requests this endpoint whenever the Ranking Card section becomes
active, and also exposes a manual refresh button.

The upstream Supabase URL and public anonymous key can be overridden with
`GALAXY_LENS_SUPABASE_URL` and `GALAXY_LENS_SUPABASE_ANON_KEY`.
The HTTP router validates the request and delegates rendering to the stateless
`RankingService`.

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

The response body is an `image/png` attachment named `ranking.png`. The server
returns the generated image without writing a copy to its local filesystem.
Save the response to a specific path with curl:

```bash
curl -X POST http://127.0.0.1:8000/v1/ranking \
  -H 'Content-Type: application/json' \
  -d '{"total":28916,"type":"CH","car":"Galaxy"}' \
  --output ranking.png
```

The image timestamp uses the server's local timezone. Counts are rounded to the
nearest whole participant, with exact halves rounded up.

Text is rendered in Arial, using Arial Bold where emphasized. Car names shrink
automatically to fit the header. Simplified Chinese car names use a compatible
CJK sans-serif font such as Hiragino Sans GB, Microsoft YaHei, or Noto Sans CJK.
