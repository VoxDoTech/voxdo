"""
Эндпоинты для работы с задачами транскрипции.
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from services.task_manager import task_manager, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> JSONResponse:
    """
    Получение информации о задаче по ID.
    
    Args:
        task_id: ID задачи
        
    Returns:
        JSONResponse с информацией о задаче
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return JSONResponse(content=task.to_dict())


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> JSONResponse:
    """
    Получение результата задачи по ID.

    Возвращает только result или error в зависимости от статуса.

    Args:
        task_id: ID задачи

    Returns:
        JSONResponse с результатом или ошибкой
    """
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )

    # Возвращаем результат только если задача завершена
    if task.status == TaskStatus.COMPLETED:
        if task.result is None:
            raise HTTPException(
                status_code=500,
                detail=f"Task {task_id} completed but result is null"
            )
        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": task.status.value,
                "result": task.result
            }
        )
    elif task.status == TaskStatus.FAILED:
        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": task.status.value,
                "error": task.error
            }
        )
    else:
        # Задача еще в процессе
        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": task.status.value,
                "message": "Task is still processing"
            }
        )
