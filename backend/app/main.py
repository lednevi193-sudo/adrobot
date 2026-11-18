from fastapi import FastAPI

from app.api import health

app = FastAPI(title="Adrobot — Keitaro wrapper")

app.include_router(health.router, prefix="/api")
