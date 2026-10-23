from fastapi import FastAPI

from src.infrastructure.clients import lifespan
from src.routers import (
    file_transfer,
    leaderboard,
    health,
    hello,
    image,
    gauntlet,
    messages,
    order,
    text_recognition,
    url_shortening,
)


app = FastAPI(title="Utility APIs", lifespan=lifespan)

app.include_router(hello.router)
app.include_router(order.router)
app.include_router(image.router)
app.include_router(health.router)
app.include_router(url_shortening.router)
app.include_router(leaderboard.router)
app.include_router(messages.router)
app.include_router(gauntlet.router)
app.include_router(text_recognition.router)
app.include_router(file_transfer.router)
