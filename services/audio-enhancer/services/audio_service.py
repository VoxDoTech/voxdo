"""Основные процессоры обработки аудио."""

import logging
import time
from typing import Dict, Any, Optional

import librosa
import numpy as np
import noisereduce as nr
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter
from scipy import signal as scipy_signal

from config.settings import config
from services.model_service import model_manager
from utils.error_handlers import AudioProcessingError
from utils.logging_utils import processing_logger, log_context
from utils.audio_utils import save_audio_to_bytes, audio_to_base64

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Основной класс для обработки аудио."""
    
    def __init__(self):
        self.loudness_meter = pyln.Meter(16000)
    
    def enhance_audio(self, audio_bytes: bytes, **kwargs) -> Dict[str, Any]:
        """
        Основной метод улучшения аудио.
        
        Args:
            audio_bytes: Байты аудио файла
            **kwargs: Параметры обработки
            
        Returns:
            Словарь с результатами обработки
        """
        with log_context("enhance_audio", **kwargs) as log:
            # Загрузка аудио
            from utils.audio_utils import load_audio_with_duration_check
            audio, sr = load_audio_with_duration_check(audio_bytes)
            
            original_audio = audio.copy()
            original_sr = sr
            
            file_size = len(audio_bytes)
            duration = len(audio) / sr
            
            log.log_audio_processing(
                "enhance_start",
                file_size,
                duration,
                sr,
                0,
                sample_rate=sr
            )
            
            start_time = processing_logger.logger.info("Starting audio enhancement...")
            
            try:
                # Обработка аудио
                processed_audio = self._process_audio_pipeline(
                    audio, sr, original_audio, original_sr, **kwargs
                )
                
                # Сохранение результата
                output_bytes = save_audio_to_bytes(processed_audio, kwargs.get("target_sample_rate", 16000))
                
                # Диаризация если требуется
                diarization_result = None
                if kwargs.get("enable_diarization", False):
                    try:
                        diarization_result = model_manager.run_diarization(original_audio, original_sr)
                    except Exception as e:
                        logger.warning(f"Диаризация не удалась: {e}")
                
                # Формирование ответа
                response = {
                    "audio_base64": audio_to_base64(output_bytes),
                    "sample_rate": kwargs.get("target_sample_rate", 16000),
                    "duration": len(processed_audio) / kwargs.get("target_sample_rate", 16000),
                    "file_size_bytes": len(output_bytes),
                    "original_duration": duration,
                    "original_sample_rate": sr,
                }
                
                if diarization_result:
                    response["diarization"] = diarization_result
                
                # Логирование завершения
                processing_time_ms = (time.time() - start_time) * 1000
                log.log_audio_processing(
                    "enhance_complete",
                    file_size,
                    duration,
                    kwargs.get("target_sample_rate", 16000),
                    processing_time_ms
                )
                
                return response
                
            except Exception as e:
                logger.error("Audio enhancement failed: %s", e)
                raise AudioProcessingError(f"Enhancement failed: {str(e)}")
    
    def _process_audio_pipeline(self, audio: np.ndarray, sr: int, 
                              original_audio: np.ndarray, original_sr: int,
                              **kwargs) -> np.ndarray:
        """
        Выполняет полный pipeline обработки аудио с улучшенными параметрами.
        
        Args:
            audio: Аудио данные
            sr: Частота дискретизации
            original_audio: Оригинальное аудио
            original_sr: Оригинальная частота
            **kwargs: Параметры обработки
            
        Returns:
            Обработанное аудио
        """
        # Логируем режим агрессивности
        aggressiveness = kwargs.get("aggressiveness", "custom")
        logger.info(f"Режим обработки: {aggressiveness}")
        
        # DeepFilterNet шумоподавление (всегда включен для light/medium)
        if kwargs.get("use_deepfilter", True) and model_manager.deepfilter_available:
            logger.info("Применяем DeepFilterNet шумоподавление...")
            try:
                audio = model_manager.apply_deepfilter(audio, sr)
                logger.info("✓ DeepFilterNet применен")
            except Exception as e:
                logger.warning(f"DeepFilterNet не удался: {e}, используем fallback")
                kwargs["use_deepfilter"] = False
        
        # WPE дереверберация (только в heavy режиме)
        if kwargs.get("use_wpe", False) and model_manager.wpe_available:
            logger.info("Применяем WPE дереверберацию...")
            try:
                audio = model_manager.apply_wpe(audio)
                logger.info("✓ WPE дереверберация применена")
            except Exception as e:
                logger.warning(f"WPE не удался: {e}")
        
        # Классическое шумоподавление (только если DeepFilter отключен)
        if (kwargs.get("noise_reduction", False) and 
            (not kwargs.get("use_deepfilter", True) or not model_manager.deepfilter_available)):
            logger.info("Применяем классическое шумоподавление...")
            audio = nr.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.8)
        
        # Спектральный гейтинг (улучшенный)
        if kwargs.get("spectral_gating", False):
            logger.info("Применяем улучшенный спектральный гейтинг...")
            try:
                audio = self._apply_spectral_gating(audio)
            except Exception as e:
                logger.warning(f"Спектральный гейтинг не удался: {e}, пропускаем")
        
        # Усиление речи (более консервативное)
        if kwargs.get("enhance_speech", False):  # Изменено на False по умолчанию
            logger.info("Усиливаем речевые частоты...")
            try:
                audio = self._enhance_speech(audio, sr)
            except Exception as e:
                logger.warning(f"Усиление речи не удалось: {e}, пропускаем")
        
        # Динамическая компрессия (более мягкая)
        if kwargs.get("use_compressor", False):
            logger.info("Применяем мягкую динамическую компрессию...")
            try:
                audio = self._apply_compression(audio, sr)
            except Exception as e:
                logger.warning(f"Компрессия не удалась: {e}, пропускаем")
        
        # Нормализация громкости (LUFS)
        if kwargs.get("normalize_volume", True):
            logger.info("Нормализуем громкость (LUFS)...")
            try:
                audio = self._normalize_volume(audio, sr)
            except Exception as e:
                logger.warning(f"Нормализация громкости не удалась: {e}, пропускаем")
        
        # Удаление пауз (по запросу)
        if kwargs.get("remove_silence", False) and model_manager.vad_available:
            logger.info("Удаляем длинные паузы...")
            audio = self._remove_silence(audio, sr)
        
        # Ресемплинг
        target_sr = kwargs.get("target_sample_rate", 16000)
        if sr != target_sr:
            logger.info(f"Ресемплинг {sr} Hz -> {target_sr} Hz...")
            audio = librosa.resample(
                audio, orig_sr=sr, target_sr=target_sr, res_type="kaiser_best"
            )
        
        return audio
    
    def _apply_spectral_gating(self, audio: np.ndarray) -> np.ndarray:
        """Применяет улучшенный спектральный гейтинг."""
        D = librosa.stft(audio)
        magnitude = np.abs(D)
        
        # Используем улучшенные параметры из конфига
        settings = config.SPECTRAL_GATING_SETTINGS
        noise_threshold = np.percentile(magnitude, settings["noise_percentile"])
        
        # Создаем маску с минимальным значением
        mask = np.maximum(
            settings["min_mask_value"], 
            1 - (noise_threshold / (magnitude + 1e-10))
        )
        
        # Применяем степень маски (менее агрессивная)
        mask = np.power(mask, settings["mask_power"])
        D_filtered = D * mask
        
        return librosa.istft(D_filtered, length=len(audio))
    
    def _enhance_speech(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Усиливает речевые частоты."""
        # Фильтры
        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=config.SPEECH_FILTER_SETTINGS["highpass_cutoff"]),
            LowpassFilter(cutoff_frequency_hz=config.SPEECH_FILTER_SETTINGS["lowpass_cutoff"]),
        ])
        audio = board(audio, sr)
        
        # Pre-emphasis
        audio = librosa.effects.preemphasis(audio, coef=config.SPEECH_FILTER_SETTINGS["preemphasis_coef"])
        
        # Частотное усиление
        fft = np.fft.rfft(audio)
        frequencies = np.fft.rfftfreq(len(audio), 1 / sr)
        
        speech_range = config.SPEECH_FILTER_SETTINGS["speech_range"]
        critical_range = config.SPEECH_FILTER_SETTINGS["critical_range"]
        
        speech_mask = (frequencies >= speech_range[0]) & (frequencies <= speech_range[1])
        critical_mask = (frequencies >= critical_range[0]) & (frequencies <= critical_range[1])
        
        gain = np.ones_like(frequencies, dtype=np.float32)
        gain[critical_mask] = config.SPEECH_FILTER_SETTINGS["critical_gain"]
        gain[speech_mask & ~critical_mask] = config.SPEECH_FILTER_SETTINGS["speech_gain"]
        gain[~speech_mask] = config.SPEECH_FILTER_SETTINGS["non_speech_gain"]
        
        fft *= gain
        return np.fft.irfft(fft, n=len(audio))
    
    def _apply_compression(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Применяет динамическую компрессию."""
        compressor = Pedalboard([
            Compressor(
                threshold_db=config.COMPRESSOR_SETTINGS["threshold_db"],
                ratio=config.COMPRESSOR_SETTINGS["ratio"],
                attack_ms=config.COMPRESSOR_SETTINGS["attack_ms"],
                release_ms=config.COMPRESSOR_SETTINGS["release_ms"]
            )
        ])
        return compressor(audio, sr)
    
    def _normalize_volume(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Нормализует громкость по LUFS."""
        # Пиковое ограничение
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * config.PEAK_LIMIT
        
        # LUFS нормализация
        try:
            if sr != 16000:
                audio_16k = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                loudness = self.loudness_meter.integrated_loudness(audio_16k)
            else:
                loudness = self.loudness_meter.integrated_loudness(audio)
            
            loudness_delta = config.LUFS_TARGET - loudness
            gain = np.power(10.0, loudness_delta / 20.0)
            audio = audio * gain
            
            logger.info(f"Громкость: {loudness:.1f} LUFS -> {config.LUFS_TARGET} LUFS")
            
        except Exception as e:
            logger.warning(f"LUFS нормализация не удалась: {e}, используем RMS")
            rms = np.sqrt(np.mean(audio**2))
            target_rms = 0.1
            if rms > 0:
                audio = audio * (target_rms / rms)
        
        return np.clip(audio, -1.0, 1.0)
    
    def _remove_silence(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Удаляет длинные паузы с помощью VAD."""
        try:
            speech_timestamps = model_manager.get_vad_timestamps(audio, sr)
            
            if not speech_timestamps:
                return audio
            
            speech_chunks = []
            for timestamp in speech_timestamps:
                start = int(timestamp["start"] * sr / 16000)
                end = int(timestamp["end"] * sr / 16000)
                speech_chunks.append(audio[start:end])
            
            if speech_chunks:
                audio = np.concatenate(speech_chunks)
                logger.info(f"✓ Удалено пауз: {len(speech_timestamps)}")
            
            return audio
            
        except Exception as e:
            logger.warning(f"Удаление пауз не удался: {e}")
            return audio
    
    def denoise_only(self, audio_bytes: bytes, stationary: bool = True, 
                    prop_decrease: float = 0.8) -> bytes:
        """
        Только шумоподавление.
        
        Args:
            audio_bytes: Байты аудио
            stationary: Стационарный шум
            prop_decrease: Агрессивность
            
        Returns:
            Обработанные байты аудио
        """
        from utils.audio_utils import load_audio_with_duration_check
        audio, sr = load_audio_with_duration_check(audio_bytes)
        
        audio_denoised = nr.reduce_noise(
            y=audio, sr=sr, stationary=stationary, prop_decrease=prop_decrease
        )
        
        return save_audio_to_bytes(audio_denoised, sr)
    
    def preprocess_audio(self, audio_bytes: bytes, target_sample_rate: int = 16000,
                        return_audio_base64: bool = True, use_wpe: bool = True, 
                        use_deepfilter: bool = True) -> Dict[str, Any]:
        """
        Предварительная обработка аудио для orchestrator.
        
        Args:
            audio_bytes: Байты входного аудио.
            target_sample_rate: Целевая частота дискретизации выходного аудио.
            return_audio_base64: Если True, включает поле audio_base64 в ответ.
                Если False, возвращаются только метаданные и параметры результата.
            use_wpe: bool, по умолчанию True. Включает WPE-деверберацию
                (удаление реверберации) на этапе preprocess. Может улучшить
                разборчивость речи в эхо/реверберационных записях.
            use_deepfilter: bool, по умолчанию True. Включает DeepFilterNet
                для шумоподавления. Может уменьшить фоновые шумы и повысить
                качество финального сигнала перед ресемплингом.
            
        Returns:
            Словарь с metadata preprocess (sample_rate, duration, preprocess_metadata)
            и опционально audio_base64 (если return_audio_base64=True). target_sample_rate
            влияет на sample_rate/duration результата; флаги use_wpe/use_deepfilter
            меняют обработанный сигнал, но формат ответа остается тем же.
        """
        from utils.audio_utils import load_audio_with_duration_check
        audio, sr = load_audio_with_duration_check(audio_bytes)
        
        # Ресемплинг до 16kHz
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000
        
        # Нормализация
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * 0.95
        
        # LUFS нормализация
        try:
            loudness = self.loudness_meter.integrated_loudness(audio)
            loudness_delta = config.LUFS_TARGET - loudness
            gain = np.power(10.0, loudness_delta / 20.0)
            audio = np.clip(audio * gain, -1.0, 1.0)
        except Exception:
            logger.debug("LUFS нормализация в preprocess не удалась", exc_info=True)
        
        # DeepFilterNet если доступен и включен
        if model_manager.deepfilter_available and use_deepfilter:
            try:
                audio_48k = librosa.resample(audio, orig_sr=16000, target_sr=48000)
                enhanced = model_manager.apply_deepfilter(audio_48k, 48000)
                audio = librosa.resample(enhanced, orig_sr=48000, target_sr=16000)
            except Exception:
                logger.debug("DeepFilter enhancement в preprocess не удался", exc_info=True)
        
        # WPE если доступен и включен
        if model_manager.wpe_available and use_wpe:
            try:
                audio = model_manager.apply_wpe(audio)
            except Exception:
                logger.debug("WPE в preprocess не удался", exc_info=True)
        
        # Фильтры речи
        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=80),
            LowpassFilter(cutoff_frequency_hz=8000)
        ])
        audio = board(audio, 16000)
        
        # Сбор метаданных
        preprocess_metadata = self._collect_preprocess_metadata(audio, 16000)
        
        # Ресемплинг к целевой частоте
        if target_sample_rate != 16000:
            audio = librosa.resample(
                audio, orig_sr=16000, target_sr=target_sample_rate, res_type="kaiser_best"
            )
        
        response = {
            "sample_rate": target_sample_rate,
            "duration": len(audio) / target_sample_rate,
            "preprocess_metadata": preprocess_metadata,
        }
        
        if return_audio_base64:
            output_bytes = save_audio_to_bytes(audio, target_sample_rate)
            response["audio_base64"] = audio_to_base64(output_bytes)
        
        return response
    
    def _collect_preprocess_metadata(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Собирает метаданные для оркестратора."""
        duration = float(len(audio)) / float(sr) if sr else 0.0
        metadata = {
            "sample_rate": sr,
            "duration": duration,
            "speech_spans": [],
            "silence_spans": [],
            "adaptive_segments": [],
            "overlap_candidates": [],
            "speaker_change_candidates": [],
        }
        
        if sr <= 0 or len(audio) == 0:
            return metadata
        
        # VAD анализ
        speech_timestamps = model_manager.get_vad_timestamps(audio, sr)
        
        # Преобразование в speech spans
        speech_spans = []
        for item in speech_timestamps:
            start = float(item["start"]) / 16000.0
            end = float(item["end"]) / 16000.0
            speech_spans.append({"start": round(start, 3), "end": round(end, 3)})
        metadata["speech_spans"] = speech_spans
        
        # Silence spans
        silence_spans = []
        cursor = 0.0
        for span in speech_spans:
            if span["start"] > cursor:
                silence_spans.append({"start": round(cursor, 3), "end": round(span["start"], 3)})
            cursor = max(cursor, span["end"])
        if cursor < duration:
            silence_spans.append({"start": round(cursor, 3), "end": round(duration, 3)})
        metadata["silence_spans"] = silence_spans
        
        # Adaptive segmentation
        adaptive_segments = []
        for span in speech_spans:
            seg_start = span["start"]
            seg_end = span["end"]
            max_chunk = 8.0
            if (seg_end - seg_start) <= max_chunk:
                adaptive_segments.append(span)
                continue
            point = seg_start
            while point < seg_end:
                nxt = min(point + max_chunk, seg_end)
                adaptive_segments.append({"start": round(point, 3), "end": round(nxt, 3)})
                point = nxt
        metadata["adaptive_segments"] = adaptive_segments
        
        # Overlap candidates и speaker changes
        overlap_candidates = []
        speaker_changes = []
        prev = None
        for idx, span in enumerate(speech_spans):
            if prev is not None:
                gap = span["start"] - prev["end"]
                if gap < 0.12:
                    overlap_candidates.append({
                        "start": round(max(prev["end"] - 0.1, 0.0), 3),
                        "end": round(span["start"] + 0.1, 3),
                        "type": "tight_turn_or_overlap",
                    })
                if gap > 0.2:
                    speaker_changes.append({
                        "time": round(span["start"], 3),
                        "reason": "pause_boundary",
                        "index": idx
                    })
            prev = span
        
        metadata["overlap_candidates"] = overlap_candidates
        metadata["speaker_change_candidates"] = speaker_changes
        
        return metadata


# Глобальный экземпляр процессора
audio_processor = AudioProcessor()
