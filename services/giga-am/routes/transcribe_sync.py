"""
Синхронный эндпоинт транскрипции.
Для новой архитектуры: быстрая синхронная транскрибация без диаризации.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.pipeline_service import PipelineService
from utils.exceptions import FileSizeError
from utils.file_validation import read_upload_with_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync-transcription"])
pipeline_service = PipelineService()


@router.post("/transcribe-sync")
async def transcribe_sync(
    file: UploadFile,
    filename: str = Form(...),
    diarization: Optional[str] = Form("false")
) -> JSONResponse:
    """
    Синхронная транскрипция аудио файла.

    Возвращает результат сразу, без создания задачи в фоне.
    Используется для первичной транскрибации в новой архитектуре.

    Args:
        file: Аудио файл
        filename: Имя файла
        diarization: Параметр не поддерживается (всегда должен быть "false")

    Returns:
        JSONResponse с результатом транскрипции
    """
    # Валидация параметра diarization
    if diarization not in ["true", "false"]:
        raise HTTPException(
            status_code=400,
            detail="diarization parameter must be 'true' or 'false'"
        )

    # Синхронный эндпоинт не поддерживает диаризацию
    if diarization == "true":
        raise HTTPException(
            status_code=400,
            detail="Diarization is not supported in sync mode. Use async diarization endpoint instead."
        )

    request_id = f"sync-req-{uuid.uuid4().hex[:12]}"

    try:
        logger.info(f"[{request_id}] Получен синхронный запрос на транскрипцию: {filename}")

        # Читаем файл чанками с проверкой размера во время чтения
        audio_data = await read_upload_with_limit(file)
        
        # Запускаем синхронную обработку
        result = await pipeline_service.process_audio_sync(
            audio_data=audio_data,
            filename=filename
        )
        
        logger.info(f"[{request_id}] Синхронная транскрибация завершена")
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except FileSizeError as fse:
        logger.error(f"[{request_id}] Ошибка размера файла: {fse}")
        raise HTTPException(
            status_code=413,
            detail=str(fse)
        ) from fse
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[{request_id}] Ошибка синхронной транскрипции: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера при транскрипции"
        ) from exc
