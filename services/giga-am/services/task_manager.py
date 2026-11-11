"""
Менеджер асинхронных задач для транскрипции.
Хранит статус задач в памяти.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Статусы задачи"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """Задача транскрипции"""
    
    def __init__(
        self,
        task_id: str,
        filename: str,
        audio_data: bytes,
        options: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.filename = filename
        self.audio_data: Optional[bytes] = audio_data
        self.options = options or {}
        self.status = TaskStatus.PENDING
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для API"""
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "status": self.status.value,
            "result": self.result if self.status == TaskStatus.COMPLETED else None,
            "error": self.error if self.status == TaskStatus.FAILED else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_time_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.completed_at and self.started_at
                else None
            )
        }


class TaskManager:
    """Менеджер задач с in-memory хранилищем"""
    
    def __init__(self, max_age_hours: int = 24):
        self.tasks: Dict[str, Task] = {}
        self.max_age = timedelta(hours=max_age_hours)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запуск фонового процесса очистки старых задач"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("TaskManager cleanup loop started")
    
    async def stop(self):
        """Остановка фонового процесса"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("TaskManager cleanup loop stopped")
    
    async def _cleanup_loop(self):
        """Фоновый цикл очистки старых задач"""
        while True:
            try:
                await asyncio.sleep(3600)  # Каждый час
                await self.cleanup_old_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def cleanup_old_tasks(self):
        """Удаление старых задач"""
        now = datetime.now(timezone.utc)
        old_tasks = [
            task_id for task_id, task in self.tasks.items()
            if now - task.created_at > self.max_age
        ]
        for task_id in old_tasks:
            del self.tasks[task_id]
            logger.debug(f"Cleaned up old task: {task_id}")
        if old_tasks:
            logger.info(f"Cleaned up {len(old_tasks)} old tasks")
    
    def create_task(
        self,
        filename: str,
        audio_data: bytes,
        options: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Создание новой задачи"""
        task_id = str(uuid.uuid4())
        task = Task(task_id, filename, audio_data, options)
        self.tasks[task_id] = task
        logger.info(f"Created task {task_id} for {filename}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Получение задачи по ID"""
        return self.tasks.get(task_id)
    
    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """Обновление статуса задачи"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = status
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error

        if status == TaskStatus.PROCESSING and task.started_at is None:
            task.started_at = datetime.now(timezone.utc)
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.now(timezone.utc)
            # Освобождаем audio_data для экономии памяти
            task.audio_data = None

        logger.info(f"Updated task {task_id} status to {status.value}")
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Статистика по задачам"""
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        for task in self.tasks.values():
            stats[task.status.value] += 1
        return stats


# Глобальный экземпляр
task_manager = TaskManager()
