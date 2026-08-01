"""Small operational contracts shared by health checks and API error handling."""

from typing import Any

from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine


DATABASE_OVERLOAD_RETRY_AFTER_SECONDS = 2


def get_database_pool_status() -> dict[str, Any]:
    """Return a non-secret snapshot of the configured SQLAlchemy pool budget."""
    pool = engine.pool
    checked_out_method = getattr(pool, "checkedout", None)
    checked_out = int(checked_out_method()) if callable(checked_out_method) else 0
    capacity = settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW
    return {
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "capacity": capacity,
        "checked_out": checked_out,
        "available": max(0, capacity - checked_out),
        "saturated": checked_out >= capacity,
    }


def database_capacity_response(request_id: str | None = None) -> JSONResponse:
    """Tell callers to retry instead of presenting pool saturation as a crash."""
    detail: dict[str, Any] = {
        "code": "database_capacity_exceeded",
        "message": "GameMind is temporarily at database capacity. Retry shortly.",
        "retry_after_seconds": DATABASE_OVERLOAD_RETRY_AFTER_SECONDS,
    }
    if request_id:
        detail["request_id"] = request_id
    return JSONResponse(
        status_code=503,
        content={"detail": detail},
        headers={"Retry-After": str(DATABASE_OVERLOAD_RETRY_AFTER_SECONDS)},
    )
