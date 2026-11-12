import asyncio
import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from utils.logger import setup_logging
from utils.error_handlers import setup_exception_handlers
from services.task_manager import task_manager

# Import routers
from routes.health import router as health_router
from routes.transcribe_async import router as transcribe_async_router, send_webhook_callback
from services.callback_outbox import callback_outbox
from routes.transcribe_diarized_async import router as transcribe_diarized_async_router
from routes.transcribe_sync import router as transcribe_sync_router
from routes.tasks import router as tasks_router
from routes.root import router as root_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager для управления жизненным циклом приложения"""
    # Startup
    with callback_outbox.connect():
        pass
    await task_manager.start()
    logger.info("TaskManager started")
    
    callback_worker = asyncio.create_task(callback_outbox.run(send_webhook_callback))
    try:
        yield
    finally:
        callback_worker.cancel()
        try:
            await callback_worker
        except asyncio.CancelledError:
            pass

        await task_manager.stop()
        logger.info("TaskManager stopped")


app = FastAPI(
    title=settings.app_name,
    description="Async API для распознавания русской речи на базе GigaAM",
    version=settings.app_version,
    lifespan=lifespan,
)

# Настройка обработчиков исключений
setup_exception_handlers(app)

# Регистрация роутеров
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(transcribe_async_router, prefix="/api", tags=["async-transcription"])
app.include_router(transcribe_diarized_async_router, prefix="/api", tags=["async-diarized-transcription"])
app.include_router(transcribe_sync_router, prefix="/api", tags=["sync-transcription"])
app.include_router(tasks_router, prefix="/api", tags=["tasks"])
app.include_router(root_router, tags=["root"])


if __name__ == "__main__":
    setup_logging()
    logger.info("Запуск приложения %s v%s", settings.app_name, settings.app_version)
    logger.info("Сервер будет запущен на %s:%s", settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
