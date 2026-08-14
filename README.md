# Message API

Install the dependencies and start the server:

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --reload
```

Then open <http://127.0.0.1:8000/>. The API returns:

```json
{"message": "Hello from FastAPI!"}
```

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.
