"""API эндпоинты audio-enhancer сервиса."""

import asyncio
import base64
import io
import logging
import time
from typing import Dict, Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from config.settings import config
from utils.audio_utils import (
    read_upload_bytes_capped, 
    validate_audio_file
)
from utils.error_handlers import (
    setup_exception_handlers,
    handle_audio_processing_error,
    ModelLoadError
)
from utils.logging_utils import request_logger, processing_logger

# Импорты для телефонии
try:
    from services.telephony_service import TelephonyProcessor
    TELEPHONY_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✓ Telephony сервис доступен")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Telephony service недоступен: {e}")
    TELEPHONY_AVAILABLE = False

# Ленивые импорты для тяжелых библиотек
def get_librosa():
    try:
        import librosa
        return librosa
    except ImportError:
        return None

def get_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None

def get_soundfile():
    try:
        import soundfile as sf
        return sf
    except ImportError:
        return None

# Импорты сервисов с проверкой
try:
    from services.audio_service import audio_processor
    AUDIO_PROCESSOR_AVAILABLE = True
except ImportError:
    audio_processor = None
    AUDIO_PROCESSOR_AVAILABLE = False

try:
    from services.model_service import model_manager
    MODEL_MANAGER_AVAILABLE = True
except ImportError:
    model_manager = None
    MODEL_MANAGER_AVAILABLE = False

# Создание FastAPI приложения
app = FastAPI(
    title=config.APP_NAME,
    version="2.0.0",
    debug=config.DEBUG,
    description="Продвинутый микросервис для улучшения качества аудио перед распознаванием речи",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production настроить конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Установка обработчиков исключений
setup_exception_handlers(app)


def get_processing_time():
    """Dependency для получения времени начала обработки."""
    return time.time()


@app.get("/")
async def root():
    """
    Корневой endpoint для проверки работоспособности.
    
    Returns:
        Информация о сервисе
    """
    return {
        "service": "Audio Enhancer v2.0",
        "status": "running",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "config": {
            "max_file_size_mb": config.MAX_UPLOAD_BYTES / 1024 / 1024,
            "max_audio_seconds": config.MAX_AUDIO_SECONDS,
            "cache_enabled": config.ENABLE_CACHE,
            "metrics_enabled": config.ENABLE_METRICS,
        }
    }


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса.
    
    Returns:
        Статус сервиса и загруженных моделей
    """
    model_status = {}
    if MODEL_MANAGER_AVAILABLE and model_manager is not None:
        try:
            model_status = model_manager.get_model_status()
        except Exception as e:
            logger.warning(f"Ошибка получения статуса моделей: {e}")
            model_status = {"error": str(e)}
    else:
        model_status = {"status": "unavailable", "message": "Model manager not available"}
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "models": model_status,
        "config": {
            "max_file_size_mb": config.MAX_UPLOAD_BYTES / 1024 / 1024,
            "max_audio_seconds": config.MAX_AUDIO_SECONDS,
        }
    }


@app.post("/enhance")
async def enhance_audio(
    file: UploadFile = File(..., description="Аудио файл для улучшения"),
    aggressiveness: str = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["aggressiveness"],
        description="Режим агрессивности обработки (light/medium/heavy)"
    ),
    use_deepfilter: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["use_deepfilter"],
        description="Применить DeepFilterNet (AI шумоподавление)"
    ),
    use_wpe: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["use_wpe"],
        description="Применить WPE (удаление реверберации)"
    ),
    noise_reduction: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["noise_reduction"],
        description="Применить классическое шумоподавление"
    ),
    normalize_volume: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["normalize_volume"],
        description="Нормализовать громкость (LUFS-based)"
    ),
    enhance_speech: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["enhance_speech"],
        description="Усилить речевые частоты"
    ),
    remove_silence: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["remove_silence"],
        description="Удалить длинные паузы"
    ),
    target_sample_rate: int = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["target_sample_rate"],
        ge=800,
        le=192000,
        description="Целевая частота дискретизации"
    ),
    use_compressor: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["use_compressor"],
        description="Применить динамическую компрессию"
    ),
    spectral_gating: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["spectral_gating"],
        description="Применить спектральный гейтинг"
    ),
    enable_diarization: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["enable_diarization"],
        description="Включить диаризацию"
    ),
    start_time: float = Depends(get_processing_time)
):
    """
    Улучшает качество аудио для ASR с использованием современных технологий.
    
    ## Parameters:
    - **file**: Аудио файл (WAV, MP3, FLAC, M4A, AAC, OGG, WEBM)
    - **aggressiveness**: Режим агрессивности (light/medium/heavy)
    - **use_deepfilter**: DeepFilterNet (нейросетевое шумоподавление, 48kHz)
    - **use_wpe**: WPE (удаление реверберации)
    - **noise_reduction**: Классическое шумоподавление (noisereduce)
    - **normalize_volume**: LUFS нормализация (-16 LUFS)
    - **enhance_speech**: Усиление речевых частот (300-3400 Hz)
    - **remove_silence**: Удаление пауз (Silero VAD)
    - **target_sample_rate**: Частота дискретизации (800-192000 Hz)
    - **use_compressor**: Динамическая компрессия (-16dB, 2:1)
    - **spectral_gating**: Спектральный гейтинг (консервативный)
    - **enable_diarization**: Диаризация (pyannote)
    
    ## Returns:
    - **JSON**: с аудио в base64 и метаданными
    - **или WAV файл**: если диаризация отключена
    
    ## Example:
    ```bash
    curl -X POST "http://localhost:7860/enhance" \\
      -F "file=@audio.mp3" \\
      -F "aggressiveness=light" \\
      -F "target_sample_rate=16000"
    ```
    """
    request_logger.log_request("POST", "/enhance", file_size=file.size)
    
    if not AUDIO_PROCESSOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Audio processing service unavailable. Please ensure audio_service is properly installed."
        )
    
    try:
        # Валидация файла
        validate_audio_file(file)
        
        # Чтение файла
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        
        # Параметры обработки
        # Валидация aggressiveness
        if aggressiveness and aggressiveness not in config.AGGRESSIVENESS_MODES and aggressiveness != "custom":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid aggressiveness value: {aggressiveness}. "
                       f"Must be one of: {list(config.AGGRESSIVENESS_MODES.keys())} or 'custom'"
            )
        
        # Применяем режим агрессивности если указан
        if aggressiveness in config.AGGRESSIVENESS_MODES:
            mode_settings = config.AGGRESSIVENESS_MODES[aggressiveness]
            # Начинаем с настроек режима, затем применяем пользовательские флаги
            params = {
                "use_deepfilter": mode_settings["use_deepfilter"],
                "use_wpe": mode_settings["use_wpe"],
                "noise_reduction": mode_settings["noise_reduction"],
                "normalize_volume": mode_settings["normalize_volume"],
                "enhance_speech": mode_settings["enhance_speech"],
                "use_compressor": mode_settings["use_compressor"],
                "spectral_gating": mode_settings["spectral_gating"],
                # Пользовательские флаги имеют приоритет
                "remove_silence": remove_silence,
                "target_sample_rate": target_sample_rate,
                "enable_diarization": enable_diarization,
                "aggressiveness": aggressiveness,
            }
        else:
            # Ручные настройки
            params = {
                "use_deepfilter": use_deepfilter,
                "use_wpe": use_wpe,
                "noise_reduction": noise_reduction,
                "normalize_volume": normalize_volume,
                "enhance_speech": enhance_speech,
                "remove_silence": remove_silence,
                "target_sample_rate": target_sample_rate,
                "use_compressor": use_compressor,
                "spectral_gating": spectral_gating,
                "enable_diarization": enable_diarization,
                "aggressiveness": "custom",
            }
        
        # Обработка аудио
        result = await asyncio.to_thread(
            audio_processor.enhance_audio,
            audio_bytes,
            **params
        )
        
        # Логирование ответа
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/enhance", 200, duration_ms)
        
        # Возврат результата
        if enable_diarization and "diarization" in result:
            return result
        else:
            # Возврат аудио файла
            import base64
            audio_bytes = base64.b64decode(result["audio_base64"])
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "attachment; filename=enhanced.wav",
                    "X-Processing-Time-ms": str(duration_ms),
                    "X-Original-Duration": str(result.get("original_duration", 0)),
                    "X-Original-Sample-Rate": str(result.get("original_sample_rate", 0)),
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/enhance", 500, duration_ms)
        logger.error("Ошибка обработки аудио", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Audio processing failed"
        ) from e


@app.post("/denoise")
async def denoise_only(
    file: UploadFile = File(..., description="Аудио файл для шумоподавления"),
    stationary: bool = Form(
        default=True,
        description="Стационарный шум (True) или нестационарный (False)"
    ),
    prop_decrease: float = Form(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Агрессивность шумоподавления (0-1)"
    ),
    start_time: float = Depends(get_processing_time)
):
    """
    Только шумоподавление (быстрый endpoint).
    
    ## Parameters:
    - **file**: Аудио файл
    - **stationary**: Стационарный шум (true) или нестационарный (false)
    - **prop_decrease**: Агрессивность шумоподавления (0-1)
    
    ## Returns:
    - **WAV файл**: обработанный аудио
    
    ## Example:
    ```bash
    curl -X POST "http://localhost:7860/denoise" \\
      -F "file=@audio.mp3" \\
      -F "stationary=true" \\
      -F "prop_decrease=0.8" \\
      -o denoised.wav
    ```
    """
    request_logger.log_request("POST", "/denoise", file_size=file.size)
    
    if not AUDIO_PROCESSOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Audio processing service unavailable. Please ensure audio_service is properly installed."
        )
    
    try:
        validate_audio_file(file)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        
        result_bytes = await asyncio.to_thread(
            audio_processor.denoise_only,
            audio_bytes,
            stationary=stationary,
            prop_decrease=prop_decrease
        )
        
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/denoise", 200, duration_ms)
        
        return Response(
            content=result_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=denoised.wav",
                "X-Processing-Time-ms": str(duration_ms),
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/denoise", 500, duration_ms)
        logger.error("Ошибка шумоподавления", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Audio processing failed"
        ) from e


@app.post("/preprocess")
@app.post("/api/preprocess")
async def preprocess_audio(
    file: UploadFile = File(..., description="Аудио файл для предобработки"),
    target_sample_rate: int = Form(
        default=16000,
        ge=800,
        le=192000,
        description="Целевая частота дискретизации"
    ),
    return_audio_base64: bool = Form(
        default=True,
        description="Возвращать аудио в base64"
    ),
    use_wpe: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["use_wpe"],
        description="Применять WPE дереверберацию"
    ),
    use_deepfilter: bool = Form(
        default=config.DEFAULT_ENHANCE_SETTINGS["use_deepfilter"],
        description="Применять DeepFilter шумоподавление"
    ),
    start_time: float = Depends(get_processing_time)
):
    """
    Quality-first preprocessing endpoint для внешнего orchestrator.
    
    Возвращает preprocess_metadata + (опционально) audio_base64.
    
    ## Parameters:
    - **file**: Аудио файл
    - **target_sample_rate**: Целевая частота дискретизации
    - **return_audio_base64**: Возвращать аудио в base64
    - **use_wpe**: Применять WPE дереверберацию
    - **use_deepfilter**: Применять DeepFilter шумоподавление
    
    ## Returns:
    - **JSON**: с метаданными и опционально аудио
    
    ## Example:
    ```bash
    curl -X POST "http://localhost:7860/preprocess" \\
      -F "file=@audio.mp3" \\
      -F "target_sample_rate=16000" \\
      -F "return_audio_base64=true"
    ```
    """
    request_logger.log_request("POST", "/preprocess", file_size=file.size)
    
    if not AUDIO_PROCESSOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Audio processing service unavailable. Please ensure audio_service is properly installed."
        )
    
    try:
        validate_audio_file(file)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        
        result = await asyncio.to_thread(
            audio_processor.preprocess_audio,
            audio_bytes,
            target_sample_rate=target_sample_rate,
            return_audio_base64=return_audio_base64,
            use_wpe=use_wpe,
            use_deepfilter=use_deepfilter,
        )
        
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/preprocess", 200, duration_ms)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/preprocess", 500, duration_ms)
        logger.error("Ошибка preprocessing", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Preprocessing failed"
        ) from e


@app.post("/diarize")
async def diarize_audio(
    file: UploadFile = File(..., description="Аудио файл для диаризации"),
    start_time: float = Depends(get_processing_time)
):
    """
    Диаризация аудио: сегментация, детекция смены спикера, детекция перекрытий.
    
    ## Parameters:
    - **file**: Аудио файл
    
    ## Returns:
    - **JSON**: с сегментами, сменами спикеров и перекрытиями
    
    ## Example:
    ```bash
    curl -X POST "http://localhost:7860/diarize" \\
      -F "file=@conversation.wav"
    ```
    """
    request_logger.log_request("POST", "/diarize", file_size=file.size)
    
    if not model_manager.pyannote_available:
        raise HTTPException(
            status_code=503,
            detail="Pyannote не доступен. Установите HF_TOKEN в переменные окружения."
        )
    
    try:
        validate_audio_file(file)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        
        from utils.audio_utils import load_audio_with_duration_check
        audio, sr = load_audio_with_duration_check(audio_bytes)
        
        result = await asyncio.to_thread(
            model_manager.run_diarization,
            audio,
            sr
        )
        
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/diarize", 200, duration_ms)
        
        return result
    
    except ModelLoadError as e:
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/diarize", 503, duration_ms)
        logger.warning(f"Диаризация недоступна: {e!s}")
        raise HTTPException(
            status_code=503,
            detail=f"Diarization service unavailable: {e!s}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        request_logger.log_response("POST", "/diarize", 500, duration_ms)
        logger.error("Ошибка диаризации", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Diarization failed"
        ) from e


@app.get("/models/status")
async def get_models_status():
    """
    Получает статус всех ML моделей.
    
    Returns:
        JSON с информацией о загруженных моделях
    """
    if MODEL_MANAGER_AVAILABLE and model_manager is not None:
        try:
            return model_manager.get_model_status()
        except Exception as e:
            logger.warning(f"Ошибка получения статуса моделей: {e}")
            return {"error": str(e)}
    else:
        return {"status": "unavailable", "message": "Model manager not available"}


@app.get("/config")
async def get_config():
    """
    Получает текущую конфигурацию сервиса.
    
    Returns:
        JSON с конфигурацией
    """
    return {
        "app_name": config.APP_NAME,
        "debug": config.DEBUG,
        "max_file_size_mb": config.MAX_UPLOAD_BYTES / 1024 / 1024,
        "max_audio_seconds": config.MAX_AUDIO_SECONDS,
        "cache_enabled": config.ENABLE_CACHE,
        "cache_ttl_seconds": config.CACHE_TTL_SECONDS,
        "metrics_enabled": config.ENABLE_METRICS,
        "default_settings": config.DEFAULT_ENHANCE_SETTINGS,
        "allowed_mime_types": list(config.ALLOWED_MIME_TYPES),
    }


# Телефонные эндпоинты
@app.post("/telephony/enhance")
async def enhance_telephony_audio(
    file: UploadFile = File(...),
    format_type: str = Form("auto"),
    duplex: bool = Form(False),
    apply_telephony_filters: bool = Form(True),
    target_sample_rate: int = Form(16000, ge=800, le=48000),
):
    """
    Улучшение телефонного аудио с поддержкой кодеков.
    
    Args:
        file: Аудио файл (G.711, G.729, Opus, WAV)
        format_type: Тип формата ('auto', 'g711', 'g729', 'opus', 'wav')
        duplex: Дуплексное аудио (два канала)
        apply_telephony_filters: Применять телефонные фильтры
        target_sample_rate: Целевая частота дискретизации
        
    Returns:
        JSON с улучшенным аудио и метаданными
    """
    if not TELEPHONY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Telephony service не доступен"
        )
    
    try:
        request_logger.log_request("POST", "/telephony/enhance", file_size=file.size)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        return await asyncio.to_thread(
            process_telephony_enhance, 
            audio_bytes, format_type, duplex, apply_telephony_filters, target_sample_rate
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка обработки телефонного аудио", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Telephony processing failed",
        ) from e


@app.post("/telephony/convert")
async def convert_telephony_format(
    file: UploadFile = File(...),
    from_format: str = Form("auto"),
    to_format: str = Form("wav"),
    sample_rate: int = Form(16000, ge=800, le=48000),
):
    """
    Конвертация телефонного формата в стандартный.
    
    Args:
        file: Аудио файл
        from_format: Исходный формат ('auto', 'g711', 'g729', 'opus')
        to_format: Целевой формат ('wav', 'mp3')
        sample_rate: Частота дискретизации
        
    Returns:
        WAV файл с конвертированным аудио
    """
    if not TELEPHONY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Telephony service не доступен"
        )
    
    try:
        request_logger.log_request("POST", "/telephony/convert", file_size=file.size)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        return await asyncio.to_thread(
            process_telephony_convert,
            audio_bytes, from_format, to_format, sample_rate
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка конвертации телефонного формата", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Format conversion failed",
        ) from e


@app.post("/telephony/split")
async def split_telephony_duplex(
    file: UploadFile = File(...),
    format_type: str = Form("auto"),
):
    """
    Разделение дуплексного аудио на два канала.
    
    Args:
        file: Стерео аудио файл (канал 1 - caller, канал 2 - callee)
        format_type: Тип формата
        
    Returns:
        JSON с разделенными каналами
    """
    if not TELEPHONY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Telephony service не доступен"
        )
    
    try:
        request_logger.log_request("POST", "/telephony/split", file_size=file.size)
        audio_bytes = await read_upload_bytes_capped(file, config.MAX_UPLOAD_BYTES)
        return await asyncio.to_thread(
            process_telephony_split,
            audio_bytes, format_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка разделения дуплексного аудио", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Duplex split failed",
        ) from e


def process_telephony_enhance(audio_bytes: bytes, format_type: str, duplex: bool, 
                           apply_filters: bool, target_sr: int) -> dict:
    """Обработка телефонного аудио с улучшением."""
    from services.telephony_service import TelephonyProcessor
    
    telephony = TelephonyProcessor()
    
    # Обработка телефонного аудио
    result = telephony.enhance_telephony_audio(
        audio_bytes, format_type, duplex
    )
    
    # Применение стандартных фильтров если нужно
    if apply_filters:
        for channel_name, channel_data in result.items():
            audio = channel_data['audio']
            sr = channel_data['sample_rate']
            
            # Применяем DeepFilterNet если доступен
            if model_manager.deepfilter_available:
                try:
                    audio = model_manager.apply_deepfilter(audio, sr)
                except Exception as e:
                    logger.warning(f"DeepFilterNet обработка не удалась: {e}")
            
            # Нормализация громкости
            try:
                import pyloudnorm as pyln
                meter = pyln.Meter(sr)
                loudness = meter.integrated_loudness(audio)
                if loudness > -16:
                    audio = pyln.normalize.loudness(audio, loudness, -16)
            except Exception as e:
                logger.warning(f"Нормализация громкости не удалась: {e}")
            
            # Ресемплинг если нужно
            if sr != target_sr:
                librosa = get_librosa()
                if librosa:
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
                    sr = target_sr  # Обновляем sr только после успешного ресемплинга
                else:
                    # Если librosa недоступен и ресемплинг необходим, оставляем исходную частоту
                    logger.warning(f"Ресемплинг с {sr}Hz до {target_sr}Hz не выполнен: librosa недоступен")
            
            result[channel_name]['audio'] = audio
            result[channel_name]['sample_rate'] = sr
    
    # Конвертация в байты для ответа
    response = {}
    for channel_name, channel_data in result.items():
        audio = channel_data['audio']
        sr = channel_data['sample_rate']
        
        # Конвертируем в 16-bit PCM
        np = get_numpy()
        if np is None:
            raise HTTPException(status_code=500, detail="NumPy library not available")
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Сохраняем в WAV
        sf = get_soundfile()
        if sf is None:
            raise HTTPException(status_code=500, detail="SoundFile library not available")
        with io.BytesIO() as buffer:
            sf.write(buffer, audio_int16, sr, format='WAV', subtype='PCM_16')
            response[channel_name] = base64.b64encode(buffer.getvalue()).decode()
    
    # Вычисляем реальную частоту дискретизации из обработанных данных
    actual_sample_rates = [data['sample_rate'] for data in result.values()]
    sample_rate = actual_sample_rates[0] if actual_sample_rates else target_sr
    
    return {
        "channels": response,
        "metadata": {
            "original_format": format_type,
            "duplex": duplex,
            "sample_rate": sample_rate,
            "duration": max(data['duration'] for data in result.values()),
            "telephony_filters_applied": apply_filters
        }
    }


def process_telephony_convert(audio_bytes: bytes, from_format: str, 
                         to_format: str, sample_rate: int) -> bytes:
    """Конвертация телефонного формата."""
    from services.telephony_service import TelephonyProcessor
    
    telephony = TelephonyProcessor()
    
    # Конвертируем в стандартный формат
    audio, sr = telephony.convert_telephony_format(audio_bytes, from_format)
    
    # Ресемплинг если нужно
    if sr != sample_rate:
        librosa = get_librosa()
        if librosa:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
            sr = sample_rate  # Обновляем sr только после успешного ресемплинга
        else:
            # Если librosa недоступен и ресемплинг необходим, оставляем исходную частоту
            logger.warning(f"Ресемплинг с {sr}Hz до {sample_rate}Hz не выполнен: librosa недоступен")
    
    # Конвертируем в 16-bit PCM
    np = get_numpy()
    if np is None:
        raise HTTPException(status_code=500, detail="NumPy library not available")
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # Сохраняем в нужном формате
    sf = get_soundfile()
    if sf is None:
        raise HTTPException(status_code=500, detail="SoundFile library not available")
    with io.BytesIO() as buffer:
        if to_format.lower() == "wav":
            sf.write(buffer, audio_int16, sr, format='WAV', subtype='PCM_16')
        elif to_format.lower() == "mp3":
            # Используем pydub для MP3
            from pydub import AudioSegment
            audio_seg = AudioSegment(
                audio_int16.tobytes(), 
                frame_rate=sr, 
                sample_width=2, 
                channels=1
            )
            audio_seg.export(buffer, format="mp3")
        else:
            raise ValueError(f"Unsupported target format: {to_format}")
        
        return buffer.getvalue()


def process_telephony_split(audio_bytes: bytes, format_type: str) -> dict:
    """Разделение дуплексного аудио."""
    from services.telephony_service import TelephonyProcessor
    
    telephony = TelephonyProcessor()
    
    # Конвертируем в стандартный формат
    audio, sr = telephony.convert_telephony_format(audio_bytes, format_type)
    
    # Разделяем каналы
    caller_audio, callee_audio = telephony.split_channels(audio)
    
    # Конвертируем в байты
    def audio_to_bytes(audio_data, name):
        np = get_numpy()
        if np is None:
            raise HTTPException(status_code=500, detail="NumPy library not available")
        audio_int16 = (audio_data * 32767).astype(np.int16)
        sf = get_soundfile()
        if sf is None:
            raise HTTPException(status_code=500, detail="SoundFile library not available")
        with io.BytesIO() as buffer:
            sf.write(buffer, audio_int16, sr, format='WAV', subtype='PCM_16')
            return base64.b64encode(buffer.getvalue()).decode()
    
    return {
        "caller": {
            "audio": audio_to_bytes(caller_audio, "caller"),
            "sample_rate": sr,
            "duration": len(caller_audio) / sr
        },
        "callee": {
            "audio": audio_to_bytes(callee_audio, "callee"), 
            "sample_rate": sr,
            "duration": len(callee_audio) / sr
        },
        "metadata": {
            "original_format": format_type,
            "channels_separated": True
        }
    }
