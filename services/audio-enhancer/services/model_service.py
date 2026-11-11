"""Модуль для работы с моделями машинного обучения."""

import logging
import time
from typing import Optional, Tuple

import torch
import librosa
import numpy as np

from config.settings import config
from utils.error_handlers import ModelLoadError
from utils.logging_utils import timing_logger, model_logger

logger = logging.getLogger(__name__)


class ModelManager:
    """Менеджер для загрузки и управления ML моделями."""
    
    def __init__(self):
        self.vad_model = None
        self.vad_utils = None
        self.deepfilter_model = None
        self.deepfilter_df_state = None
        
        # Флаги доступности
        self.vad_available = False
        self.deepfilter_available = False
        self.wpe_available = False
        
        # Загружаем модели при инициализации
        self._load_models()
    
    def _load_models(self):
        """Загружает все модели."""
        self._load_vad_model()
        self._load_deepfilter_model()
        self._check_wpe_availability()
        # Pyannote не нужен - диаризация обрабатывается в другом сервисе
    
    @timing_logger("vad_model_load")
    def _load_vad_model(self):
        """Загружает Silero VAD модель."""
        try:
            self.vad_model, self.vad_utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            
            (get_speech_timestamps, save_audio, read_audio, 
             VADIterator, collect_chunks) = self.vad_utils
            
            self.vad_available = True
            model_logger.log_model_load("silero_vad", 0, True)
            logger.info("✓ Silero VAD модель загружена")
            
        except Exception as e:
            self.vad_available = False
            model_logger.log_model_load("silero_vad", 0, False)
            logger.warning(f"Не удалось загрузить Silero VAD: {e}")
    
    @timing_logger("deepfilter_model_load")
    def _load_deepfilter_model(self):
        """Загружает DeepFilterNet модель."""
        try:
            from df.enhance import enhance, init_df
            from df.io import resample
            
            self.deepfilter_model, self.deepfilter_df_state, _ = init_df()
            self.deepfilter_available = True
            model_logger.log_model_load("deepfilter", 0, True)
            logger.info("✓ DeepFilterNet модель загружена")
            
        except ImportError:
            self.deepfilter_available = False
            logger.warning("DeepFilterNet не установлен")
        except Exception as e:
            self.deepfilter_available = False
            model_logger.log_model_load("deepfilter", 0, False)
            logger.warning(f"Не удалось загрузить DeepFilterNet: {e}")
    
    def _check_wpe_availability(self):
        """Проверяет доступность WPE."""
        try:
            from nara_wpe import wpe_v8 as wpe
            self.wpe_available = True
            logger.info("✓ WPE доступен")
        except ImportError:
            self.wpe_available = False
            logger.warning("WPE не установлен")
        except Exception as e:
            self.wpe_available = False
            logger.warning(f"WPE недоступен: {e}")
    
    
    def get_vad_timestamps(self, audio: np.ndarray, sr: int) -> list:
        """
        Получает временные метки речи с помощью VAD.
        
        Args:
            audio: Аудио данные
            sr: Частота дискретизации
            
        Returns:
            Список временных меток речи
        """
        if not self.vad_available or self.vad_model is None:
            return []
        
        try:
            # Ресемплинг до 16kHz для VAD
            if sr != 16000:
                audio_16k = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            else:
                audio_16k = audio
            
            audio_tensor = torch.from_numpy(audio_16k).float()
            get_speech_timestamps = self.vad_utils[0]
            
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                self.vad_model,
                sampling_rate=16000,
                threshold=config.VAD_SETTINGS["threshold"],
                min_speech_duration_ms=config.VAD_SETTINGS["min_speech_duration_ms"],
                min_silence_duration_ms=config.VAD_SETTINGS["min_silence_duration_ms"],
            )
            
            return speech_timestamps
            
        except Exception as e:
            logger.error("VAD processing failed: %s", e)
            return []
    
    def apply_deepfilter(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Применяет DeepFilterNet шумоподавление.
        
        Args:
            audio: Аудио данные
            sr: Частота дискретизации
            
        Returns:
            Обработанное аудио
        """
        if not self.deepfilter_available or self.deepfilter_model is None:
            raise ModelLoadError("deepfilter", "Model not loaded")
        
        try:
            # Ресемплинг до 48kHz для DeepFilterNet
            if sr != 48000:
                audio_48k = librosa.resample(audio, orig_sr=sr, target_sr=48000)
            else:
                audio_48k = audio
            
            audio_48k_tensor = torch.from_numpy(audio_48k).unsqueeze(0)
            
            from df.enhance import enhance
            enhanced = enhance(self.deepfilter_model, self.deepfilter_df_state, audio_48k_tensor)
            audio_48k = enhanced.squeeze(0).numpy()
            
            # Возврат к исходной частоте
            if sr != 48000:
                audio = librosa.resample(audio_48k, orig_sr=48000, target_sr=sr)
            else:
                audio = audio_48k
            
            return audio
            
        except Exception as e:
            logger.error("DeepFilter processing failed: %s", e)
            raise ModelLoadError("deepfilter", f"Processing failed: {str(e)}")
    
    def apply_wpe(self, audio: np.ndarray) -> np.ndarray:
        """
        Применяет WPE дереверберацию.
        
        Args:
            audio: Аудио данные
            
        Returns:
            Обработанное аудио
        """
        if not self.wpe_available:
            raise ModelLoadError("wpe", "WPE not available")
        
        try:
            from nara_wpe import wpe_v8 as wpe
            
            stft = librosa.stft(audio, n_fft=512, hop_length=128)
            stft_wpe = wpe(stft[np.newaxis, :, :], taps=10, delay=3, iterations=3)
            audio = librosa.istft(stft_wpe[0], hop_length=128, length=len(audio))
            
            return audio
            
        except Exception as e:
            logger.error("WPE processing failed: %s", e)
            raise ModelLoadError("wpe", f"Processing failed: {str(e)}")
    
    @property
    def pyannote_available(self) -> bool:
        """
        Возвращает доступность Pyannote для диаризации.
        
        Returns:
            False - диаризация обрабатывается в другом сервисе
        """
        return False
    
    def run_diarization(self, audio: np.ndarray, sr: int) -> dict:
        """
        Запускает диаризацию аудио.
        
        Args:
            audio: Аудио данные
            sr: Частота дискретизации
            
        Returns:
            Результат диаризации
            
        Raises:
            ModelLoadError: Always - диаризация не поддерживается в этом сервисе
        """
        raise ModelLoadError("pyannote", "Diarization is handled by a separate service")
    
    
    def get_model_status(self) -> dict:
        """
        Возвращает статус всех моделей.
        
        Returns:
            Словарь со статусами моделей
        """
        return {
            "vad_loaded": self.vad_available,
            "deepfilter_loaded": self.deepfilter_available,
            "wpe_available": self.wpe_available,
            "pyannote_loaded": False,  # Диаризация обрабатывается в другом сервисе
        }


# Глобальный экземпляр менеджера моделей
model_manager = ModelManager()
