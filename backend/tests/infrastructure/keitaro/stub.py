"""Подмена сети для тестов ACL: httpx.MockTransport (≈ свой HttpMessageHandler в .NET)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from app.config import Settings
from app.infrastructure.keitaro import CampaignPlacement, HttpKeitaroGateway, KeitaroClient

Handler = Callable[[httpx.Request], httpx.Response]
PLACEMENT = CampaignPlacement(domain_id=1813, group_id=10332, traffic_source_id=836)


def settings() -> Settings:
    return Settings(
        _env_file=None,  # не читать настоящий .env
        keitaro_url="https://keitaro.test",
        keitaro_api_key="test-key",
        database_url="postgresql+psycopg://unused",
        campaign_prefix="test_x_",
    )


@dataclass
class KeitaroStub:
    """Отвечает по таблице (метод, путь) -> ответ и запоминает запросы."""

    routes: dict[tuple[str, str], httpx.Response | Handler] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)

    def on(self, method: str, path: str, json_body: object = None, status: int = 200) -> None:
        self.routes[(method, "/admin_api/v1" + path)] = httpx.Response(status, json=json_body)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, text="<html>404 Not Found</html>", headers={"content-type": "text/html"})
        return route(request) if callable(route) else route

    def body(self, index: int = -1) -> object:
        return json.loads(self.requests[index].content)

    def client(self) -> KeitaroClient:
        return KeitaroClient.from_settings(settings(), transport=httpx.MockTransport(self.handle))

    def gateway(self, **options) -> HttpKeitaroGateway:
        return HttpKeitaroGateway(self.client(), PLACEMENT, alias_factory=lambda: "Abc12345", **options)
