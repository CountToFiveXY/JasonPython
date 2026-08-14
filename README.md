# Message API

Install the dependencies:

```bash
python3 -m pip install -r requirements.txt
```
start the server

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

On this Mac, open <http://127.0.0.1:8080/>.

From another device on the same Wi-Fi network, replace `YOUR_MAC_IP` with
your Mac's local IP address and open:

```text
http://YOUR_MAC_IP:8080/
```

For example: `http://192.168.1.25:8080/`

The API returns:

```json
{"message": "Hello from FastAPI!"}
```

Interactive API documentation is available at:

- On this Mac: <http://127.0.0.1:8080/docs>
- On another device: `http://YOUR_MAC_IP:8080/docs`

To find your Mac's Wi-Fi IP address, run:

```bash
ipconfig getifaddr en0
```
