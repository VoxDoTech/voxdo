"""Обработка исключений и ошибки."""

import logging
from typing import Dict, Any, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    """Базовое исключение для обработки аудио."""
    
    def __init__(self, message: str, error_code: str = "AUDIO_PROCESSING_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ModelLoadError(AudioProcessingError):
    """Ошибка загрузки модели."""
    
    def __init__(self, model_name: str, reason: str):
        message = f"Failed to load model {model_name}: {reason}"
        super().__init__(message, f"MODEL_LOAD_ERROR_{model_name.upper()}")
        self.model_name = model_name
        self.reason = reason


class AudioFormatError(AudioProcessingError):
    """Ошибка формата аудио."""
    
    def __init__(self, format_name: str, reason: str):
        message = f"Unsupported audio format {format_name}: {reason}"
        super().__init__(message, "AUDIO_FORMAT_ERROR")
        self.format_name = format_name
        self.reason = reason


class AudioSizeError(AudioProcessingError):
    """Ошибка размера аудио."""
    
    def __init__(self, size_bytes: int, max_bytes: int):
        message = f"Audio too large: {size_bytes} bytes (max: {max_bytes})"
        super().__init__(message, "AUDIO_SIZE_ERROR")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class AudioDurationError(AudioProcessingError):
    """Ошибка длительности аудио."""
    
    def __init__(self, duration_seconds: float, max_seconds: int):
        message = f"Audio too long: {duration_seconds}s (max: {max_seconds}s)"
        super().__init__(message, "AUDIO_DURATION_ERROR")
        self.duration_seconds = duration_seconds
        self.max_seconds = max_seconds


class ResourceExhaustedError(AudioProcessingError):
    """Ошибка исчерпания ресурсов."""
    
    def __init__(self, resource_type: str):
        message = f"Resource exhausted: {resource_type}"
        super().__init__(message, "RESOURCE_EXHAUSTED_ERROR")
        self.resource_type = resource_type


def create_error_response(error_code: str, message: str, 
                         status_code: int = 500, **kwargs) -> JSONResponse:
    """
    Создает стандартизированный ответ об ошибке.
    
    Args:
        error_code: Код ошибки
        message: Сообщение об ошибке
        status_code: HTTP статус код
        **kwargs: Дополнительные данные
        
    Returns:
        JSONResponse с ошибкой
    """
    error_data = {
        "error": {
            "code": error_code,
            "message": message,
            "type": "processing_error" if status_code >= 500 else "client_error",
            **kwargs
        }
    }
    
    logger.error("Error response: %s", error_data)
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


def handle_audio_processing_error(func):
    """
    Декоратор для обработки ошибок обработки аудио.
    
    Args:
        func: Функция для декорирования
        
    Returns:
        Обернутая функция
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AudioProcessingError as e:
            # Наши кастомные ошибки
            status_code = 400
            if isinstance(e, (AudioSizeError, AudioDurationError)):
                status_code = 413
            elif isinstance(e, ModelLoadError):
                status_code = 503
            elif isinstance(e, ResourceExhaustedError):
                status_code = 507
                
            return create_error_response(
                error_code=e.error_code,
                message=e.message,
                status_code=status_code
            )
        except Exception as e:
            # Неожиданные ошибки
            logger.exception("Unexpected error in %s", func.__name__)
            return create_error_response(
                error_code="INTERNAL_ERROR",
                message="Internal server error",
                status_code=500
            )
    
    return wrapper


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Обработчик ошибок валидации FastAPI.
    
    Args:
        request: HTTP запрос
        exc: Исключение валидации
        
    Returns:
        JSONResponse с ошибкой валидации
    """
    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request parameters",
        status_code=422,
        details=exc.errors()
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Общий обработчик исключений.
    
    Args:
        request: HTTP запрос
        exc: Исключение
        
    Returns:
        JSONResponse с ошибкой
    """
    logger.exception("Unhandled exception in %s %s", request.method, request.url)
    
    return create_error_response(
        error_code="INTERNAL_ERROR",
        message="Internal server error",
        status_code=500
    )


def setup_exception_handlers(app):
    """
    Устанавливает обработчики исключений для FastAPI приложения.
    
    Args:
        app: FastAPI приложение
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
