"""HTTP-тесты: настоящее приложение FastAPI, порты подменены фейками.

app.dependency_overrides ≈ WebApplicationFactory.ConfigureTestServices в ASP.NET.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies as deps
from app.main import app
from tests.application.world import PREFIX, World, make_world


@pytest.fixture
def world() -> World:
    return make_world()


@pytest.fixture
def client(world: World) -> Iterator[TestClient]:
    app.dependency_overrides = {
        deps.get_repository: lambda: world.repo,
        deps.get_unit_of_work: lambda: world.uow,
        deps.get_keitaro: lambda: world.keitaro,
        deps.get_prefix: lambda: PREFIX,
    }
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}
