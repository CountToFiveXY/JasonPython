# Run Temporal locally

The API connects to Temporal at `127.0.0.1:7233` and uses the `default`
namespace unless environment variables override those values.

## 1. Install the dependencies

```bash
python -m pip install -r requirements.txt
```

Install the Temporal CLI on macOS if it is not already available:

```bash
brew install temporal
```

## 2. Start the local Temporal server

```bash
temporal server start-dev
```

The Temporal Web UI is available at <http://127.0.0.1:8233>.

## 3. Start the worker

In another terminal, from the project root:

```bash
python -m temporal_service.worker
```

## 4. Start the API

Redis must also be running. Then start FastAPI:

```bash
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```

## 5. Run a workflow through the API

```bash
curl -X POST http://127.0.0.1:8080/workflows/greeting \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jason"}'
```

The response includes the workflow ID. Search for that ID in the Temporal Web
UI to inspect its event history.

## Configuration

Both the API and worker recognize these environment variables:

| Variable | Default |
| --- | --- |
| `TEMPORAL_ADDRESS` | `127.0.0.1:7233` |
| `TEMPORAL_NAMESPACE` | `default` |
| `TEMPORAL_TASK_QUEUE` | `utility-api` |

The API and worker must use the same namespace and task queue.
