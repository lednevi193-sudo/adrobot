from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Проверка, что приложение живо и видит БД. 503, если БД недоступна."""
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as e:
        # e.orig — исходное исключение драйвера psycopg; первая строка без пароля и стектрейса
        reason = str(e.orig).splitlines()[0] if e.orig else "unknown"
        return JSONResponse(status_code=503, content={"status": "degraded", "database": reason})
    return {"status": "ok", "database": "ok"}
