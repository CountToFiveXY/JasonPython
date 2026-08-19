from fastapi import FastAPI

from database import lifespan
from routers import health, messages, temporal_workflows, url_shortening


app = FastAPI(title="Utility APIs", lifespan=lifespan)

app.include_router(url_shortening.router)
app.include_router(temporal_workflows.router)
app.include_router(messages.router)
app.include_router(health.router)
