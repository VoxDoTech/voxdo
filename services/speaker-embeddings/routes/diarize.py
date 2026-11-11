"""Diarization endpoints (sync and async)."""
import asyncio
import logging
import os
import time
import uuid
import threading
from typing import Any

import httpx
import librosa
import numpy as np
import soundfile as sf
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.diarization_service import process_diarization

logger = logging.getLogger(__name__)

router = APIRouter()

# Хранилище асинхронных задач (in-memory)
_task_store: dict[str, dict[str, Any]] = {}
_task_store_lock = threading.Lock()

# Максимальное время хранения завершенных задач (в секундах)
_TASK_RETENTION_SECONDS = 3600  # 1 час


# Inngest конфигурация
INNGEST_API_URL = os.getenv("INNGEST_API_URL", "http://localhost:3001")
INNGEST_EVENT_KEY = os.getenv("INNGEST_EVENT_KEY", "")


def _cleanup_old_tasks():
    """
    Удаляет старые завершенные задачи из хранилища для предотвращения memory leak.
    Задачи удаляются если они завершены (completed/failed) и старше _TASK_RETENTION_SECONDS.
    """
    current_time = time.time()
    tasks_to_remove = []

    with _task_store_lock:
        for task_id, task_data in _task_store.items():
            # Удаляем только завершенные задачи
            if task_data["status"] in ("completed", "failed"):
                age_seconds = current_time - task_data["updated_at"]
                if age_seconds > _TASK_RETENTION_SECONDS:
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del _task_store[task_id]

    if tasks_to_remove:
        logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks from task store")


async def send_inngest_event(
    task_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    call_id: str | None = None,
) -> bool:
    """
    Отправка события в Inngest о завершении задачи диаризации (async версия).

    Args:
        task_id: ID задачи
        status: Статус (completed/failed)
        result: Результат диаризации
        error: Ошибка если есть
        call_id: ID звонка для связи с внешней системой

    Returns:
        True если успешно отправлено
    """
    if not INNGEST_EVENT_KEY:
        logger.warning("INNGEST_EVENT_KEY not configured, skipping callback")
        return False

    event_name = "speaker-embeddings/diarization.completed"

    payload = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "error": error,
        "call_id": call_id,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{INNGEST_API_URL}/e/{INNGEST_EVENT_KEY}",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "name": event_name,
                    "data": payload,
                },
            )

            if response.status_code == 200:
                logger.info(f"Sent Inngest event {event_name} for task {task_id}")
                return True
            else:
                logger.error(
                    f"Failed to send Inngest event: {response.status_code} {response.text}"
                )
                return False
    except Exception as e:
        logger.error(f"Error sending Inngest event: {e}", exc_info=True)
        return False


def send_inngest_event_sync(
    task_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    call_id: str | None = None,
) -> bool:
    """
    Отправка события в Inngest о завершении задачи диаризации (sync версия).
    Используется в фоновых задачах без event loop.

    Args:
        task_id: ID задачи
        status: Статус (completed/failed)
        result: Результат диаризации
        error: Ошибка если есть
        call_id: ID звонка для связи с внешней системой

    Returns:
        True если успешно отправлено
    """
    if not INNGEST_EVENT_KEY:
        logger.warning("INNGEST_EVENT_KEY not configured, skipping callback")
        return False

    event_name = "speaker-embeddings/diarization.completed"

    payload = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "error": error,
        "call_id": call_id,
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                f"{INNGEST_API_URL}/e/{INNGEST_EVENT_KEY}",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "name": event_name,
                    "data": payload,
                },
            )

            if response.status_code == 200:
                logger.info(f"Sent Inngest event {event_name} for task {task_id}")
                return True
            else:
                logger.error(
                    f"Failed to send Inngest event: {response.status_code} {response.text}"
                )
                return False
    except Exception as e:
        logger.error(f"Error sending Inngest event: {e}", exc_info=True)
        return False


def _run_diarization_task(
    task_id: str,
    audio: np.ndarray,
    sr: int,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
    call_id: str | None = None,
):
    """Выполняет диаризацию в фоновом режиме и отправляет результат в Inngest."""
    try:
        # Обновляем статус на processing
        with _task_store_lock:
            _task_store[task_id]["status"] = "processing"
            _task_store[task_id]["updated_at"] = time.time()

        logger.info(f"Starting background diarization task: {task_id}")

        # Выполняем диаризацию
        result = process_diarization(
            audio,
            sr,
            num_speakers,
            min_speakers,
            max_speakers,
        )

        # Сохраняем результат
        with _task_store_lock:
            _task_store[task_id]["status"] = "completed"
            _task_store[task_id]["result"] = result
            _task_store[task_id]["updated_at"] = time.time()

        logger.info(f"Background diarization task completed: {task_id}")

        # Отправляем событие в Inngest
        send_inngest_event_sync(task_id, "completed", result=result, call_id=call_id)

    except Exception as exc:
        logger.exception(f"Background diarization task failed: {task_id}")
        # Сохраняем ошибку
        with _task_store_lock:
            _task_store[task_id]["status"] = "failed"
            _task_store[task_id]["error"] = str(exc)
            _task_store[task_id]["updated_at"] = time.time()

        # Отправляем событие об ошибке в Inngest
        send_inngest_event_sync(task_id, "failed", error=str(exc), call_id=call_id)


def _load_and_preprocess_audio(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Синхронная предобработка аудио — вызывается через asyncio.to_thread."""
    import io
    audio, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = np.asarray(audio, dtype=np.float32)
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        sr = 16000
    return audio, sr


def _validate_speaker_params(
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None
) -> None:
    """Валидация параметров количества спикеров."""
    if num_speakers is not None:
        if not isinstance(num_speakers, int) or num_speakers <= 0:
            raise HTTPException(
                status_code=400,
                detail="num_speakers must be a positive integer"
            )

    if min_speakers is not None:
        if not isinstance(min_speakers, int) or min_speakers <= 0:
            raise HTTPException(
                status_code=400,
                detail="min_speakers must be a positive integer"
            )

    if max_speakers is not None:
        if not isinstance(max_speakers, int) or max_speakers <= 0:
            raise HTTPException(
                status_code=400,
                detail="max_speakers must be a positive integer"
            )

    # Проверка соотношения между min и max
    if min_speakers is not None and max_speakers is not None:
        if min_speakers > max_speakers:
            raise HTTPException(
                status_code=400,
                detail="min_speakers must be less than or equal to max_speakers"
            )

    # Проверка, что num_speakers находится в диапазоне [min_speakers, max_speakers]
    if num_speakers is not None:
        if min_speakers is not None and num_speakers < min_speakers:
            raise HTTPException(
                status_code=400,
                detail="num_speakers must be greater than or equal to min_speakers"
            )
        if max_speakers is not None and num_speakers > max_speakers:
            raise HTTPException(
                status_code=400,
                detail="num_speakers must be less than or equal to max_speakers"
            )


@router.post("/diarize")
async def diarize(
    file: UploadFile = File(...),
    num_speakers: int | None = Form(None),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
):
    """
    Speaker diarization endpoint.

    Определяет "кто говорил когда" в аудио файле.
    Возвращает список сегментов с временными метками и ID спикеров.
    """
    # Замер общего времени выполнения endpoint
    request_start_time = time.time()

    try:
        # Замер времени загрузки и предобработки аудио
        audio_processing_start = time.time()

        # Читаем байты асинхронно
        audio_bytes = await file.read()

        # Перемещаем I/O + CPU-работу в thread pool
        audio, sr = await asyncio.to_thread(
            _load_and_preprocess_audio, audio_bytes
        )

        audio_processing_end = time.time()
        audio_processing_time = audio_processing_end - audio_processing_start

        logger.info(
            f"Audio loaded and preprocessed in {audio_processing_time:.2f}s "
            f"(duration: {len(audio)/sr:.2f}s, sample_rate: {sr}Hz)"
        )

        # Валидация параметров (лёгкая, оставляем в event loop)
        _validate_speaker_params(num_speakers, min_speakers, max_speakers)

        # Тяжёлый ML inference — обязательно в thread pool
        result = await asyncio.to_thread(
            process_diarization, audio, sr, num_speakers, min_speakers, max_speakers
        )

        # Завершение замера времени выполнения endpoint
        request_end_time = time.time()
        total_request_time = request_end_time - request_start_time

        logger.info(
            f"Total request completed in {total_request_time:.2f}s "
            f"(audio: {len(audio)/sr:.2f}s, "
            f"real_time_factor: {total_request_time/(len(audio)/sr):.2f}x)"
        )

        return result

    except HTTPException:
        request_end_time = time.time()
        total_request_time = request_end_time - request_start_time
        logger.warning(f"Request failed after {total_request_time:.2f}s")
        raise
    except Exception as exc:
        request_end_time = time.time()
        total_request_time = request_end_time - request_start_time
        logger.exception(f"diarization failed after {total_request_time:.2f}s: %s", exc)
        raise HTTPException(status_code=500, detail="diarization failed") from exc


@router.post("/diarize-async")
async def diarize_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    call_id: str | None = Form(None),
    num_speakers: int | None = Form(None),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
):
    """
    Асинхронный speaker diarization endpoint.

    Запускает диаризацию в фоне и возвращает task_id для отслеживания.
    Используйте /status/{task_id} для проверки статуса или ожидайте callback в Inngest.
    
    Args:
        call_id: ID звонка для передачи в Inngest callback
    """
    try:
        # Читаем байты асинхронно
        audio_bytes = await file.read()

        # Перемещаем I/O + CPU-работу в thread pool
        audio, sr = await asyncio.to_thread(
            _load_and_preprocess_audio, audio_bytes
        )

        # Валидация параметров
        _validate_speaker_params(num_speakers, min_speakers, max_speakers)

        # Очищаем старые завершенные задачи для предотвращения memory leak
        _cleanup_old_tasks()

        # Генерируем task_id
        task_id = str(uuid.uuid4())

        # Создаем запись задачи
        with _task_store_lock:
            _task_store[task_id] = {
                "status": "pending",
                "created_at": time.time(),
                "updated_at": time.time(),
                "result": None,
                "error": None,
            }

        # Запускаем диаризацию в фоне
        background_tasks.add_task(
            _run_diarization_task,
            task_id,
            audio,
            sr,
            num_speakers,
            min_speakers,
            max_speakers,
            call_id,
        )

        logger.info(f"Async diarization task created: {task_id}")

        return JSONResponse(
            content={"task_id": task_id, "status": "pending"},
            status_code=202
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to create async diarization task: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create async task") from exc


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Возвращает статус асинхронной задачи диаризации.

    Статусы:
    - pending: задача в очереди
    - processing: диаризация выполняется
    - completed: диаризация завершена успешно
    - failed: диаризация завершилась с ошибкой
    """
    with _task_store_lock:
        task = _task_store.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    response = {
        "task_id": task_id,
        "status": task["status"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }

    if task["status"] == "completed" and task["result"]:
        response["result"] = task["result"]
    elif task["status"] == "failed" and task["error"]:
        response["error"] = task["error"]

    return response
