"""Типизированные идентификаторы — ID сущностей в Keitaro.

NewType не создаёт обёртку в рантайме (это обычный int), но не даёт тайпчекеру
перепутать ID оффера с ID потока — аналог strongly-typed ID в C#.
"""

from typing import NewType

OfferId = NewType("OfferId", int)
StreamId = NewType("StreamId", int)
CampaignId = NewType("CampaignId", int)
