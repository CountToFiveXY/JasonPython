from uuid import uuid4

from fastapi import FastAPI


app = FastAPI(title="Message API")


@app.get("/")
def extend_text(text: str) -> dict[str, str]:
    identifier = str(uuid4())
    extended_text = f"{text}-{identifier}"
    print(extended_text)
    return {"message": extended_text}
