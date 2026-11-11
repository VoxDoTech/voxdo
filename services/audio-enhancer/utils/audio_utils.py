"""Утилиты для работы с аудио файлами."""

import io
import base64
import tempfile
import subprocess
import json
import logging
import os
from typing import Optional, Tuple

import librosa
import numpy as np
import soundfile as sf
from fastapi import HTTPException, UploadFile

from config.settings import config

logger = logging.getLogger(__name__)


def parse_bool_env(value: Optional[str], default: bool = False) -> bool:
    """Парсит булево значение из переменной окружения."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int_env(name: str, default: int) -> int:
    """Парсит целое число из переменной окружения."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning("Некорректное значение %s=%r, используем %d", name, raw, default)
        return default
    if parsed <= 0:
        logger.warning("Значение %s=%d должно быть > 0, используем %d", name, parsed, default)
        return default
    return parsed


async def read_upload_bytes_capped(upload: UploadFile, max_bytes: int) -> bytes:
    """
    Читает тело запроса с ограничением размера.
    
    Args:
        upload: Загружаемый файл
        max_bytes: Максимальный размер в байтах
        
    Returns:
        Байты файла
        
    Raises:
        HTTPException: Если файл слишком большой
    """
    # Проверка Content-Length
    cl = upload.headers.get("content-length")
    if cl is not None:
        try:
            n = int(cl)
        except ValueError:
            n = -1
        if n > max_bytes:
            raise HTTPException(
                status_code=413, 
                detail=f"Payload too large. Max size: {max_bytes} bytes"
            )
    
    # Чтение с проверкой размера
    chunks = []
    total = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413, 
                detail=f"Payload too large. Max size: {max_bytes} bytes"
            )
        chunks.append(chunk)
    
    return b"".join(chunks)


def validate_audio_file(upload: UploadFile) -> None:
    """
    Валидирует аудио файл.
    
    Args:
        upload: Загружаемый файл
        
    Raises:
        HTTPException: Если файл не валидный
    """
    # Проверка MIME типа
    content_type = upload.content_type
    if content_type and content_type not in config.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. "
                   f"Allowed types: {', '.join(config.ALLOWED_MIME_TYPES)}"
        )
    
    # Проверка расширения файла
    if not upload.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    allowed_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm"}
    file_ext = os.path.splitext(upload.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {file_ext}. "
                   f"Allowed extensions: {', '.join(allowed_extensions)}"
        )


def load_audio_with_duration_check(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """
    Загружает аудио с проверкой длительности.
    
    Args:
        audio_bytes: Байты аудио файла
        
    Returns:
        Кортеж (audio_data, sample_rate)
        
    Raises:
        HTTPException: Если аудио слишком длинное или не валидное
    """
    # Проверка длительности через ffprobe
    duration = probe_audio_duration_seconds(audio_bytes)
    if duration is not None and duration > config.MAX_AUDIO_SECONDS:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too long. Max duration: {config.MAX_AUDIO_SECONDS}s"
        )
    
    # Загрузка аудио
    try:
        with io.BytesIO(audio_bytes) as audio_stream:
            audio, sr = librosa.load(audio_stream, sr=None, mono=True)
    except Exception as e:
        logger.error("Failed to load audio: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load audio file: {str(e)}"
        ) from e
    
    # Fallback проверка длительности
    decoded_duration = float(len(audio)) / float(sr) if sr else 0.0
    if decoded_duration > config.MAX_AUDIO_SECONDS:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too long. Max duration: {config.MAX_AUDIO_SECONDS}s"
        )
    
    logger.info("Loaded audio: %d samples, %d Hz, %.2fs", len(audio), sr, decoded_duration)
    return audio, sr


def probe_audio_duration_seconds(audio_bytes: bytes) -> Optional[float]:
    """
    Определяет длительность аудио через ffprobe.
    
    Args:
        audio_bytes: Байты аудио файла
        
    Returns:
        Длительность в секундах или None если не удалось определить
    """
    temp_path = None
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        # Вызываем ffprobe
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            temp_path,
        ]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        
        if result.returncode != 0:
            logger.warning("ffprobe failed: %s", result.stderr.strip())
            return None
        
        # Парсим результат
        payload = json.loads(result.stdout or "{}")
        duration_raw = payload.get("format", {}).get("duration")
        
        if duration_raw is None:
            return None
        
        duration = float(duration_raw)
        return duration if duration >= 0 else None
        
    except FileNotFoundError:
        logger.warning("ffprobe not found")
        return None
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse ffprobe output: %s", e)
        return None
    except Exception as e:
        logger.warning("ffprobe error: %s", e)
        return None
    finally:
        # Удаляем временный файл
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def save_audio_to_bytes(audio: np.ndarray, sr: int, format: str = "WAV") -> bytes:
    """
    Сохраняет аудио в байты.
    
    Args:
        audio: Аудио данные
        sr: Частота дискретизации
        format: Формат аудио
        
    Returns:
        Байты аудио файла
    """
    with io.BytesIO() as output_stream:
        sf.write(
            output_stream,
            audio,
            sr,
            subtype="PCM_16",
            format=format,
        )
        return output_stream.getvalue()


def audio_to_base64(audio_bytes: bytes) -> str:
    """
    Конвертирует аудио байты в base64 строку.
    
    Args:
        audio_bytes: Байты аудио
        
    Returns:
        Base64 строка
    """
    return base64.b64encode(audio_bytes).decode()


def base64_to_audio(base64_string: str) -> bytes:
    """
    Конвертирует base64 строку в аудио байты.
    
    Args:
        base64_string: Base64 строка
        
    Returns:
        Байты аудио
    """
    return base64.b64decode(base64_string)
