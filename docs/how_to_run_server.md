# How to Run the Server

Follow this guide from the project root when setting up the application for the
first time. The local environment includes Redis, Kafka, a Kafka message worker,
Temporal Server, a Temporal worker, and FastAPI.

The order API also requires credentials for the `jasonapp-xm0830` Firebase
project. Before starting locally, set `GOOGLE_APPLICATION_CREDENTIALS` to the
absolute path of a service-account JSON file stored outside this repository:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
```

## First-time setup

### 1. Download the project

Skip the clone command if you already have the project. Otherwise:

```bash
git clone git@github.com:CountToFiveXY/JasonPython.git  # Download the project from GitHub.
cd JasonPython  # Enter the project root directory.
```

All remaining commands assume your terminal is in the project root.

### 2. Install Homebrew

The startup script installs Redis, Temporal, and Python automatically when they
are missing. Homebrew itself must already be available:

```bash
brew --version
```

If Homebrew is not installed, get it from <https://brew.sh>.

## Start the complete local environment

Run one command from the project root:

```bash
./scripts/run_local.sh  # Start Redis, Temporal Server, the worker, and FastAPI.
```

Leave this terminal open. The script:

1. Installs missing Homebrew dependencies, including Kafka.
2. Creates `.venv` and installs Python requirements when needed.
3. Starts Redis, unless Redis is already running.
4. Starts Kafka, creates the message topic, and starts its consumer worker.
5. Starts Temporal Server, unless it is already running.
6. Starts the Python Temporal worker.
7. Starts FastAPI on port 8000, falling back to 8088 and then 8888 when busy.

An existing Redis or Temporal Server instance is reused and will not be stopped
by the script. By default, Redis saves its snapshot to the parent workspace at
`/Users/sword23/Workspace/redis/dump.rdb`.

## Verify the application

Wait until the startup output says that FastAPI is running. It prints the
selected URL. With the preferred port, open:

- FastAPI documentation: <http://127.0.0.1:8000/docs>
- Health endpoint: <http://127.0.0.1:8000/health>
- Temporal Web UI: <http://127.0.0.1:8233>

Run a Temporal workflow from another terminal:

```bash
curl -X POST http://127.0.0.1:8000/workflows/hello
# Start the hello workflow; the worker prints "Hello there" and returns it.
```

Create an order and start its workflow:

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
# Create an order in Firestore and start its Temporal workflow.
```

The response contains the order ID, creation time, and matching workflow ID.
Search for that ID in the Temporal Web UI to inspect its event history.

Other available endpoints are documented in
[How to call the API](how_to_call_api.md).

Publish a Kafka message:

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"id":"ORDER_ID_FROM_RESPONSE","status":"SUCCESS"}'
```

## Stop the complete local environment

Press `Control+C` in the terminal running `run_local.sh`. The script stops the
worker, FastAPI, and any Redis or Temporal Server process that it started.

## Manual startup

Use this sequence when troubleshooting individual components. Keep each
foreground process open in its own terminal.

### Terminal 1: Redis

```bash
export REDIS_DATA_DIR=/Users/sword23/Workspace/redis  # Select the directory for dump.rdb.
redis-server --daemonize yes --dir "$REDIS_DATA_DIR" --dbfilename dump.rdb  # Start Redis with persistent snapshot storage.
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
python -m src.temporal.worker  # Poll for and execute Temporal workflow tasks.
```

### Terminal 4: FastAPI

```bash
source .venv/bin/activate  # Make this terminal use the project's Python environment.
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000  # Start the FastAPI development server.
```

Kafka must also be running on port `9092`, and the Kafka consumer can be run
manually with `python -m src.messaging.worker`.

See the [Temporal reference](depdency/temporal_reference.md) for namespace,
address, and task-queue configuration.

## Troubleshooting

- `Homebrew is required`: install Homebrew from <https://brew.sh>.
- A package installation failure: review the command output, fix the reported
  Homebrew or pip issue, and run the same startup script again.
- Ports 8000, 8088, and 8888 are all busy: stop one conflicting process or set
  `FASTAPI_PORT` to another available port.
- `Error 61 connecting to 127.0.0.1:6379`: Redis is not running or is using a
  different address.
- A connection error for `127.0.0.1:7233`: Temporal Server is not running.
- A connection error for `127.0.0.1:9092`: Kafka is not running or the
  configured broker address is incorrect.
- A workflow request waits indefinitely: the Temporal worker is not running or
  its namespace or task queue does not match FastAPI.
- `DefaultCredentialsError`: set `GOOGLE_APPLICATION_CREDENTIALS` to a valid
  service-account JSON file for the Firebase project.

## Access from another device

Find the Mac's Wi-Fi IP address:

```bash
ipconfig getifaddr en0  # Print the Mac's Wi-Fi IP address.
```

Replace `YOUR_MAC_IP` in the application URLs, for example:

```text
http://YOUR_MAC_IP:8000/docs
http://YOUR_MAC_IP:8000/health
```

The macOS firewall and local network must allow incoming connections.
