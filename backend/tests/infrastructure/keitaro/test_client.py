"""Транспорт: заголовки и перевод сбоев Keitaro в понятные ошибки (NFR-3, FR-1.8)."""

import httpx
import pytest

from app.application.errors import KeitaroError, KeitaroUnavailable
from app.infrastructure.keitaro import KeitaroClient
from tests.infrastructure.keitaro.stub import KeitaroStub, settings


def test_sends_api_key_and_explicit_user_agent() -> None:
    stub = KeitaroStub()
    stub.on("GET", "/offers", [])

    stub.client().get("/offers")

    headers = stub.requests[0].headers
    assert headers["Api-Key"] == "test-key"
    assert headers["User-Agent"] == "keitaro-wrapper/0.1"  # без него Cloudflare отвечает 403
    assert str(stub.requests[0].url) == "https://keitaro.test/admin_api/v1/offers"


def test_keitaro_error_text_reaches_the_user() -> None:
    stub = KeitaroStub()
    stub.on("POST", "/offers", {"error": "You have no permission"}, status=403)

    with pytest.raises(KeitaroError) as exc:
        stub.client().post("/offers", {})

    assert exc.value.status == 403
    assert "You have no permission" in exc.value.message


def test_validation_error_406_lists_fields() -> None:
    stub = KeitaroStub()
    stub.on("POST", "/campaigns", {"alias": ["already taken"]}, status=406)

    with pytest.raises(KeitaroError) as exc:
        stub.client().post("/campaigns", {})
    assert "alias: already taken" in exc.value.message


def test_html_404_does_not_leak_markup() -> None:
    with pytest.raises(KeitaroError) as exc:
        KeitaroStub().client().get("/campaigns/1")
    assert exc.value.status == 404
    assert "<html>" not in exc.value.message


def test_timeout_becomes_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = KeitaroClient.from_settings(settings(), transport=httpx.MockTransport(timeout))
    with pytest.raises(KeitaroUnavailable):
        client.get("/campaigns")
