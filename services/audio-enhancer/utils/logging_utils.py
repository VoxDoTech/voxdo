"""Структурированное логирование и метрики."""

import time
import logging
import json
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import contextmanager

import psutil
import torch

from config.settings import config


class StructuredLogger:
    """Структурированный логгер с метриками."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._metrics_enabled = config.ENABLE_METRICS
    
    def log_request(self, method: str, endpoint: str, **kwargs) -> None:
        """Логирует API запрос."""
        self._log_structured("request", {
            "method": method,
            "endpoint": endpoint,
            **kwargs
        })
    
    def log_response(self, method: str, endpoint: str, status_code: int, 
                    duration_ms: float, **kwargs) -> None:
        """Логирует API ответ."""
        self._log_structured("response", {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            **kwargs
        })
    
    def log_audio_processing(self, operation: str, file_size_bytes: int,
                           duration_seconds: float, sample_rate: int,
                           processing_time_ms: float, **kwargs) -> None:
        """Логирует обработку аудио."""
        metrics = {}
        if self._metrics_enabled:
            metrics.update(self._get_system_metrics())
        
        self._log_structured("audio_processing", {
            "operation": operation,
            "file_size_bytes": file_size_bytes,
            "duration_seconds": duration_seconds,
            "sample_rate": sample_rate,
            "processing_time_ms": processing_time_ms,
            "realtime_factor": duration_seconds * 1000 / processing_time_ms if processing_time_ms > 0 else 0,
            **metrics,
            **kwargs
        })
    
    def log_model_load(self, model_name: str, load_time_ms: float,
                      success: bool, **kwargs) -> None:
        """Логирует загрузку модели."""
        self._log_structured("model_load", {
            "model": model_name,
            "load_time_ms": load_time_ms,
            "success": success,
            **kwargs
        })
    
    def log_error(self, error_type: str, error_message: str, **kwargs) -> None:
        """Логирует ошибку."""
        self._log_structured("error", {
            "error_type": error_type,
            "error_message": error_message,
            **kwargs
        })
    
    def _log_structured(self, event_type: str, data: Dict[str, Any]) -> None:
        """Логирует структурированное сообщение."""
        log_entry = {
            "timestamp": time.time(),
            "event": event_type,
            "service": config.APP_NAME.lower().replace(" ", "_"),
            **data
        }
        
        if config.DEBUG:
            self.logger.info(json.dumps(log_entry, indent=2))
        else:
            self.logger.info(json.dumps(log_entry))
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Собирает системные метрики."""
        try:
            # CPU и память
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / 1024 / 1024,
            }
            
            # GPU метрики если доступно
            if torch.cuda.is_available():
                metrics.update({
                    "gpu_available": True,
                    "gpu_memory_allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
                    "gpu_memory_reserved_mb": torch.cuda.memory_reserved() / 1024 / 1024,
                })
            else:
                metrics["gpu_available"] = False
            
            return metrics
        except Exception as e:
            self.logger.warning("Failed to collect system metrics: %s", e)
            return {"metrics_error": str(e)}


def timing_logger(operation: str = "operation"):
    """Декоратор для логирования времени выполнения."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger = StructuredLogger(func.__module__)
                logger.logger.debug(
                    "%s completed in %.2fms", operation, duration_ms
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger = StructuredLogger(func.__module__)
                logger.log_error(
                    f"{operation}_error",
                    str(e),
                    duration_ms=duration_ms
                )
                raise
        return wrapper
    return decorator


@contextmanager
def log_context(operation: str, **context_data):
    """Контекстный менеджер для логирования операций."""
    start_time = time.time()
    logger = StructuredLogger(__name__)
    
    try:
        logger.logger.debug("Starting %s", operation)
        yield logger
        duration_ms = (time.time() - start_time) * 1000
        logger.logger.debug("%s completed in %.2fms", operation, duration_ms)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.log_error(f"{operation}_error", str(e), duration_ms=duration_ms, **context_data)
        raise


# Глобальные логгеры
request_logger = StructuredLogger("request")
processing_logger = StructuredLogger("processing")
model_logger = StructuredLogger("models")
