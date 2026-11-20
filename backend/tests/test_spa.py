"""Раздача собранного фронта: файлы, fallback на index.html, /api и /docs не перехвачены."""

from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.spa import mount_spa


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=app></div>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("secret", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(dist: Path) -> TestClient:
    app = FastAPI()
    api = APIRouter(prefix="/api")
    api.add_api_route("/health", lambda: {"status": "ok"})
    app.include_router(api)
    assert mount_spa(app, dist)
    return TestClient(app)


def test_serves_built_file(client: TestClient) -> None:
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log(1)"


@pytest.mark.parametrize("path", ["/", "/campaigns", "/campaigns/42", "/create"])
def test_spa_routes_fall_back_to_index(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert "<div id=app>" in response.text


def test_api_still_works_and_unknown_api_is_json_404(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_docs_not_shadowed(client: TestClient) -> None:
    assert "swagger" in client.get("/docs").text.lower()
    assert client.get("/openapi.json").status_code == 200


def test_no_escape_from_dist(client: TestClient) -> None:
    response = client.get("/..%2Fsecret.txt")
    assert "secret" not in response.text


def test_without_dist_nothing_is_mounted(tmp_path: Path) -> None:
    app = FastAPI()
    assert mount_spa(app, tmp_path / "missing") is False
    assert TestClient(app).get("/campaigns").status_code == 404
