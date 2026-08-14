from fastapi import FastAPI


app = FastAPI(title="Message API")


@app.get("/")
def print_message() -> dict[str, str]:
    message = "Hello from FastAPI!"
    print(message)
    return {"message": message}
