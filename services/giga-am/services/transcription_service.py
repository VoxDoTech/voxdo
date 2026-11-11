import logging
import os
import threading
import asyncio
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional
import gigaam
import torch
import torchaudio
from config import settings
from utils.exceptions import ModelLoadError, GigaTimeoutError

logger = logging.getLogger(__name__)

def to_safe_float(value) -> Optional[float]:
    """
    Безопасно конвертирует значение в float.
    
    Args:
        value: Значение для конвертации
        
    Returns:
        float или None в случае ошибки
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

class TranscriptionService:
    def __init__(self):
        self.model = None
        self.model_name = settings.model_name
        self._model_lock = threading.RLock()  # Reentrant lock для thread safety
        self._loading_lock = threading.Lock()  # Для предотвращения параллельной загрузки
        self._model_initialized = False
        self._model_loading = False
        self._model_error = None
        self._executor = ThreadPoolExecutor(max_workers=settings.model_workers)  # Используем настройку из config
        self._initialization_event = threading.Event()
        
        # Запускаем инициализацию в фоновом потоке
        self._init_thread = threading.Thread(target=self._initialize_model_async, daemon=True)
        self._init_thread.start()
    
    def _initialize_model_async(self):
        """Асинхронная инициализация модели в фоновом потоке"""
        # Устанавливаем флаг загрузки перед запуском потока
        self._model_loading = True
        try:
            self._initialize_model()
        except Exception as e:
            logger.error(f"Ошибка при фоновой загрузке модели: {e}")
            # Намеренное защитное присвоение: _initialize_model уже устанавливает
            # self._model_error перед повторным выбросом исключения, но это присвоение
            # страхует от исключений, возникших вне _initialize_model в данном блоке.
            self._model_error = e
        finally:
            self._initialization_event.set()
            self._model_loading = False
    
    def _raise_model_loading_timeout(self, elapsed_seconds: float, extra_context: str = ""):
        """Вспомогательный метод для унифицированного поднятия GigaTimeoutError при загрузке модели"""
        raise GigaTimeoutError(
            f"Превышено время ожидания загрузки модели ({elapsed_seconds:.1f} сек). "
            f"Возможно, модель скачивается с HuggingFace или сервер перегружен. "
            f"Попробуйте повторить запрос позже.{extra_context}",
            timeout_seconds=settings.model_loading_timeout,
            operation="model_loading",
            elapsed_seconds=int(elapsed_seconds)
        )

    def _ensure_model_loaded(self, max_retries: int = 1):
        """Гарантирует, что модель загружена с retry при таймауте"""
        # Если модель уже загружена, возвращаемся сразу
        if self._model_initialized and self.model is not None:
            return

        # Если есть ошибка загрузки, бросаем исключение
        if self._model_error:
            raise ModelLoadError(
                f"Ошибка загрузки модели: {self._model_error}",
                model_name=self.model_name
            )

        # Если модель сейчас загружается, ждем завершения с retry
        if self._model_loading:
            wait_start = time.time()
            logger.info(
                "Модель загружается в другом потоке, ждем завершения... "
                f"(таймаут: {settings.model_loading_timeout} сек, попыток: {max_retries + 1})"
            )

            for attempt in range(max_retries + 1):
                # Вычисляем оставшийся бюджет времени для текущей попытки
                elapsed = time.time() - wait_start
                attempt_timeout = max(0, settings.model_loading_timeout - elapsed)
                if attempt_timeout <= 0:
                    # Бюджет времени исчерпан - бросаем GigaTimeoutError
                    total_elapsed = time.time() - wait_start
                    self._raise_model_loading_timeout(total_elapsed)
                
                if self._initialization_event.wait(timeout=attempt_timeout):
                    # Загрузка завершена - пересчитываем elapsed после wait
                    elapsed = time.time() - wait_start
                    
                    # Проверяем состояние после завершения
                    if self._model_error:
                        raise ModelLoadError(
                            f"Ошибка загрузки модели: {self._model_error}",
                            model_name=self.model_name
                        )
                    if not self._model_initialized or self.model is None:
                        raise ModelLoadError(
                            "Модель не инициализирована после завершения загрузки",
                            model_name=self.model_name
                        )
                    logger.info(f"Модель загружена за {elapsed:.1f} секунд")
                    return
                
                # Таймаут - пересчитываем elapsed и логируем
                elapsed = time.time() - wait_start
                if attempt < max_retries:
                    remaining = max(0, settings.model_loading_timeout - elapsed)
                    logger.warning(
                        f"Таймаут ожидания загрузки модели ({elapsed:.1f} сек), "
                        f"повторная попытка {attempt + 1}/{max_retries} (оставшийся бюджет: {remaining:.1f} сек)..."
                    )
                else:
                    total_elapsed = time.time() - wait_start
                    self._raise_model_loading_timeout(total_elapsed)
            # Если вышли из цикла без возврата/исключения - это тоже таймаут
            total_elapsed = time.time() - wait_start
            self._raise_model_loading_timeout(total_elapsed)
        
        # Если дошли сюда, значит нужно загрузить модель синхронно
        with self._loading_lock:
            # Двойная проверка после получения лока
            if self._model_initialized or self._model_loading:
                return
            
            load_start = time.time()
            self._model_loading = True
            try:
                logger.info(f"Начинаем загрузку модели {self.model_name}...")
                self._initialize_model()
                load_time = time.time() - load_start
                logger.info(f"Модель {self.model_name} загружена за {load_time:.1f} секунд")
            except Exception as e:
                load_time = time.time() - load_start
                logger.error(f"Ошибка загрузки модели после {load_time:.1f} секунд: {e}")
                self._model_error = e
                raise
            finally:
                self._model_loading = False
                self._initialization_event.set()
    
    def _initialize_model(self):
        """Инициализация модели GigaAM"""
        with self._model_lock:
            if self._model_initialized:
                return
                
            try:
                logger.info(f"Загрузка модели {self.model_name}...")
                self._log_runtime_versions()
                
                # Установка HF токена из настроек или переменной окружения
                hf_token = settings.hf_token or os.getenv("HF_TOKEN")
                if hf_token and hf_token != "your_token_here":
                    os.environ["HF_TOKEN"] = hf_token
                    logger.info("HF_TOKEN установлен из конфигурации")
                else:
                    logger.warning("HF_TOKEN не найден или не настроен. Длинные аудио могут не работать.")
                    logger.warning("Получите токен на https://huggingface.co/settings/tokens")
                    logger.warning("Примите условия: https://huggingface.co/pyannote/segmentation-3.0")
                
                # Предзагрузка pyannote модели (опционально)
                if settings.preload_pyannote_model:
                    self._preload_pyannote_model()
                else:
                    logger.info("Предзагрузка pyannote отключена (preload_pyannote_model=false). Модель загрузится при первом использовании longform.")
                
                self.model = self._load_model_with_recovery()
                self._model_initialized = True
                self._model_error = None
                logger.info("Модель успешно загружена")
            except Exception as e:
                logger.error(f"Ошибка при загрузке модели: {e}")
                self._model_initialized = False
                self._model_error = e
                raise

    def _log_runtime_versions(self):
        """Логирует версии ключевых библиотек для диагностики окружения."""
        logger.info(
            "Runtime versions: python=%s, gigaam=%s, torch=%s, torchaudio=%s",
            os.sys.version.split(" ")[0],
            getattr(gigaam, "__version__", "unknown"),
            getattr(torch, "__version__", "unknown"),
            getattr(torchaudio, "__version__", "unknown"),
        )

    def _preload_pyannote_model(self):
        """Предзагрузка pyannote модели для проверки доступа"""
        try:
            from pyannote.audio import Model
            hf_token = os.getenv("HF_TOKEN")
            
            if not hf_token or hf_token == "your_token_here":
                logger.warning("Пропускаем предзагрузку pyannote - HF_TOKEN не настроен")
                return
            
            logger.info("Проверка доступа к pyannote/segmentation-3.0...")
            model = Model.from_pretrained(
                "pyannote/segmentation-3.0",
                token=hf_token
            )
            logger.info("Pyannote модель успешно загружена")
        except Exception as e:
            logger.warning(f"Ошибка при загрузке pyannote модели: {e}")
            logger.warning("Убедитесь что:")
            logger.warning("1. HF_TOKEN установлен в переменных окружения Spaces")
            logger.warning("2. Вы приняли условия: https://huggingface.co/pyannote/segmentation-3.0")
            logger.warning("3. Токен имеет права на чтение")
            # Не бросаем исключение, чтобы приложение могло работать без longform
    
    def _load_model_with_recovery(self):
        """Загрузка модели с восстановлением после поврежденного кэша."""
        try:
            return gigaam.load_model(self.model_name)
        except AssertionError as e:
            error_text = str(e)
            if "Model checksum failed" not in error_text:
                raise

            cache_path = Path.home() / ".cache" / "gigaam" / f"{self.model_name}.ckpt"
            logger.warning("Обнаружен поврежденный кэш модели, очищаем и пробуем заново")
            try:
                cache_path.unlink(missing_ok=True)
            except Exception as cleanup_error:
                logger.warning(f"Не удалось удалить кэш модели: {cleanup_error}")

            return gigaam.load_model(self.model_name)
    
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Распознавание речи из аудиофайла с thread-safe доступом к модели
        
        Args:
            audio_path: Путь к аудиофайлу
            
        Returns:
            Словарь с результатом распознавания
        """
        try:
            logger.info(f"Начало распознавания файла: {os.path.basename(audio_path)}")
            
            # Гарантируем, что модель загружена
            self._ensure_model_loaded()
            
            if not self._model_initialized or self.model is None:
                return {
                    "success": False,
                    "error": {
                        "code": "MODEL_LOAD_ERROR",
                        "message": "Модель не инициализирована"
                    }
                }
            
            # Используем ThreadPoolExecutor для thread-safe доступа к модели
            future = self._executor.submit(self._transcribe_sync, audio_path)
            
            # Ждем результат с таймаутом
            try:
                utterances = future.result(timeout=settings.transcription_timeout)
            except TimeoutError:
                future.cancel()  # Отменяем задачу при таймауте
                return {
                    "success": False,
                    "error": {
                        "code": "TIMEOUT_ERROR",
                        "message": f"Превышено время распознавания ({settings.transcription_timeout} секунд)"
                    }
                }
            
            result = {
                "success": True,
                "segments": [],
                "total_duration": 0,
                "skipped_segments": []  # Информация о пропущенных сегментах
            }
            
            logger.info(
                f"Получено utterances от модели: {len(utterances) if utterances else 0}, "
                f"тип: {type(utterances).__name__}"
            )
            
            for utt in utterances:
                try:
                    start, end, text = self._extract_utterance_fields(utt)
                except ValueError as parse_error:
                    # Собираем безопасную информацию о пропущенном сегменте
                    safe_utt_info = f"type={type(utt).__name__}"
                    if isinstance(utt, dict):
                        safe_utt_info += f", keys={list(utt.keys())}"
                    
                    skipped_info = {
                        "error": str(parse_error),
                        "utterance_info": safe_utt_info
                    }
                    result["skipped_segments"].append(skipped_info)
                    logger.warning("Пропущен сегмент с неподдерживаемым форматом: %s; %s", parse_error, safe_utt_info)
                    continue

                segment = {
                    "text": text,
                    "start": start,
                    "end": end,
                    "start_formatted": gigaam.format_time(start),
                    "end_formatted": gigaam.format_time(end),
                    "duration": end - start
                }
                result["segments"].append(segment)
                result["total_duration"] = max(result["total_duration"], end)
            
            # Формируем final_transcript из сегментов
            full_text_parts = []
            for segment in result["segments"]:
                seg_text = segment.get("text", "").strip()
                if seg_text:
                    full_text_parts.append(seg_text)
            result["final_transcript"] = " ".join(full_text_parts).strip()
            
            logger.info(
                f"Распознавание завершено. Сегментов: {len(result['segments'])}, "
                f"пропущено: {len(result['skipped_segments'])}, "
                f"final_transcript_length: {len(result.get('final_transcript', ''))}"
            )
            return result
            
        except (ModelLoadError, GigaTimeoutError) as e:
            # Re-raise domain exceptions to propagate to HTTP layer
            logger.error(f"Domain exception during transcription: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при распознавании аудио: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _extract_utterance_fields(utterance: Any) -> tuple[float, float, str]:
        """
        Извлекает start/end/text из utterance в разных форматах ответа модели.
        Поддерживает:
        - dict с ключами "boundaries"/"transcription"
        - объекты с атрибутами boundaries/transcription
        - boundaries как tuple/list [start, end] или объект Segment с .start/.end
        """
        if isinstance(utterance, dict):
            # Популярные варианты имен полей
            if "start" in utterance and "end" in utterance:
                start = to_safe_float(utterance["start"])
                end = to_safe_float(utterance["end"])
                if start is not None and end is not None:
                    text = utterance.get("transcription") or utterance.get("text") or ""
                    return start, end, str(text)
            boundaries = utterance.get("boundaries") or utterance.get("segment") or utterance.get("timestamp")
            text = utterance.get("transcription") or utterance.get("text") or ""
        else:
            # Вариант с объектом, где start/end доступны напрямую
            if hasattr(utterance, "start") and hasattr(utterance, "end"):
                start = to_safe_float(getattr(utterance, "start"))
                end = to_safe_float(getattr(utterance, "end"))
                if start is not None and end is not None:
                    text = getattr(utterance, "transcription", None) or getattr(utterance, "text", None) or ""
                    return start, end, str(text)

            boundaries = (
                getattr(utterance, "boundaries", None)
                or getattr(utterance, "segment", None)
                or getattr(utterance, "timestamp", None)
            )
            text = getattr(utterance, "transcription", None) or getattr(utterance, "text", None) or ""

            # Иногда utterance приходит как tuple/list вида (segment, text)
            if boundaries is None and isinstance(utterance, (list, tuple)) and len(utterance) >= 2:
                candidate_segment, candidate_text = utterance[0], utterance[1]
                if hasattr(candidate_segment, "start") and hasattr(candidate_segment, "end"):
                    start = to_safe_float(candidate_segment.start)
                    end = to_safe_float(candidate_segment.end)
                    if start is not None and end is not None:
                        return start, end, str(candidate_text or "")
                if isinstance(candidate_segment, (list, tuple)) and len(candidate_segment) >= 2:
                    start = to_safe_float(candidate_segment[0])
                    end = to_safe_float(candidate_segment[1])
                    if start is not None and end is not None:
                        return start, end, str(candidate_text or "")

        if boundaries is None:
            raise ValueError("Utterance не содержит boundaries/segment/start-end")

        # pyannote Segment и похожие объекты с .start/.end
        if hasattr(boundaries, "start") and hasattr(boundaries, "end"):
            start = to_safe_float(boundaries.start)
            end = to_safe_float(boundaries.end)
        else:
            try:
                start_raw, end_raw = boundaries
                start = to_safe_float(start_raw)
                end = to_safe_float(end_raw)
            except Exception as exc:
                raise ValueError(f"Неподдерживаемый формат boundaries: {type(boundaries)}") from exc

        if start is None or end is None:
            raise ValueError("Не удалось конвертировать start/end в числа")
        
        if end < start:
            raise ValueError(f"end ({end}) должен быть >= start ({start})")

        return start, end, str(text or "")
    
    def _transcribe_sync(self, audio_path: str):
        """Синхронное распознавание в отдельном потоке"""
        logger.info(f"Начало распознавания: {audio_path}")
        
        # Проверяем существование файла
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")
        
        # Проверяем размер файла
        file_size = os.path.getsize(audio_path)
        logger.info(f"Размер аудиофайла: {file_size} bytes")
        
        # Сначала пробуем передать путь к файлу
        try:
            with self._model_lock:
                raw_result = self.model.transcribe_longform(audio_path)
                
                # Конвертируем результат в список если это объект LongformTranscriptionResult
                if not isinstance(raw_result, (list, tuple)):
                    try:
                        result = list(raw_result)
                    except TypeError:
                        if hasattr(raw_result, 'segments'):
                            result = list(raw_result.segments)
                        elif hasattr(raw_result, 'utterances'):
                            result = list(raw_result.utterances)
                        else:
                            result = [raw_result]
                else:
                    result = list(raw_result)
                
                logger.info(f"Распознавание успешно завершено, сегментов: {len(result) if result else 0}")
                return result
        except (RuntimeError, ValueError, OSError) as model_error:
            # Для ошибок модели/обработки используем fallback с librosa
            # Используем обычный transcribe вместо transcribe_longform, чтобы избежать загрузки pyannote
            logger.info(f"Не удалось распознать по пути к файлу (ошибка модели): {model_error}")
            logger.info("Пробуем использовать обычный transcribe с загруженными аудиоданными")
            
            # Загружаем аудиоданные с помощью librosa ВНЕ блокировки
            import librosa
            import torch
            audio_data, sample_rate = librosa.load(audio_path, sr=16000, mono=True)
            logger.info(f"Аудиоданные загружены: длина={len(audio_data)}, sample_rate={sample_rate}")
            
            # Конвертируем в тензор torch и передаем в обычный transcribe
            with self._model_lock:
                audio_tensor = torch.from_numpy(audio_data).float()
                raw_result = self.model.transcribe(audio_tensor)
                
                # Обычный transcribe возвращает строку, конвертируем в формат сегментов
                if isinstance(raw_result, str):
                    # Создаем один сегмент с полным текстом
                    duration = len(audio_data) / sample_rate
                    result = [{
                        "start": 0.0,
                        "end": duration,
                        "text": raw_result
                    }]
                elif not isinstance(raw_result, (list, tuple)):
                    try:
                        result = list(raw_result)
                    except TypeError:
                        if hasattr(raw_result, 'segments'):
                            result = list(raw_result.segments)
                        elif hasattr(raw_result, 'utterances'):
                            result = list(raw_result.utterances)
                        else:
                            result = [raw_result]
                else:
                    result = list(raw_result)
                
                logger.info(f"Распознавание успешно завершено, сегментов: {len(result) if result else 0}")
                return result
    
    def format_transcription_text(self, result: Dict[str, Any]) -> str:
        """
        Форматирование результата в текстовый формат с временными метками
        
        Args:
            result: Результат распознавания
            
        Returns:
            Отформатированный текст
        """
        if not result.get("success"):
            return f"Ошибка распознавания: {result.get('error', 'Неизвестная ошибка')}"
        
        lines = []
        for segment in result["segments"]:
            line = f"[{segment['start_formatted']} - {segment['end_formatted']}]: {segment['text']}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели"""
        return {
            "model_name": self.model_name,
            "status": "loaded" if self._model_initialized and self.model else "not_loaded",
            "supported_formats": settings.allowed_audio_formats,
            "max_file_size_mb": settings.max_file_size // (1024 * 1024),
            "transcription_timeout": settings.transcription_timeout
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья модели"""
        return {
            "model_loaded": self._model_initialized and self.model is not None,
            "model_name": self.model_name,
            "model_loading": self._model_loading,
            "model_error": str(self._model_error) if self._model_error else None,
            "thread_pool_active": not self._executor._shutdown,
            "initialization_complete": self._initialization_event.is_set()
        }
    
    def get_loading_status(self) -> Dict[str, Any]:
        """Получение детального статуса загрузки модели"""
        return {
            "initialized": self._model_initialized,
            "loading": self._model_loading,
            "error": str(self._model_error) if self._model_error else None,
            "waiting_for_init": not self._initialization_event.is_set()
        }

# Глобальный экземпляр сервиса
transcription_service = TranscriptionService()
