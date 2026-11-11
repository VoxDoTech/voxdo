"""Speaker Diarization API - модульное приложение."""
import logging
import os

from fastapi import FastAPI
import uvicorn

from routes.diarize import router as diarize_router
from routes.health import router as health_router
from routes.diagnostics import router as diagnostics_router
from routes.root import router as root_router
from utils.middleware import MaxContentSizeMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("speaker-embeddings")

app = FastAPI(
    title="Speaker Diarization API",
    description="Speaker diarization service using pyannote.audio",
    version="2.0.0",
)

# Добавляем middleware для ограничения размера запроса (100MB)
app.add_middleware(MaxContentSizeMiddleware, max_size=100 * 1024 * 1024)

# Подключаем маршруты
app.include_router(root_router)
app.include_router(health_router)
app.include_router(diagnostics_router)
app.include_router(diarize_router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
