"""Health check endpoints."""
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint"""
    # Проверяем что pyannote доступен
    pyannote_available = False
    try:
        from pyannote.audio import Pipeline
        pyannote_available = True
    except Exception as e:
        pyannote_available = False
        logger.exception("pyannote.audio initialization failed")

    # Для community версии токен не требуется
    diarization_model = os.getenv("PYANNOTE_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
    is_community = "community" in diarization_model.lower()
    hf_token_set = bool(os.getenv("HF_TOKEN", "").strip())

    # Community версия работает без токена
    requires_token = not is_community

    # Если pyannote недоступен, или требуется токен но он не установлен - сервис нездоров
    if not pyannote_available or (requires_token and not hf_token_set):
        detail = {
            "status": "unhealthy",
            "pyannote_available": pyannote_available,
            "hf_token_set": hf_token_set,
            "requires_hf_token": requires_token,
            "model": diarization_model,
        }
        if requires_token and not hf_token_set:
            detail["reason"] = "HF_TOKEN required for non-community model"
        raise HTTPException(status_code=503, detail=detail)

    return {
        "status": "healthy",
        "pyannote_available": pyannote_available,
        "hf_token_set": hf_token_set,
        "requires_hf_token": requires_token,
        "model": diarization_model,
    }
