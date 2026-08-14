# How to Run Redis

This project uses Redis Open Source as its local backend database. The default
connection is `redis://127.0.0.1:6379/0`.

Redis must be running before FastAPI starts because the application verifies
the database connection during startup.

## Start Redis

```bash
/opt/homebrew/bin/redis-server /opt/homebrew/etc/redis.conf --daemonize yes
```

## Verify Redis

```bash
/opt/homebrew/bin/redis-cli ping
```

A working server responds with `PONG`.

## Inspect stored URLs

```bash
/opt/homebrew/bin/redis-cli SCAN 0 MATCH 'short_url:*'
```

To retrieve a known mapping, replace the example code:

```bash
/opt/homebrew/bin/redis-cli GET short_url:Ab12Cd34
```

## Stop Redis

```bash
/opt/homebrew/bin/redis-cli shutdown
```

## Use a different Redis server

Set `REDIS_URL` before starting FastAPI:

```bash
export REDIS_URL=redis://127.0.0.1:6379/0
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```
