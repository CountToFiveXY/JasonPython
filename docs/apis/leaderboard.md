# Leaderboard API

The leaderboard stores maps, the tracks that belong to them, and the fastest
car times recorded on each track. Cloud Firestore holds the data, so times
survive restarts and can be inspected in the Firebase console.

A map owns a fixed pair of tracks, and a track belongs to exactly one map. Maps
and tracks are created together and cannot be renamed or removed afterwards.
Only car times change.

## Identifiers

Maps and tracks are addressed by an identifier derived from their display name:
lower-cased, with every run of other characters replaced by a hyphen. `New York`
becomes `new-york` and `A park In A run` becomes `a-park-in-a-run`. Two maps
cannot share an identifier, and the two tracks in one map must differ.

Letters of every script are kept, so `旧金山` stays `旧金山` and the car `杰弟`
stays `杰弟`. Only characters that are neither letters nor digits become
hyphens, which keeps Firestore console paths readable for non-Latin names. A
name made entirely of punctuation has no identifier and is rejected with HTTP
`422 Unprocessable Entity`.

Cars are matched the same way, so `C2`, `c2`, and ` C2 ` are the same car. Each
car holds at most one time per track.

## List the cars

```bash
curl http://127.0.0.1:8000/v1/leaderboard/cars
```

```json
{"cars": [{"id": "c2", "name": "c2"}, {"id": "杰弟", "name": "杰弟"}]}
```

Every car holding a time anywhere, ordered by name. This is what fills the car
selector in JasonApp, so a car already recorded elsewhere is picked from the
list instead of retyped. A car written several ways (`C2` and `c2`) is one
entry, reported under its most-used spelling, with ties broken alphabetically.

The endpoint reads the `times` collection group, so its cost grows with the
number of recorded times rather than the number of maps.

## Add a map

```bash
curl -X POST http://127.0.0.1:8000/v1/leaderboard/maps \
  -H 'Content-Type: application/json' \
  -d '{"name":"New York","tracks":["A park In A run","Harbor Sprint"]}'
```

Exactly two track names are required. The endpoint responds with HTTP
`201 Created` and the new map's empty leaderboards:

```json
{
  "id": "new-york",
  "name": "New York",
  "tracks": [
    {"id": "a-park-in-a-run", "name": "A park In A run", "times": []},
    {"id": "harbor-sprint", "name": "Harbor Sprint", "times": []}
  ]
}
```

A map whose name is already taken responds with HTTP `409 Conflict`.

## List the maps

```bash
curl http://127.0.0.1:8000/v1/leaderboard/maps
```

```json
{"maps": [{"id": "san-francisco", "name": "San Francisco", "chinese_name": "旧金山"}]}
```

Maps are listed in the game's release order, which is the order the JasonApp
map selector shows them in. That order is the `release_order` field on each map
document; a map without one sorts after every map that has one, by name. The
sort runs in the service rather than as a Firestore `order_by`, because an
`order_by` silently drops documents that lack the field.

`chinese_name` is the map's Chinese name, which JasonApp appends to the English
one — `San Francisco (旧金山)`. Tracks carry the same field; it is blank until
filled in. Both are optional, and a map created through this API starts with a
blank `chinese_name` and no release order.

## Read a map's leaderboards

```bash
curl http://127.0.0.1:8000/v1/leaderboard/maps/new-york
```

Each track lists every car that holds a time on it, fastest first and
ranked from one:

```json
{
  "id": "new-york",
  "name": "New York",
  "tracks": [
    {
      "id": "a-park-in-a-run",
      "name": "A park In A run",
      "times": [
        {"car": "C2", "seconds": 19.62, "rank": 1},
        {"car": "C5", "seconds": 20.14, "rank": 2}
      ]
    },
    {"id": "harbor-sprint", "name": "Harbor Sprint", "times": []}
  ]
}
```

## List every track

```bash
curl http://127.0.0.1:8000/v1/leaderboard/tracks
```

```json
{"tracks": [
  {"id": "railroad-bustle", "name": "Railroad Bustle", "chinese_name": "喧闹铁路",
   "map_id": "san-francisco", "map_name": "San Francisco", "map_chinese_name": "旧金山"}
]}
```

All 36 tracks with the map each belongs to, in map release order and then the
map's own track order. This fills the track selectors in JasonApp, which send
the identifiers straight back to the lookup below.

Names come from the track documents, so the list is one collection-group read
on top of the cached map list. It is deliberately not cached itself: a separate
cache key would not be invalidated by the Firestore watcher and could go stale
behind a console edit.

## Look up tracks by name

```bash
curl -X POST http://127.0.0.1:8000/v1/leaderboard/tracks/lookup \
  -H 'Content-Type: application/json' \
  -d '{"names":["WATERSLIDE WHIRL","LEAP OF FAITH","NOT A TRACK"]}'
```

```json
{
  "tracks": [
    {
      "id": "waterslide-whirl",
      "name": "Waterslide Whirl",
      "chinese_name": "滑水道旋流",
      "map_id": "singapore",
      "map_name": "Singapore",
      "map_chinese_name": "新加坡",
      "requested_name": "WATERSLIDE WHIRL",
      "times": [{"car": "狼", "seconds": 21.057, "rank": 1}]
    }
  ],
  "unmatched": ["NOT A TRACK"]
}
```

Built for a line-up read off a screenshot with the
[text recognition API](text_recognition.md): the names arrive as text, the
tracks they name usually belong to different maps, and some names will not
match anything. Results keep the order asked for, each carries the map it
belongs to and the `requested_name` it was matched from, and names that matched
nothing come back in `unmatched` rather than being dropped silently.

Identifiers work as input too, which is what the track selectors send.

Matching tries the derived identifier first, then the name reduced to letters
and digits, so `ITS A TWISTER` finds `It's a Twister!` — punctuation is what
optical recognition gets wrong most often. A track's Chinese name matches too.
Track names are read from the track documents, so a name only recorded there
still resolves.

One read covers the whole track index, and one per distinct map covers the
times, so a five-track line-up spanning five maps costs six reads rather than
one per track — and the map reads come from the Redis cache when warm.

## Record a car's time

```bash
curl -X PUT \
  http://127.0.0.1:8000/v1/leaderboard/maps/new-york/tracks/a-park-in-a-run/times \
  -H 'Content-Type: application/json' \
  -d '{"car":"C2","seconds":19.62}'
```

The request replaces whatever time the car already holds on that track, even a
faster one, and responds with the track's refreshed leaderboard. Times are
recorded in seconds, rounded to three decimal places.

## Delete a car's time

```bash
curl -X DELETE \
  http://127.0.0.1:8000/v1/leaderboard/maps/new-york/tracks/a-park-in-a-run/times/C2
```

The response is the track's refreshed leaderboard. A car with no time on the
track responds with HTTP `404 Not Found`.

## Caching

Reading a map costs four Firestore round trips, so `GET` results are cached in
Redis under `leaderboard:maps`, `leaderboard:cars`, and
`leaderboard:map:{map_id}`. A warm read is roughly a thousand times faster than
a cold one.

Writes through this API clear the keys they affect. That alone is not enough,
because maps and tracks are also edited directly in the Firebase console, and
those edits never reach this API. So the cache is kept honest by change data
capture: `LeaderboardCacheWatcher` in `src/infrastructure/cache_watcher.py`
subscribes to Firestore itself — the `maps` collection and the `tracks` and
`times` collection groups — and clears the keys a changed document makes stale,
whoever wrote it. A console edit reaches the app in about a tenth of a second.

The listener runs inside the API process rather than as a Cloud Function
trigger, because a function running in Google's cloud cannot reach a Redis
listening on `127.0.0.1`.

`LEADERBOARD_CACHE_TTL_SECONDS` (default 300) is the backstop for anything the
listener misses, such as changes made while the API is stopped. Without
Firestore credentials the API still starts, and the cache falls back to
expiring on that TTL alone.

## Storage layout

```text
maps/{map_id}                                  id, name, chinese_name,
                                               release_order, tracks[]
maps/{map_id}/tracks/{track_id}                id, name, chinese_name
maps/{map_id}/tracks/{track_id}/times/{car_id} car, seconds
```

The map document carries both tracks so one read renders the whole selector and
both leaderboards. That array fixes which tracks a map has and the order they
appear in; each track's own document owns its `name` and `chinese_name`, so
there is one obvious place to edit them and no duplicated value to drift. A
detail missing from the track document falls back to the array. Each track's times are a subcollection, so a track's times
are a single ordered query and one car's time can be replaced or deleted without
rewriting the others. Creating a map writes the map and its two track documents
in one batch, which also makes the duplicate-name check atomic.

`LeaderboardService` in `src/services/leaderboard.py` owns this layout and runs
the blocking Firestore calls on worker threads. The router in
`src/routers/leaderboard.py` translates its errors into status codes.

See the [Firestore reference](../depdency/firestore_reference.md) for local
authentication and configuration.
