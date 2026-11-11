from fastapi import APIRouter

from config import settings

router = APIRouter()

@router.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "GigaAM Sync API",
        "description": "Sync API для распознавания русской речи на базе GigaAM",
        "version": settings.app_version
    }
