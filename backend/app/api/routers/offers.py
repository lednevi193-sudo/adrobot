"""Справочник офферов: автодополнение (FR-1.2)."""

from fastapi import APIRouter

from app.api.dependencies import Keitaro
from app.api.presenters import offer_dto
from app.api.schemas import OfferDto
from app.application.offers.search_offers import search_offers

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("")
def search(keitaro: Keitaro, q: str = "") -> list[OfferDto]:
    return [offer_dto(o) for o in search_offers(keitaro, q)]
