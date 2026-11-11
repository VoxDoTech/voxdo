"""Сервисы обработки."""

from .model_service import model_manager, ModelManager
from .audio_service import audio_processor, AudioProcessor

__all__ = [
    "model_manager",
    "ModelManager", 
    "audio_processor",
    "AudioProcessor",
]
