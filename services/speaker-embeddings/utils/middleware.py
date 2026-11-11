"""Middleware для FastAPI приложения."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class MaxContentSizeMiddleware(BaseHTTPMiddleware):
    """Middleware для ограничения максимального размера контента запроса"""

    def __init__(self, app, max_size: int = 100 * 1024 * 1024):  # 100MB default
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        # Check Content-Length only for POST, PUT, PATCH (methods with body)
        if request.method in ("POST", "PUT", "PATCH"):
            # Explicitly reject Transfer-Encoding to prevent chunked bypass
            transfer_encoding = request.headers.get("transfer-encoding")
            if transfer_encoding:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Transfer-Encoding header is not supported. Use Content-Length instead."}
                )

            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    content_length_int = int(content_length)
                    if content_length_int < 0:
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Content-Length header cannot be negative"}
                        )
                    if content_length_int > self.max_size:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": f"Request entity too large. Maximum size is {self.max_size // (1024*1024)}MB"}
                        )
                except (ValueError, TypeError):
                    # If Content-Length is not a valid number, reject request
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header"}
                    )
            else:
                # If Content-Length is missing for methods with body, reject request for security
                # This prevents bypass via Transfer-Encoding: chunked
                return JSONResponse(
                    status_code=411,
                    content={"detail": "Content-Length header is required"}
                )

        return await call_next(request)
