from fastapi import FastAPI

from routers import health, messages, url_shortening


app = FastAPI(title="Message APIs")

app.include_router(url_shortening.router)
app.include_router(messages.router)
app.include_router(health.router)
