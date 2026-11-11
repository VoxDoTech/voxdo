"""Root endpoint."""
import logging
import os
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root() -> dict[str, Any]:
    """Корневой endpoint с информацией о сервисе"""
    return {
        "service": "Speaker Diarization API",
        "version": "2.0.0",
        "description": "Speaker diarization using pyannote.audio 4.x",
        "endpoints": {
            "/": "GET - Информация о сервисе",
            "/health": "GET - Health check",
            "/api/diagnostics": "GET - Диагностическая информация",
            "/api/diarize": "POST - Speaker diarization (синхронный)",
            "/api/diarize-async": "POST - Speaker diarization (асинхронный)",
            "/api/status/{task_id}": "GET - Статус асинхронной задачи"
        },
        "docs": "/docs",
        "models": {
            "diarization": os.getenv("PYANNOTE_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"),
        }
    }
