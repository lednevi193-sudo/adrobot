"""Порт транзакции: граница сценария приложения.

Session SQLAlchemy подходит под него как есть (у неё есть commit и rollback) — отдельный
класс-обёртка не нужен. Сценарии не импортируют SQLAlchemy и тестируются с фейком.
"""

from typing import Protocol


class UnitOfWork(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
