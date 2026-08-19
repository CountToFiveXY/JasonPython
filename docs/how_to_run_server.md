# How to Run the Server

This is the main startup guide. A complete local environment consists of four
processes:

1. Redis
2. Temporal Server
3. The Temporal worker
4. The FastAPI server

Keep each process running in its own terminal.

## 1. Install dependencies

From the project directory, create and activate a virtual environment:

```bash
python3 -m venv .venv  # Create an isolated Python environment for this project.
source .venv/bin/activate  # Make this terminal use the environment's Python and packages.
python -m pip install -r requirements.txt  # Install the project's Python dependencies.
```

Install Redis and the Temporal CLI on macOS if they are not already installed:

```bash
brew install redis temporal  # Install the Redis server and Temporal CLI on macOS.
```

## 2. Start Redis

In the first terminal:

```bash
/opt/homebrew/bin/redis-server /opt/homebrew/etc/redis.conf --daemonize yes  # Start Redis in the background using its Homebrew configuration.
/opt/homebrew/bin/redis-cli ping  # Confirm that Redis is running; it should return PONG.
```

The second command must respond with `PONG`. See
[Redis reference](depdency/redis_reference.md) for configuration and inspection
commands.

## 3. Start Temporal Server

**In the second terminal**, start Temporal Server:

```bash
temporal server start-dev  # Start a local development Temporal Server and Web UI.
```

This starts the local Temporal service at `127.0.0.1:7233` and its Web UI at
<http://127.0.0.1:8233>. Keep this terminal open.

## 4. Start the Temporal worker

**In the third terminal**, activate the project environment and start the
Temporal worker:

```bash
source .venv/bin/activate  # Make this terminal use the project's Python environment.
python -m temporal_service.worker  # Start the worker that executes Temporal workflows and activities.
```

The worker polls the `utility-api` task queue and executes the application's
workflows and activities. Keep this terminal open.

## 5. Start FastAPI

In the fourth terminal, activate the project environment and start Uvicorn:

```bash
source .venv/bin/activate  # Make this terminal use the project's Python environment.
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080  # Start FastAPI and reload it when source files change.
```

The `--reload` option automatically restarts the development server after code
changes. Do not use it for a production deployment.

## 6. Verify the application

On the Mac running the server:

- URL shortening API: <http://127.0.0.1:8080/tinyUrl?url=https://example.com>
- Temporal workflow API: `POST http://127.0.0.1:8080/workflows/greeting`
- Image API: <http://127.0.0.1:8080/display>
- Health API: <http://127.0.0.1:8080/health>
- Interactive documentation: <http://127.0.0.1:8080/docs>

Run a Temporal workflow:

```bash
curl -X POST http://127.0.0.1:8080/workflows/greeting \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jason"}'
# Start a greeting workflow through FastAPI and wait for its result.
```

The response includes a workflow ID. Open the
[Temporal Web UI](http://127.0.0.1:8233) to inspect its event history. See
[Temporal reference](depdency/temporal_reference.md) for configuration details.

To call the server from another device on the same local network, find the
Mac's Wi-Fi IP address:

```bash
ipconfig getifaddr en0  # Print the Mac's Wi-Fi IP address for access from another device.
```

Replace `YOUR_MAC_IP` in these addresses:

```text
http://YOUR_MAC_IP:8080/tinyUrl?url=https://example.com
http://YOUR_MAC_IP:8080/display
http://YOUR_MAC_IP:8080/health
http://YOUR_MAC_IP:8080/docs
```

Your macOS firewall and network settings must allow incoming connections.

## Stop the local environment

Press `Control+C` in the FastAPI, Temporal worker, and Temporal Server
terminals. Stop the background Redis process with:

```bash
/opt/homebrew/bin/redis-cli shutdown  # Ask Redis to save its data and stop cleanly.
```

## Troubleshooting

- `Error 61 connecting to 127.0.0.1:6379`: Redis is not running. Repeat step 2.
- Temporal connection errors for `127.0.0.1:7233`: Temporal Server is not
  running. Repeat step 3.
- A workflow request waits indefinitely: confirm the Temporal worker from step
  4 is running and uses the same task queue as the API.
