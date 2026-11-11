"""
Отправка событий о завершении задач в Inngest.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

INNGEST_EVENT_NAME = "giga-am/transcription.completed"


async def send_inngest_event(
    task_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> bool:
    """
    Отправка события в Inngest о завершении задачи.

    Всегда используется зарегистрированное событие
    "giga-am/transcription.completed" — статус передается в payload.

    Args:
        task_id: ID задачи
        status: Статус (completed/failed)
        result: Результат транскрипции
        error: Ошибка если есть

    Returns:
        True если успешно отправлено
    """
    if not settings.inngest_event_key or not settings.inngest_api_url:
        logger.warning("Inngest credentials not configured, skipping callback")
        return False

    payload: Dict[str, Any] = {
        "task_id": task_id,
        "status": status,
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error

    log_data = {
        "task_id": task_id,
        "status": status,
        "has_result": result is not None,
        "has_error": error is not None,
        "payload_size": len(str(payload)),
    }

    try:
        logger.info(f"[Inngest] Отправка события {INNGEST_EVENT_NAME}: {log_data}")

        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            response = await client.post(
                f"{settings.inngest_api_url}/e/{settings.inngest_event_key}",
                headers={"Content-Type": "application/json"},
                json={"name": INNGEST_EVENT_NAME, "data": payload},
            )

        if response.status_code == 200:
            logger.info(f"[Inngest] Событие отправлено для task {task_id}")
            return True

        logger.error(
            f"[Inngest] Ошибка отправки: {response.status_code} {response.text}"
        )
        return False
    except Exception as e:
        logger.error(f"[Inngest] Ошибка отправки события: {e}", exc_info=True)
        return False
