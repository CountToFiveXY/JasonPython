# Galaxy Lens Leaderboard API

`GET /v1/leaderboard` reads the public Galaxy Lens leaderboard feed
and normalizes it for JasonApp. The response contains active and finished event
leaderboards, their participant totals, update timestamps, and ordered ranking
tiers. JasonUI requests this endpoint whenever the Leaderboard section becomes
active, and also exposes a manual refresh button.

The upstream Supabase URL and public anonymous key can be overridden with
`LEADERBOARD_SUPABASE_URL` and `LEADERBOARD_SUPABASE_ANON_KEY`.
The legacy `GALAXY_LENS_SUPABASE_URL` and `GALAXY_LENS_SUPABASE_ANON_KEY`
settings remain supported as fallbacks.
