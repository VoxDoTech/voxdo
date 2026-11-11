"""
Сервис для выполнения транскрипции аудио.
"""
import asyncio
import logging
import os
import tempfile
import uuid
from typing import Dict, Any

from config import settings
from services.transcription_service import transcription_service

logger = logging.getLogger(__name__)



class PipelineService:
    """Сервис для выполнения pipeline транскрипции."""
    
    async def process_audio_sync(self, audio_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Синхронная обработка аудио файла.
        
        Вызывается из Inngest и ждет завершения транскрипции.
        
        Args:
            audio_data: Байты аудио файла
            filename: Имя файла
            
        Returns:
            Результат транскрипции
        """
        request_id = f"sync-{uuid.uuid4()}"
        
        try:
            logger.info(f"[{request_id}] Начало синхронной обработки аудио: {filename}")
            
            # Проверяем размер файла
            max_size = settings.max_file_size
            if len(audio_data) > max_size:
                from utils.exceptions import FileSizeError
                raise FileSizeError(
                    f"Размер файла ({len(audio_data)} bytes) превышает лимит ({max_size} bytes)",
                    file_size=len(audio_data),
                    max_size=max_size
                )
            
            # Сохраняем аудио во временный файл
            tmp_path = None
            try:
                # Извлекаем только расширение из filename
                file_extension = os.path.splitext(filename)[1] or ".tmp"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                    tmp_path = tmp_file.name
                    tmp_file.write(audio_data)
                
                # Запускаем только транскрипцию
                result = await asyncio.to_thread(
                    transcription_service.transcribe_audio, 
                    tmp_path
                )
                
                # Конвертируем в ожидаемый формат
                if result.get("success"):
                    result = {
                        "success": True,
                        "final_transcript": result.get("final_transcript", ""),
                        "segments": result.get("segments", []),
                        "pipeline": "gigam-asr-only",
                        "dual_asr_enabled": False,
                    }
                else:
                    # Сохраняем детали ошибки для отладки
                    error_details = {
                        "success": result.get("success"),
                        "error": result.get("error"),
                        "text": result.get("text"),
                        "pipeline": "gigam-asr-only"
                    }
                    logger.error(f"[{request_id}] ASR транскрипция не удалась: {error_details}")
                    raise RuntimeError(f"ASR транскрипция не удалась: {error_details}")
                
                logger.info(f"[{request_id}] Синхронная обработка завершена")
                return result
            finally:
                # Очистка временного файла
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception as e:
                        logger.warning(f"[{request_id}] Failed to cleanup temp file {tmp_path}: {e}")
            
        except Exception as e:
            logger.error(f"[{request_id}] Ошибка синхронной обработки: {e}")
            raise
