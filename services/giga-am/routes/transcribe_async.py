"""
Асинхронный эндпоинт транскрипции с поддержкой Inngest callback.
"""
import asyncio
import logging
import uuid
from typing import Any, Dict, Optional, Set

import httpx
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import settings
from services.pipeline_service import PipelineService
from services.callback_outbox import callback_outbox
from utils.callback_network import CallbackTransport, validate_callback_url
from services.task_manager import TaskStatus, task_manager
from utils.exceptions import FileSizeError
from utils.file_validation import read_upload_with_limit
from utils.inngest import send_inngest_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["async-transcription"])
pipeline_service = PipelineService()

# Set для отслеживания background tasks
BACKGROUND_TASKS: Set[asyncio.Task] = set()


async def send_webhook_callback(
    callback_url: str,
    task_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> bool:
    """Отправка результата задачи на webhook URL."""
    payload: Dict[str, Any] = {"task_id": task_id, "status": status}
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error

    try:
        validate_callback_url(callback_url)
        async with httpx.AsyncClient(
            timeout=settings.callback_timeout, transport=CallbackTransport(),
            trust_env=False, follow_redirects=False,
        ) as client:
            async with client.stream("POST", callback_url, json=payload) as response:
                # Raw bytes avoid decompression bombs. Logs use a bounded prefix.
                body = bytearray()
                async for chunk in response.aiter_raw(chunk_size=4096):
                    remaining = settings.callback_response_max_bytes - len(body)
                    body.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        logger.error("Webhook response too large for task %s", task_id)
                        return False
                if response.status_code < 300:
                    logger.info("Webhook callback delivered for task %s", task_id)
                    return True
                logger.error("Webhook callback failed for task %s: %s %r",
                             task_id, response.status_code,
                             bytes(body[:1024]).decode("utf-8", errors="replace"))
                return False
    except Exception as e:
        logger.error(f"Webhook callback error for task {task_id}: {e}", exc_info=True)
        return False


async def process_task_background(task_id: str):
    """
    Фоновая обработка задачи транскрипции.
    
    Args:
        task_id: ID задачи
    """
    task = task_manager.get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found for background processing")
        return
    if task.audio_data is None:
        logger.error(f"Task {task_id} has no audio data")
        return

    task_manager.update_status(task_id, TaskStatus.PROCESSING)
    result = None
    error = None
    try:
        result = await pipeline_service.process_audio_sync(
            audio_data=task.audio_data, filename=task.filename
        )
        status = TaskStatus.COMPLETED
    except Exception as exc:
        logger.exception("Task %s failed", task_id)
        status = TaskStatus.FAILED
        error = str(exc)

    task_manager.update_status(task_id, status, result=result, error=error)
    callback_url = task.options.get("callback_url")
    if callback_url:
        # Persist before attempting delivery or contacting another event service.
        callback_outbox.enqueue(callback_url, task_id, status.value, result=result, error=error)
        await callback_outbox.deliver(send_webhook_callback, task_id)
    await send_inngest_event(task_id, status.value, result=result, error=error)


@router.post("/transcribe-async")
async def transcribe_async(
    file: UploadFile,
    filename: str = Form(...),
    callback_url: Optional[str] = Form(None)
) -> JSONResponse:
    """
    Асинхронная транскрипция аудио файла.
    
    Возвращает task_id сразу и обрабатывает в фоне.
    Результат будет отправлен через Inngest event или webhook.
    
    Args:
        file: Аудио файл
        filename: Имя файла
        callback_url: Опциональный webhook URL для обратного вызова
        
    Returns:
        JSONResponse с task_id
    """
    if callback_url is not None:
        try:
            validate_callback_url(callback_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Нужен хотя бы один способ доставки результата: Inngest или webhook
    inngest_configured = bool(settings.inngest_event_key and settings.inngest_api_url)
    if not inngest_configured and not callback_url:
        raise HTTPException(
            status_code=503,
            detail="No result delivery configured. Set INNGEST_EVENT_KEY/INNGEST_API_URL or pass callback_url."
        )
    
    request_id = f"async-req-{uuid.uuid4().hex[:12]}"

    try:
        logger.info(f"[{request_id}] Получен асинхронный запрос на транскрипцию: {filename}")

        # Читаем файл чанками с проверкой размера во время чтения
        audio_data = await read_upload_with_limit(file, filename)
        
        # Создаем задачу
        task = task_manager.create_task(
            filename,
            audio_data,
            options={"callback_url": callback_url} if callback_url else None,
        )
        
        # Запускаем фоновую обработку с отслеживанием
        background_task = asyncio.create_task(process_task_background(task.task_id))
        BACKGROUND_TASKS.add(background_task)
        background_task.add_done_callback(BACKGROUND_TASKS.discard)
        
        return JSONResponse(
            status_code=202,
            content={
                "task_id": task.task_id,
                "status": "pending",
                "message": "Task created and processing in background"
            }
        )
        
    except FileSizeError as fse:
        logger.error("Ошибка размера файла в асинхронной транскрипции: %s", fse)
        raise HTTPException(
            status_code=413,
            detail=str(fse)
        ) from fse
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Ошибка асинхронной транскрипции: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера при создании задачи"
        ) from exc


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> JSONResponse:
    """
    Получение статуса задачи по ID.
    
    Args:
        task_id: ID задачи
        
    Returns:
        JSONResponse со статусом задачи
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return JSONResponse(content=task.to_dict())


@router.get("/tasks/stats")
async def get_tasks_stats() -> JSONResponse:
    """
    Получение статистики по задачам.
    
    Returns:
        JSONResponse со статистикой
    """
    stats = task_manager.get_stats()
    return JSONResponse(content=stats)
