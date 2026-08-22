# How to Run the Server

Follow this guide from the project root when setting up the application for the
first time. The local environment includes Redis, Temporal Server, a Temporal
worker, and FastAPI.

## First-time setup

### 1. Download the project

Skip the clone command if you already have the project. Otherwise:

```bash
git clone git@github.com:CountToFiveXY/JasonPython.git  # Download the project from GitHub.
cd JasonPython  # Enter the project root directory.
```

All remaining commands assume your terminal is in the project root.

### 2. Install the system dependencies

On macOS with Homebrew:

```bash
brew install redis temporal  # Install Redis and the Temporal command-line tool.
```

Confirm that Python 3 is installed:

```bash
python3 --version  # Print the installed Python version.
```

### 3. Create the Python environment

Run these commands from the project root:

```bash
python3 -m venv .venv  # Create an isolated Python environment in the project.
source .venv/bin/activate  # Make this terminal use the new Python environment.
python -m pip install -r requirements.txt  # Install FastAPI, Redis, Temporal, and Uvicorn packages.
```

You only need to create the virtual environment once. The startup script uses
`.venv/bin/python` directly, so you do not need to activate the environment
again before running it.

## Start the complete local environment

Run one command from the project root:

```bash
./scripts/run_local.sh  # Start Redis, Temporal Server, the worker, and FastAPI.
```

Leave this terminal open. The script:

1. Starts Redis, unless Redis is already running.
2. Starts Temporal Server, unless it is already running.
3. Starts the Python Temporal worker.
4. Starts FastAPI with automatic reload enabled.

An existing Redis or Temporal Server instance is reused and will not be stopped
by the script.

## Verify the application

Wait until the startup output says that FastAPI is running. Then open:

- FastAPI documentation: <http://127.0.0.1:8080/docs>
- Health endpoint: <http://127.0.0.1:8080/health>
- Temporal Web UI: <http://127.0.0.1:8233>

Run a Temporal workflow from another terminal:

```bash
curl -X POST http://127.0.0.1:8080/workflows/hello
# Start the hello workflow; the worker prints "Hello there" and returns it.
```

Run the greeting workflow with a custom name:

```bash
curl -X POST http://127.0.0.1:8080/workflows/greeting \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jason"}'
# Start a greeting workflow through FastAPI and wait for its result.
```

The response contains a workflow ID and greeting result. Search for the
workflow ID in the Temporal Web UI to inspect its event history.

Other available endpoints are documented in
[How to call the API](how_to_call_api.md).

## Stop the complete local environment

Press `Control+C` in the terminal running `run_local.sh`. The script stops the
worker, FastAPI, and any Redis or Temporal Server process that it started.

## Manual startup

Use this sequence when troubleshooting individual components. Keep each
foreground process open in its own terminal.

### Terminal 1: Redis

```bash
redis-server --daemonize yes  # Start Redis in the background.
redis-cli ping  # Confirm Redis is running; it should return PONG.
```

See the [Redis reference](depdency/redis_reference.md) for inspection and
configuration commands.

### Terminal 2: Temporal Server

```bash
temporal server start-dev  # Start Temporal Server and its local Web UI.
```

### Terminal 3: Temporal worker

```bash
source .venv/bin/activate  # Make this terminal use the project's Python environment.
python -m temporal.worker  # Poll for and execute Temporal workflow tasks.
```

### Terminal 4: FastAPI

```bash
source .venv/bin/activate  # Make this terminal use the project's Python environment.
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080  # Start the FastAPI development server.
```

See the [Temporal reference](depdency/temporal_reference.md) for namespace,
address, and task-queue configuration.

## Troubleshooting

- `Required command not found`: install the missing system dependency from
  step 2.
- `Python virtual environment not found`: complete step 3 from the project
  root.
- `Error 61 connecting to 127.0.0.1:6379`: Redis is not running or is using a
  different address.
- A connection error for `127.0.0.1:7233`: Temporal Server is not running.
- A workflow request waits indefinitely: the Temporal worker is not running or
  its namespace or task queue does not match FastAPI.

## Access from another device

Find the Mac's Wi-Fi IP address:

```bash
ipconfig getifaddr en0  # Print the Mac's Wi-Fi IP address.
```

Replace `YOUR_MAC_IP` in the application URLs, for example:

```text
http://YOUR_MAC_IP:8080/docs
http://YOUR_MAC_IP:8080/health
```

The macOS firewall and local network must allow incoming connections.
