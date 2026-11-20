"""Сценарии приложения тестируются на фейках портов: без сети и без Postgres."""

import pytest

from tests.application.world import World, make_world


@pytest.fixture
def world() -> World:
    return make_world()
