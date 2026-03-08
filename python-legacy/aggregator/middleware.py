"""Security middleware: API key auth, rate limiting."""

import time
from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token against configured API keys.

    If no API keys are configured, all requests are allowed (dev mode).
    Health endpoint is always public.
    """

    def __init__(self, app, api_keys: List[str]):  # type: ignore[override]
        super().__init__(app)
        self.api_keys = set(api_keys)

    async def dispatch(self, request: Request, call_next: Callable):
        # Always allow health check
        if request.url.path == "/api/v1/health":
            return await call_next(request)

        # Skip auth if no keys configured (dev mode)
        if not self.api_keys:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token in self.api_keys:
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API key",
                },
            },
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter per client IP."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):  # type: ignore[override]
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window

        # Clean old entries
        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests",
                    },
                },
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
