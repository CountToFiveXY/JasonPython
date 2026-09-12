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
{"maps": [{"id": "new-york", "name": "New York"}]}
```

Maps are ordered by name, which is the order the JasonApp map selector shows.

## Read a map's leaderboards

```bash
curl http://127.0.0.1:8000/v1/leaderboard/maps/new-york
```

Each track lists its five fastest cars, ranked from one:

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

## Storage layout

```text
maps/{map_id}                                  id, name, tracks[]
maps/{map_id}/tracks/{track_id}                id, name
maps/{map_id}/tracks/{track_id}/times/{car_id} car, seconds
```

The map document carries both tracks so one read renders the whole selector and
both leaderboards. Each track's times are a subcollection, so a track's top five
is a single ordered query and one car's time can be replaced or deleted without
rewriting the others. Creating a map writes the map and its two track documents
in one batch, which also makes the duplicate-name check atomic.

`LeaderboardService` in `src/services/leaderboard.py` owns this layout and runs
the blocking Firestore calls on worker threads. The router in
`src/routers/leaderboard.py` translates its errors into status codes.

See the [Firestore reference](../depdency/firestore_reference.md) for local
authentication and configuration.
