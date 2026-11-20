"""Сборка приложения FastAPI (≈ Program.cs): роутеры, обработчики ошибок, статика фронта."""

from collections.abc import Sequence

from fastapi import APIRouter, FastAPI

from app.api.routers import campaigns, health, offers, streams
from app.api.errors import register_error_handlers
from app.spa import mount_spa

def create_app(*, demo: bool = False, additional_routers: Sequence[APIRouter] = ()) -> FastAPI:
    app = FastAPI(title="Adrobot — DEMO" if demo else "Adrobot — Keitaro wrapper")

    register_error_handlers(app)
    routers = (offers.router, campaigns.router, streams.router)
    if not demo:
        app.include_router(health.router, prefix="/api")
    else:
        @app.get("/api/health", tags=["health"])
        def demo_health():
            return {"status": "ok", "storage": "memory", "mode": "demo"}

    for router in (*routers, *additional_routers):
        app.include_router(router, prefix="/api")

    @app.get("/api/runtime", tags=["runtime"])
    def runtime():
        return {"mode": "demo" if demo else "live"}

    mount_spa(app)  # последним: ловит все остальные пути; без frontend/dist ничего не делает
    return app


app = create_app()
