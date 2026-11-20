"""Раздача собранного фронта (frontend/dist) тем же FastAPI (NFR-1).

≈ UseStaticFiles + MapFallbackToFile("index.html") в ASP.NET Core: файл из dist,
если он есть, иначе index.html — маршруты SPA (/campaigns/42) разбирает Vue Router.
/api и /docs не перехватываются: их маршруты зарегистрированы раньше, а неизвестный
/api/... отвечает JSON 404, а не страницей фронта.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# app/spa.py -> app -> backend -> корень репозитория
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

API_PREFIX = "api"


def mount_spa(app: FastAPI, dist: Path = FRONTEND_DIST) -> bool:
    """Подключить фронт, если он собран. Регистрировать последним: маршрут ловит всё."""
    index = dist / "index.html"
    if not index.is_file():
        return False
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == API_PREFIX or path.startswith(API_PREFIX + "/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):  # не выпускаем за пределы dist
            return FileResponse(file)
        return FileResponse(index)

    return True
