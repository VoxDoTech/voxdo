"""Обработка телефонных звонков и кодеков."""

import io
import logging
import numpy as np
import soundfile as sf
from typing import Optional, Tuple, Union
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class TelephonyProcessor:
    """Обработчик телефонных аудио с поддержкой различных кодеков."""
    
    def __init__(self):
        self.sample_rate = 8000  # Стандартная частота для телефонии
        self.channels = 1  # Моно для телефонии
        
    def convert_telephony_format(self, audio_data: bytes, format_type: str = "auto") -> Tuple[np.ndarray, int]:
        """
        Конвертирует аудио из телефонного формата в стандартный формат.
        
        Args:
            audio_data: Аудио данные в байтах
            format_type: Тип формата ('auto', 'g711', 'g729', 'opus', 'wav')
            
        Returns:
            Tuple[np.ndarray, int]: Аудио данные и частота дискретизации
        """
        try:
            if format_type == "auto":
                # Автоопределение формата
                format_type = self._detect_format(audio_data)
                
            if format_type == "g711":
                return self._convert_g711(audio_data)
            elif format_type == "g729":
                return self._convert_g729(audio_data)
            elif format_type == "opus":
                return self._convert_opus(audio_data)
            else:
                # WAV или другой стандартный формат
                return self._convert_wav(audio_data)
                
        except Exception as e:
            logger.error(f"Ошибка конвертации телефонного формата {format_type}: {e}")
            raise ValueError(f"Failed to convert telephony format: {e}")
    
    def _detect_format(self, audio_data: bytes) -> str:
        """Автоопределение формата аудио."""
        # Простая эвристика для определения формата
        if len(audio_data) < 100:
            return "g711"
        
        # Проверяем заголовки WAV
        if audio_data.startswith(b'RIFF') and audio_data[8:12] == b'WAVE':
            return "wav"
        
        # Проверяем Opus
        if b'OpusHead' in audio_data[:100]:
            return "opus"
            
        # По умолчанию считаем G.711
        return "g711"
    
    def _convert_g711(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Конвертация G.711 (A-law/μ-law) в PCM."""
        try:
            # Используем pydub для конвертации
            audio = AudioSegment(audio_data, sample_width=1, frame_rate=8000, channels=1)
            audio = audio.set_sample_width(2)  # 16-bit
            audio = audio.set_frame_rate(16000)  # Upsample до 16kHz
            
            samples = np.array(audio.get_array_of_samples())
            return samples.astype(np.float32) / 32768.0, 16000
            
        except Exception as e:
            logger.error(f"Ошибка конвертации G.711: {e}")
            # Fallback - простая конвертация
            return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0, 8000
    
    def _convert_g729(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Конвертация G.729 в PCM."""
        # G.729 требует специального декодера
        try:
            # Здесь должна быть библиотека для G.729
            # Пока используем заглушку
            logger.warning("G.729 декодер не реализован, используем заглушку")
            return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0, 8000
        except Exception as e:
            logger.error(f"Ошибка конвертации G.729: {e}")
            raise
    
    def _convert_opus(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Конвертация Opus в PCM."""
        try:
            # Используем pydub для Opus
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="opus")
            audio = audio.set_sample_width(2)  # 16-bit
            audio = audio.set_frame_rate(16000)  # Standard для ASR
            audio = audio.set_channels(1)  # Моно
            
            samples = np.array(audio.get_array_of_samples())
            return samples.astype(np.float32) / 32768.0, 16000
            
        except Exception as e:
            logger.error(f"Ошибка конвертации Opus: {e}")
            raise
    
    def _convert_wav(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Конвертация WAV в numpy array."""
        try:
            audio, sr = sf.read(io.BytesIO(audio_data))
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)  # Конвертируем в моно
            return audio.astype(np.float32), sr
        except Exception as e:
            logger.error(f"Ошибка конвертации WAV: {e}")
            raise
    
    def apply_telephony_filters(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Применяет фильтры специфичные для телефонии.
        
        Args:
            audio: Аудио данные
            sample_rate: Частота дискретизации
            
        Returns:
            np.ndarray: Обработанное аудио
        """
        try:
            # 1. High-pass фильтр для удаления низкочастотного шума линии
            from scipy import signal
            nyquist = sample_rate // 2
            low_cutoff = 300  # Стандарт для телефонии
            high_cutoff = 3400  # Стандарт для телефонии
            
            # Band-pass фильтр 300Hz-3400Hz
            low = low_cutoff / nyquist
            high = high_cutoff / nyquist
            b, a = signal.butter(4, [low, high], btype='band')
            audio = signal.filtfilt(b, a, audio)
            
            # 2. Подавление эха (простой эхо-компенсатор)
            audio = self._reduce_echo(audio, sample_rate)
            
            # 3. Нормализация громкости для телефонии
            audio = self._normalize_telephony_level(audio)
            
            return audio
            
        except Exception as e:
            logger.error(f"Ошибка применения телефонных фильтров: {e}")
            return audio
    
    def _reduce_echo(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Простое подавление эха."""
        try:
            # Простая эхо-компенсация
            delay_samples = int(0.1 * sample_rate)  # 100ms задержка
            decay_factor = 0.5
            
            echo_free = audio.copy()
            for i in range(delay_samples, len(audio)):
                echo_component = decay_factor * audio[i - delay_samples]
                echo_free[i] = audio[i] - echo_component
                
            return echo_free
        except Exception:
            return audio
    
    def _normalize_telephony_level(self, audio: np.ndarray) -> np.ndarray:
        """Нормализация уровня для телефонии."""
        try:
            # RMS нормализация для телефонных уровней
            rms = np.sqrt(np.mean(audio ** 2))
            target_rms = 0.1  # Целевой RMS для телефонии
            
            if rms > 0:
                gain = target_rms / rms
                gain = np.clip(gain, 0.1, 10.0)  # Ограничиваем усиление
                audio = audio * gain
                
            return audio
        except Exception:
            return audio
    
    def split_channels(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Разделяет дуплексное аудио на два канала.
        
        Args:
            audio: Стерео аудио (канал 1 - caller, канал 2 - callee)
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (caller_audio, callee_audio)
        """
        if len(audio.shape) == 1:
            # Если моно, дублируем
            return audio, audio
        elif audio.shape[1] >= 2:
            return audio[:, 0], audio[:, 1]
        else:
            return audio.flatten(), audio.flatten()
    
    def enhance_telephony_audio(self, audio_data: bytes, format_type: str = "auto", 
                             duplex: bool = False) -> dict:
        """
        Полная обработка телефонного аудио.
        
        Args:
            audio_data: Аудио данные
            format_type: Тип формата
            duplex: Дуплексное аудио (два канала)
            
        Returns:
            dict: Результат обработки
        """
        try:
            # 1. Конвертируем в стандартный формат
            audio, sr = self.convert_telephony_format(audio_data, format_type)
            
            # 2. Применяем телефонные фильтры
            audio = self.apply_telephony_filters(audio, sr)
            
            # 3. Разделяем каналы если нужно
            result = {}
            if duplex and len(audio.shape) > 1:
                caller_audio, callee_audio = self.split_channels(audio)
                result['caller'] = {
                    'audio': caller_audio,
                    'sample_rate': sr,
                    'duration': len(caller_audio) / sr
                }
                result['callee'] = {
                    'audio': callee_audio,
                    'sample_rate': sr,
                    'duration': len(callee_audio) / sr
                }
            else:
                result['mono'] = {
                    'audio': audio,
                    'sample_rate': sr,
                    'duration': len(audio) / sr
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки телефонного аудио: {e}")
            raise
