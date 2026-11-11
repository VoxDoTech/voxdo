"""Diagnostics endpoint."""
import logging
import os
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Диагностическая информация о сервисе"""
    return {
        "service": "Speaker Diarization API",
        "version": "2.0.0",
        "pyannote": {
            "diarization_model": os.getenv("PYANNOTE_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"),
            "hf_token_set": bool(os.getenv("HF_TOKEN", "").strip()),
        },
        "config": {
            "port": os.getenv("PORT", "7860"),
        },
    }
