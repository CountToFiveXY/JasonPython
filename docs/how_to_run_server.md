# How to Run the Server

Follow this guide from the project root when setting up the application for the
first time. The local environment includes Redis, Kafka, a Kafka message worker,
Temporal Server, a Temporal worker, and FastAPI.

The backend reads Firestore and calls Cloud Vision in the `jasonapp-xm0830`
Google Cloud project, so **each laptop needs its own service account**. See
[step 3](#3-create-this-laptops-google-cloud-service-account).

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

### 3. Create this laptop's Google Cloud service account

Each laptop gets its own service account, created by hand in the
[Google Cloud console](https://console.cloud.google.com/) for project
`jasonapp-xm0830`:

1. **IAM & Admin** → **Service Accounts** → **Create service account**
2. **Service account name**: `jasonapp-<laptop>`, e.g. `jasonapp-yuqiao-mbp` →
   **Create and continue**
3. **Grant this service account access to project** → add these roles →
   **Continue** → **Done**
   - **Cloud Datastore User** (Firestore)
   - **Service Usage Consumer** (Cloud Vision)
4. Open the new account → **Keys** → **Add key** → **Create new key** →
   **JSON** → **Create**

Move the downloaded key to where `scripts/run_local.sh` looks for it:

```bash
mkdir -p ~/.config/jasonapp
mv ~/Downloads/jasonapp-xm0830-*.json ~/.config/jasonapp/service-account.json
chmod 600 ~/.config/jasonapp/service-account.json
```

Never commit the key or copy it to another laptop. To retire a laptop, delete
its service account in the same page.

## Start only the core services

```bash
./scripts/run_local.sh --core  # Start Redis and FastAPI only.
```

The core startup runs Redis and FastAPI, which reads Firestore. It does not
install, start, or wait for Kafka, Temporal, or their workers. FastAPI gives
Temporal and Kafka five seconds each to connect and then starts without them:
the workflow and order APIs (Temporal) and the messages API (Kafka) return
`503` saying the service is not running, `/health` reports `kafka:
"unavailable"`, and everything else works. JasonApp runs this when it opens
and the backend is down.

Run the script without `--core` to start everything; it stops the core
session first.

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

Running the script again stops the previous session first, so it always
starts the checkout's current code. FastAPI does not reload on its own when
code changes; run the script again, or click **Restart Services** on
JasonApp's Server pane, which runs this script for you.

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
- `DefaultCredentialsError`: this laptop has no service-account key. Follow
  [step 3](#3-create-this-laptops-google-cloud-service-account), or set
  `GOOGLE_APPLICATION_CREDENTIALS` to the absolute path of this laptop's key.
- `403 Permission denied` from Firestore or Cloud Vision: the laptop's account
  is missing one of the two roles in step 3.

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
