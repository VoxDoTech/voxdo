"""
Кастомные исключения для GigaAM API
"""
from typing import Optional, Dict, Any


class GigaAMException(Exception):
    """Базовое исключение для GigaAM API"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(GigaAMException):
    """Ошибка валидации данных"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, **kwargs}
        )
        self.field = field


class AudioProcessingError(GigaAMException):
    """Ошибка обработки аудио"""
    
    def __init__(self, message: str, audio_file: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="AUDIO_PROCESSING_ERROR",
            details={"audio_file": audio_file, **kwargs}
        )
        self.audio_file = audio_file


class ModelLoadError(GigaAMException):
    """Ошибка загрузки модели"""
    
    def __init__(self, message: str, model_name: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="MODEL_LOAD_ERROR",
            details={"model_name": model_name, **kwargs}
        )
        self.model_name = model_name


class TranscriptionError(GigaAMException):
    """Ошибка транскрипции"""
    
    def __init__(self, message: str, stage: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="TRANSCRIPTION_ERROR",
            details={"stage": stage, **kwargs}
        )
        self.stage = stage


class FileSizeError(GigaAMException):
    """Ошибка размера файла"""
    
    def __init__(self, message: str, file_size: Optional[int] = None, max_size: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="FILE_SIZE_ERROR",
            details={"file_size": file_size, "max_size": max_size, **kwargs}
        )
        self.file_size = file_size
        self.max_size = max_size


class UnsupportedFormatError(GigaAMException):
    """Ошибка неподдерживаемого формата"""
    
    def __init__(self, message: str, file_format: Optional[str] = None, supported_formats: Optional[list] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_FORMAT_ERROR",
            details={"file_format": file_format, "supported_formats": supported_formats, **kwargs}
        )
        self.file_format = file_format
        self.supported_formats = supported_formats


class ServiceUnavailableError(GigaAMException):
    """Ошибка недоступности сервиса"""
    
    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE_ERROR",
            details={"service_name": service_name, **kwargs}
        )
        self.service_name = service_name


class GigaTimeoutError(GigaAMException):
    """Ошибка таймаута"""
    
    def __init__(self, message: str, timeout_seconds: Optional[int] = None, operation: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="TIMEOUT_ERROR",
            details={"timeout_seconds": timeout_seconds, "operation": operation, **kwargs}
        )
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class ConfigurationError(GigaAMException):
    """Ошибка конфигурации"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key, **kwargs}
        )
        self.config_key = config_key
