"""Перевод ошибок домена и приложения в HTTP (≈ ExceptionFilter / ProblemDetails в ASP.NET).

Тело всегда {code, message, ...детали}: code — для логики фронта, message — для пользователя.
Статус ищется по MRO исключения: самый конкретный класс из таблицы побеждает.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.presenters import change_dtos
from app.application.errors import (
    ApplicationError,
    CampaignAlreadyExists,
    CampaignCreationFailed,
    CampaignNotFound,
    ConcurrencyConflict,
    KeitaroError,
    KeitaroUnavailable,
    NotOurCampaign,
    OfferNotFound,
    PushNotConfirmed,
)
from app.domain.campaigns.errors import CampaignHasDrafts, OfferNotInStream, StreamNotInCampaign
from app.domain.common.errors import DomainError

STATUS: dict[type[Exception], int] = {
    DomainError: 422,  # нарушено правило: веса, гео, название, состояние оффера
    CampaignHasDrafts: 409,
    StreamNotInCampaign: 404,
    OfferNotInStream: 404,
    ApplicationError: 500,
    CampaignNotFound: 404,
    OfferNotFound: 404,
    CampaignAlreadyExists: 409,
    ConcurrencyConflict: 409,
    NotOurCampaign: 403,
    KeitaroError: 502,  # сбой внешней системы, а не наш
    CampaignCreationFailed: 502,
    PushNotConfirmed: 502,
    KeitaroUnavailable: 504,
}


def status_for(error: Exception) -> int:
    return next(STATUS[cls] for cls in type(error).__mro__ if cls in STATUS)


def error_body(error: DomainError | ApplicationError) -> dict:
    body: dict = {"code": error.code, "message": error.message}
    if isinstance(error, CampaignHasDrafts):
        body["changes"] = [
            dto.model_dump() for sid, changes in error.changes.items() for dto in change_dtos(sid, changes)
        ]
    if isinstance(error, PushNotConfirmed):
        body["differences"] = error.differences
    return body


async def _handle(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, DomainError | ApplicationError)
    return JSONResponse(status_code=status_for(error), content=error_body(error))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle)
    app.add_exception_handler(ApplicationError, _handle)
