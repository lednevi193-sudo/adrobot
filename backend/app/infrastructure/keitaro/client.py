"""Транспорт к Keitaro Admin API: заголовки, таймаут, перевод HTTP-сбоев в KeitaroError.

Аналог typed HttpClient в .NET: один экземпляр httpx.Client на процесс (пул соединений),
настроенный base_url и заголовками. Про кампании и потоки этот модуль не знает.
"""

from typing import Any

import httpx

from app.application.errors import KeitaroError, KeitaroUnavailable
from app.config import Settings

API_PATH = "/admin_api/v1"
_ERROR_TEXT_LIMIT = 300

Json = Any  # ответы Keitaro — dict или list; форму проверяет маппинг


class KeitaroClient:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    @classmethod
    def from_settings(cls, settings: Settings, transport: httpx.BaseTransport | None = None) -> "KeitaroClient":
        """transport — подмена сети в тестах (≈ свой HttpMessageHandler)."""
        http = httpx.Client(
            base_url=settings.keitaro_url.rstrip("/") + API_PATH,
            headers={
                "Api-Key": settings.keitaro_api_key,
                # без явного User-Agent Cloudflare стенда отвечает 403 (error 1010)
                "User-Agent": settings.keitaro_user_agent,
                "Accept": "application/json",
            },
            timeout=settings.keitaro_timeout,
            transport=transport,
        )
        return cls(http)

    def get(self, path: str) -> Json:
        return self._send("GET", path)

    def post(self, path: str, body: Json) -> Json:
        return self._send("POST", path, body)

    def put(self, path: str, body: Json) -> Json:
        return self._send("PUT", path, body)

    def delete(self, path: str) -> Json:
        return self._send("DELETE", path)

    def close(self) -> None:
        self._http.close()

    def _send(self, method: str, path: str, body: Json = None) -> Json:
        try:
            response = self._http.request(method, path, json=body)
        except httpx.TimeoutException as e:
            raise KeitaroUnavailable(f"Keitaro не ответил вовремя ({method} {path})") from e
        except httpx.TransportError as e:
            raise KeitaroUnavailable(f"Нет связи с Keitaro ({method} {path}): {e}") from e

        if response.is_error:
            raise KeitaroError(
                f"Keitaro отклонил {method} {path} ({response.status_code}): {describe_error(response)}",
                status=response.status_code,
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as e:
            raise KeitaroError(f"Keitaro вернул не JSON на {method} {path}", response.status_code) from e


def describe_error(response: httpx.Response) -> str:
    """Человекочитаемый текст ошибки Keitaro.

    Форматы из документации: {"error": "..."} для 4xx/5xx и {"nameField": [...]} для 406.
    404 стенда приходит HTML-страницей nginx — тогда только код.
    """
    try:
        data = response.json()
    except ValueError:
        if "html" in response.headers.get("content-type", ""):
            return response.reason_phrase or "ошибка без описания"
        return response.text[:_ERROR_TEXT_LIMIT] or response.reason_phrase

    if isinstance(data, dict):
        if isinstance(data.get("error"), str):
            return data["error"]
        messages = [f"{field}: {', '.join(map(str, v)) if isinstance(v, list) else v}" for field, v in data.items()]
        if messages:
            return "; ".join(messages)[:_ERROR_TEXT_LIMIT]
    return str(data)[:_ERROR_TEXT_LIMIT]
