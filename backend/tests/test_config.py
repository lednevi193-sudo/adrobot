"""Настройки: CAMPAIGN_PREFIX обязателен и не может остаться плейсхолдером (NFR-4)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {"keitaro_url": "https://keitaro.test", "keitaro_api_key": "k", "database_url": "postgresql+psycopg://x"}


@pytest.mark.parametrize("prefix", ["", "   ", "test_<фамилия>_"])
def test_prefix_must_be_real(prefix: str) -> None:
    with pytest.raises(ValidationError, match="CAMPAIGN_PREFIX"):
        Settings(_env_file=None, **BASE, campaign_prefix=prefix)


def test_prefix_is_trimmed() -> None:
    assert Settings(_env_file=None, **BASE, campaign_prefix=" test_ivanov_ ").campaign_prefix == "test_ivanov_"
