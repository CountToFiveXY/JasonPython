# How to Run the Server

## Install dependencies

From the project directory, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start Redis and confirm that it responds with `PONG` by following
[How to run Redis](how_to_run_redis.md).

## Start the server

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

The `--reload` option automatically restarts the development server after code
changes. Do not use it for a production deployment.

## Open the application

On the Mac running the server:

- URL shortening API: <http://127.0.0.1:8080/tinyUrl?url=https://example.com>
- Image API: <http://127.0.0.1:8080/display>
- Health API: <http://127.0.0.1:8080/health>
- Interactive documentation: <http://127.0.0.1:8080/docs>

To call the server from another device on the same local network, find the
Mac's Wi-Fi IP address:

```bash
ipconfig getifaddr en0
```

Replace `YOUR_MAC_IP` in these addresses:

```text
http://YOUR_MAC_IP:8080/tinyUrl?url=https://example.com
http://YOUR_MAC_IP:8080/display
http://YOUR_MAC_IP:8080/health
http://YOUR_MAC_IP:8080/docs
```

Your macOS firewall and network settings must allow incoming connections.

## Stop the server

Press `Control+C` in the terminal running Uvicorn.
