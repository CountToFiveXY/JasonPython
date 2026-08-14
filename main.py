from fastapi import FastAPI

from routers import health, messages, uuid_messages


app = FastAPI(title="Message APIs")

app.include_router(uuid_messages.router)
app.include_router(messages.router)
app.include_router(health.router)
