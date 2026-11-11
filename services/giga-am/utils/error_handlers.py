"""
Обработчики ошибок для FastAPI
"""
import logging
from typing import Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.exceptions import (
    GigaAMException,
    ValidationError,
    AudioProcessingError,
    ModelLoadError,
    TranscriptionError,
    FileSizeError,
    UnsupportedFormatError,
    ServiceUnavailableError,
    GigaTimeoutError,
    ConfigurationError
)

logger = logging.getLogger(__name__)


async def gigaam_exception_handler(request: Request, exc: GigaAMException) -> JSONResponse:
    """Обработчик кастомных исключений GigaAM"""
    logger.error(
        f"GigaAM Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Определяем HTTP статус код на основе типа исключения
    status_code_map = {
        ValidationError: 400,
        AudioProcessingError: 422,
        ModelLoadError: 503,
        TranscriptionError: 500,
        FileSizeError: 413,
        UnsupportedFormatError: 400,
        ServiceUnavailableError: 503,
        GigaTimeoutError: 408,
        ConfigurationError: 500
    }
    
    status_code = status_code_map.get(type(exc), 500)
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def http_exception_handler(request: Request, exc: Union[HTTPException, StarletteHTTPException]) -> JSONResponse:
    """Улучшенный обработчик HTTP исключений"""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "details": {}
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic"""
    logger.warning(
        f"Validation Error: {exc.errors()}",
        extra={
            "validation_errors": exc.errors(),
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Форматируем ошибки в более читаемый вид
    formatted_errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        formatted_errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Ошибка валидации входных данных",
                "details": {
                    "validation_errors": formatted_errors
                }
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик непредвиденных исключений"""
    logger.exception(
        f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Внутренняя ошибка сервера",
                "details": {
                    "exception_type": type(exc).__name__
                }
            }
        }
    )


def setup_exception_handlers(app):
    """Настройка обработчиков исключений для FastAPI приложения"""
    app.add_exception_handler(GigaAMException, gigaam_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
