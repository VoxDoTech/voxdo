"""
Health check эндпоинты.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Проверка здоровья сервиса.
    """
    try:
        # Импортируем сервисы для проверки состояния
        from services.transcription_service import transcription_service
        from config import settings
        
        # Проверяем состояние модели транскрипции
        model_loaded = (
            transcription_service._model_initialized and 
            not transcription_service._model_loading and 
            transcription_service.model is not None
        )
        
        # Проверяем доступность diarization через настроенный HF_TOKEN
        pyannote_available = bool(settings.hf_token)

        return JSONResponse(content={
            "status": "healthy",
            "service": "giga-am-transcription",
            "version": settings.app_version,
            "model_loaded": model_loaded,
            "pyannote_available": pyannote_available
        })

    except Exception as e:
        # В случае ошибки всё равно возвращаем healthy, но с флагами
        return JSONResponse(content={
            "status": "healthy",
            "service": "giga-am-transcription",
            "version": "unknown",
            "model_loaded": False,
            "pyannote_available": False,
            "error": str(e)
        })


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Проверка готовности сервиса.
    """
    try:
        # Импортируем и проверяем готовность transcription_service
        from services.transcription_service import transcription_service
        
        # Проверяем, что сервис готов к работе
        # Используем внутренние флаги _model_initialized/_model_loading, так как is_ready() не существует
        # Также проверяем, что модель объект действительно существует
        if (not transcription_service._model_initialized or 
            transcription_service._model_loading or 
            transcription_service.model is None):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": "giga-am-transcription",
                    "reason": "model not loaded, still loading, or model instance is missing"
                }
            )
        
        # Если нет специфических проверок готовности, считаем сервис готовым
        return JSONResponse(content={
            "status": "ready",
            "service": "giga-am-transcription"
        })
        
    except AttributeError as ae:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "giga-am-transcription",
                "reason": f"Service attribute missing: {str(ae)}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "giga-am-transcription",
                "reason": f"Service not ready: {str(e)}"
            }
        )
