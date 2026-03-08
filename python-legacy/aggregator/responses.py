"""Standardized API response helpers."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse


def _meta() -> Dict[str, str]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "request_id": str(uuid.uuid4()),
    }


def success_response(
    data: Any, status_code: int = 200
) -> JSONResponse:
    """Build a standardised success response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "success",
            "data": data,
            "meta": _meta(),
        },
    )


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Build a standardised error response."""
    error: Dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": error,
            "meta": _meta(),
        },
    )
