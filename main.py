from fastapi import FastAPI

from infrastructure.clients import lifespan
from routers import greeting, health, hello, messages, ranking, url_shortening


app = FastAPI(title="Utility APIs", lifespan=lifespan)

app.include_router(hello.router)
app.include_router(greeting.router)
app.include_router(messages.router)
app.include_router(health.router)
app.include_router(url_shortening.router)
app.include_router(ranking.router)
