# Redis Reference

This project uses Redis Open Source as its local backend database. The default
connection is `redis://127.0.0.1:6379/0`.

For the complete local startup sequence, follow
[How to run the server](../how_to_run_server.md). This page contains additional
Redis inspection and configuration commands.

## Snapshot location

The local startup script stores the Redis RDB snapshot at:

```text
/Users/sword23/Workspace/redis/dump.rdb
```

The script defaults `REDIS_DATA_DIR` to a `redis` directory alongside the
project and creates it when necessary. Override it before startup to use
another writable directory:

```bash
export REDIS_DATA_DIR=/another/path  # Select the directory that will contain dump.rdb.
./scripts/run_local.sh  # Start the local environment with the selected Redis directory.
```

If Redis is already running with a different data directory, stop it before
running the script. The script will not silently change or stop a Redis instance
that it did not start.

## Check the connection

```bash
/opt/homebrew/bin/redis-cli ping  # Confirm Redis is reachable; it should return PONG.
```

## Inspect stored URLs

```bash
/opt/homebrew/bin/redis-cli SCAN 0 MATCH 'short_url:*'  # List URL-shortener keys without blocking Redis.
```

To retrieve a known mapping, replace the example code:

```bash
/opt/homebrew/bin/redis-cli GET short_url:Ab12Cd34  # Retrieve the original URL for one short code.
```

## Stop Redis

```bash
/opt/homebrew/bin/redis-cli shutdown  # Save Redis data and stop the server cleanly.
```

## Use a different Redis server

Set `REDIS_URL` before starting FastAPI:

```bash
export REDIS_URL=redis://127.0.0.1:6379/0  # Select the Redis database used by FastAPI.
```

Set `REDIS_URL` in the terminal before starting FastAPI. The application checks
the connection during startup and exits if Redis is unavailable.

## Troubleshooting

If FastAPI reports `Error 61 connecting to 127.0.0.1:6379`, Redis is not
listening at the configured address. Start Redis using the main server guide or
set `REDIS_URL` to a reachable Redis instance.
