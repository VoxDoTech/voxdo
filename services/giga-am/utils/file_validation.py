import io
import logging
import os

from fastapi import HTTPException, UploadFile

from config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64KB


async def read_upload_with_limit(file: UploadFile, filename: str) -> bytes:
    """
    Читает загруженный файл чанками, прерываясь при превышении лимита размера.

    Также проверяет расширение файла по settings.allowed_audio_formats.

    Args:
        file: Загруженный файл
        filename: Имя, используемое обработчиком аудио

    Returns:
        Содержимое файла в байтах

    Raises:
        HTTPException: 400 для пустого файла/неподдерживаемого формата,
            413 при превышении лимита размера
    """
    # Проверка расширения файла
    file_extension = os.path.splitext(filename or "")[1].lower()
    if file_extension not in settings.allowed_audio_formats:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Неподдерживаемый формат файла '{file_extension}'. "
                f"Допустимые: {', '.join(settings.allowed_audio_formats)}"
            ),
        )

    max_size = settings.max_file_size
    audio_buffer = io.BytesIO()
    total_size = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Размер файла ({total_size} bytes) превышает лимит ({max_size} bytes)"
            )
        audio_buffer.write(chunk)

    audio_data = audio_buffer.getvalue()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Аудио файл пуст")
    return audio_data
