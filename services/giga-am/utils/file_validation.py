import io
import os
import logging
import hashlib
import tempfile
from typing import Optional, Dict, Any
from contextlib import contextmanager
from fastapi import UploadFile, HTTPException
from config import settings
from utils.exceptions import (
    ValidationError,
    AudioProcessingError,
    FileSizeError,
    UnsupportedFormatError
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64KB


async def read_upload_with_limit(file: UploadFile) -> bytes:
    """
    Читает загруженный файл чанками, прерываясь при превышении лимита размера.

    Args:
        file: Загруженный файл

    Returns:
        Содержимое файла в байтах

    Raises:
        HTTPException: 413 при превышении лимита, 400 для пустого файла
    """
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


class FileValidator:
    @staticmethod
    def validate_audio_file(file: UploadFile, content_length: Optional[int] = None) -> bool:
        """
        Валидация аудиофайла
        
        Args:
            file: Загруженный файл
            content_length: Content-Length заголовок для проверки размера
            
        Returns:
            True если файл валидный
            
        Raises:
            HTTPException: Если файл невалидный
        """
        # Проверка наличия файла
        if not file or not file.filename:
            raise ValidationError("Файл не загружен", field="file")
        
        # Проверка безопасности имени файла
        if not FileValidator.is_safe_filename(file.filename):
            raise ValidationError(
                "Небезопасное имя файла", 
                field="filename",
                filename=file.filename
            )
        
        # Проверка размера файла через Content-Length (приоритет)
        if content_length and content_length > settings.max_file_size:
            raise FileSizeError(
                f"Размер файла превышает лимит {settings.max_file_size // (1024*1024)}MB",
                file_size=content_length,
                max_size=settings.max_file_size
            )
        
        # Проверка размера файла через атрибут size (fallback)
        if hasattr(file, 'size') and file.size and file.size > settings.max_file_size:
            raise FileSizeError(
                f"Размер файла превышает лимит {settings.max_file_size // (1024*1024)}MB",
                file_size=file.size,
                max_size=settings.max_file_size
            )
        
        # Проверка расширения файла
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_audio_formats:
            raise UnsupportedFormatError(
                f"Неподдерживаемый формат файла",
                file_format=file_extension,
                supported_formats=settings.allowed_audio_formats
            )
        
        # Строгая проверка MIME типа
        allowed_mime_types = {
            '.mp3': ['audio/mpeg', 'audio/mp3', 'application/octet-stream'],
            '.wav': ['audio/wav', 'audio/x-wav', 'audio/wave', 'application/octet-stream'],
            '.flac': ['audio/flac', 'audio/x-flac', 'application/octet-stream'],
            '.m4a': ['audio/mp4', 'audio/x-m4a', 'application/octet-stream'],
            '.aac': ['audio/aac', 'audio/x-aac', 'application/octet-stream'],
            '.ogg': ['audio/ogg', 'audio/x-ogg', 'application/octet-stream'],
            '.webm': ['audio/webm', 'application/octet-stream']
        }
        
        if file.content_type:
            expected_mimes = allowed_mime_types.get(file_extension, [])
            if expected_mimes and file.content_type not in expected_mimes:
                logger.error(f"MIME тип {file.content_type} не соответствует расширению {file_extension}")
                raise ValidationError(
                    f"MIME тип {file.content_type} не соответствует расширению {file_extension}. Ожидалось: {', '.join(expected_mimes)}",
                    field="content_type",
                    actual_mime=file.content_type,
                    expected_mimes=expected_mimes
                )
        else:
            logger.debug(f"MIME тип отсутствует для файла {file.filename}")
            # Попытка определить MIME тип из данных файла
            try:
                # Читаем первые 512 байт для определения MIME типа
                file.file.seek(0)
                header = file.file.read(512)
                file.file.seek(0)  # Возвращаем указатель в начало
                
                import magic
                detected_mime = magic.from_buffer(header, mime=True)
                expected_mimes = allowed_mime_types.get(file_extension, [])
                if expected_mimes and detected_mime not in expected_mimes:
                    logger.error(f"Обнаруженный MIME тип {detected_mime} не соответствует расширению {file_extension}")
                    raise ValidationError(
                        f"Обнаруженный MIME тип {detected_mime} не соответствует расширению {file_extension}",
                        field="content_type",
                        actual_mime=detected_mime,
                        expected_mimes=expected_mimes
                    )
            except ImportError:
                logger.debug("python-magic не установлен, пропускаем глубокую проверку MIME")
            except Exception as e:
                logger.debug(f"Ошибка при определении MIME типа: {e}")
        
        return True
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        Вычисление SHA256 хеша файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA256 хеш файла
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    @staticmethod
    @contextmanager
    def secure_temp_file(file: UploadFile, suffix: str = ".tmp"):
        """
        Безопасное создание и очистка временного файла
        
        Args:
            file: Загруженный файл
            suffix: Расширение временного файла
            
        Yields:
            Путь к временному файлу
        """
        temp_path = None
        try:
            # Создаем временный файл с безопасным именем
            file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
                temp_path = tmp.name
                
                # Читаем и записываем данные по частям для экономии памяти
                file.file.seek(0)
                while True:
                    chunk = file.file.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    tmp.write(chunk)
                
                tmp.flush()
                os.fsync(tmp.fileno())  # Гарантируем запись на диск
                
            yield temp_path
            
        except Exception as e:
            logger.error(f"Ошибка при обработке временного файла: {e}")
            raise
        finally:
            # Безопасная очистка временного файла
            if temp_path and os.path.exists(temp_path):
                try:
                    # Перезаписываем файл случайными данными перед удалением
                    with open(temp_path, "wb") as f:
                        f.write(os.urandom(os.path.getsize(temp_path)))
                    os.unlink(temp_path)
                    logger.debug(f"Временный файл {temp_path} безопасно удален")
                except Exception as cleanup_error:
                    logger.warning(f"Не удалось безопасно удалить временный файл {temp_path}: {cleanup_error}")
                    # Пытаемся удалить обычным способом
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        logger.error(f"Не удалось удалить временный файл {temp_path}")
    
    @staticmethod
    def validate_audio_content(file_path: str) -> Dict[str, Any]:
        """
        Валидация содержимого аудиофайла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Словарь с информацией о файле
            
        Raises:
            HTTPException: Если файл невалидный
        """
        try:
            import librosa
            import soundfile
            
            # Проверяем, что файл действительно является аудио
            try:
                duration = librosa.get_duration(path=file_path)
                if duration <= 0:
                    raise AudioProcessingError(
                        "Файл не содержит аудиоданных или имеет нулевую длительность",
                        audio_file=file_path,
                        duration=duration
                    )
            except Exception as e:
                logger.error(f"Ошибка при проверке аудиофайла {file_path}: {e}")
                raise AudioProcessingError(
                    "Файл не является корректным аудиофайлом",
                    audio_file=file_path,
                    original_error=str(e)
                ) from e
            
            # Получаем метаданные
            try:
                info = soundfile.info(file_path)
                return {
                    "duration": duration,
                    "sample_rate": info.samplerate,
                    "channels": info.channels,
                    "frames": info.frames,
                    "format": info.format,
                    "subtype": info.subtype
                }
            except Exception as e:
                logger.debug(f"Не удалось получить метаданные аудиофайла: {e}")
                return {"duration": duration}
                
        except ImportError:
            logger.debug("librosa или soundfile не установлены, пропускаем глубокую проверку аудио")
            return {}
    
    @staticmethod
    def get_file_info(file: UploadFile) -> dict:
        """
        Получение информации о файле
        
        Args:
            file: Загруженный файл
            
        Returns:
            Словарь с информацией о файле
        """
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": getattr(file, 'size', 0),
            "extension": os.path.splitext(file.filename)[1].lower() if file.filename else None
        }
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """
        Проверка безопасности имени файла
        
        Args:
            filename: Имя файла
            
        Returns:
            True если имя файла безопасное
        """
        if not filename:
            return False
        
        # Проверка на опасные символы
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in filename:
                return False
        
        # Проверка длины имени
        if len(filename) > 255:
            return False
        
        return True
