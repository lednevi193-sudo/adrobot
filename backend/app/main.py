"""Сборка приложения FastAPI (≈ Program.cs): роутеры и обработчики ошибок."""

from fastapi import FastAPI

from app.api.routers import campaigns, health, offers, streams
from app.api.errors import register_error_handlers

app = FastAPI(title="Adrobot — Keitaro wrapper")

register_error_handlers(app)
for router in (health.router, offers.router, campaigns.router, streams.router):
    app.include_router(router, prefix="/api")
