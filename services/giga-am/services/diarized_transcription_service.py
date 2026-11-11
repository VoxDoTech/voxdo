"""
Сервис для параллельной транскрипции диаризированных сегментов.

Решает проблему N+1 HTTP-запросов при транскрипции диаризированного аудио.
Вместо отдельных запросов для каждого сегмента, принимает полный файл + сегменты,
нарезает и транскрибирует параллельно с ограничением concurrency.
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import uuid

import librosa
import soundfile
import numpy as np

from config import settings
from services.transcription_service import transcription_service

logger = logging.getLogger(__name__)


@dataclass
class DiarizationSegment:
    """Сегмент диаризации"""
    start: float  # секунды
    end: float    # секунды
    speaker: str


@dataclass
class TranscribedSegment:
    """Результат транскрипции сегмента"""
    speaker: str
    start: float
    end: float
    text: str
    confidence: float


class DiarizedTranscriptionService:
    """
    Сервис для транскрипции диаризированного аудио.
    
    Особенности:
    - Принимает полный аудио файл + сегменты диаризации
    - Нарезает аудио на сегменты локально
    - Транскрибирует сегменты параллельно с семафором
    - Возвращает результаты с сохранением временных меток
    """
    
    def __init__(self, max_concurrent_segments: int = 4):
        """
        Args:
            max_concurrent_segments: Максимальное количество параллельных транскрипций
        """
        self.max_concurrent = max_concurrent_segments
        self._semaphore: asyncio.Semaphore | None = None  # Ленивая инициализация
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_segments)
        logger.info(f"DiarizedTranscriptionService инициализирован (max_concurrent={max_concurrent_segments})")
    
    async def _get_semaphore(self) -> asyncio.Semaphore:
        """Лениво инициализирует и возвращает семафор."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
    async def transcribe_diarized_audio(
        self,
        audio_data: bytes,
        filename: str,
        segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Транскрибирует диаризированное аудио.
        
        Args:
            audio_data: Полный аудио файл
            filename: Имя файла
            segments: Список сегментов диаризации [{start, end, speaker}, ...]
            
        Returns:
            Результат транскрипции с сегментами
        """
        request_id = f"diarized-{uuid.uuid4()}"
        start_time = asyncio.get_running_loop().time()
        
        logger.info(
            f"[{request_id}] Начало транскрипции диаризированного аудио: "
            f"{filename}, сегментов: {len(segments)}"
        )
        
        if not segments:
            logger.warning(f"[{request_id}] Нет сегментов для транскрипции")
            return {
                "success": True,
                "final_transcript": "",
                "speakerTimeline": [],
                "segments": [],
                "num_speakers": 0,
                "speakers": [],
                "processing_time": 0,
                "pipeline": "gigaam-diarized",
            }
        
        # Проверяем размер файла
        if len(audio_data) > settings.max_file_size:
            from utils.exceptions import FileSizeError
            raise FileSizeError(
                f"Размер файла ({len(audio_data)} bytes) превышает лимит ({settings.max_file_size} bytes)",
                file_size=len(audio_data),
                max_size=settings.max_file_size
            )
        
        temp_dir = None
        try:
            # Создаем временную директорию для сегментов
            temp_dir = tempfile.mkdtemp(prefix="diarized_")
            
            # Сохраняем полный аудио файл
            file_extension = os.path.splitext(filename)[1] or ".wav"
            full_audio_path = os.path.join(temp_dir, f"full{file_extension}")
            
            with open(full_audio_path, 'wb') as f:
                f.write(audio_data)
            
            # Загружаем полное аудио для нарезки
            audio_array, sample_rate = await asyncio.to_thread(
                librosa.load, full_audio_path, sr=16000, mono=True
            )
            
            logger.info(
                f"[{request_id}] Аудио загружено: {len(audio_array)} samples, "
                f"{len(audio_array)/sample_rate:.2f}s, SR={sample_rate}"
            )
            
            # Создаем сегменты для обработки
            diarization_segments = [
                DiarizationSegment(
                    start=seg.get("start", 0),
                    end=seg.get("end", 0),
                    speaker=seg.get("speaker") or "unknown"
                )
                for seg in segments
            ]
            
            # Нарезаем аудио на сегменты (параллельно)
            segment_files = await self._extract_segments_parallel(
                audio_array, sample_rate, diarization_segments, temp_dir, request_id
            )
            
            # Транскрибируем сегменты параллельно с семафором
            transcribed_segments = await self._transcribe_segments_parallel(
                segment_files, diarization_segments, request_id
            )
            
            # Собираем полный текст
            full_transcript = " ".join(
                seg.text for seg in transcribed_segments if seg.text
            ).strip()
            
            # Логируем статистику по текстам сегментов
            empty_segments = sum(1 for seg in transcribed_segments if not seg.text)
            non_empty_segments = len(transcribed_segments) - empty_segments
            total_text_length = sum(len(seg.text) for seg in transcribed_segments)
            
            logger.info(
                f"[{request_id}] Формирование итогового текста: "
                f"всего_сегментов={len(transcribed_segments)}, "
                f"пустых={empty_segments}, "
                f"непустых={non_empty_segments}, "
                f"total_text_length={total_text_length}, "
                f"full_transcript_length={len(full_transcript)}, "
                f"full_transcript_preview='{full_transcript[:100]}...'"
            )
            
            # Получаем уникальных спикеров
            speakers = list(set(seg.speaker for seg in transcribed_segments))
            
            processing_time = asyncio.get_running_loop().time() - start_time
            
            logger.info(
                f"[{request_id}] Транскрипция завершена: {len(transcribed_segments)} сегментов, "
                f"{len(speakers)} спикеров, {processing_time:.2f}s"
            )
            
            # Формируем результат в формате, совместимом с GigaAMResponseSchema
            return {
                "success": True,
                "final_transcript": full_transcript,
                "segments": [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "end": seg.end,
                        "speaker": seg.speaker,
                        "confidence": seg.confidence,
                    }
                    for seg in transcribed_segments
                ],
                "speakerTimeline": [
                    {
                        "speaker": seg.speaker,
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text,
                    }
                    for seg in transcribed_segments
                ],
                "num_speakers": len(speakers),
                "speakers": speakers,
                "processing_time": processing_time,
                "pipeline": "gigaam-diarized",
            }
            
        except Exception as e:
            logger.error(f"[{request_id}] Ошибка транскрипции: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "final_transcript": "",
                "speakerTimeline": [],
                "segments": [],
                "num_speakers": 0,
                "speakers": [],
                "processing_time": 0,
                "pipeline": "gigaam-diarized",
            }
        finally:
            # Очистка временных файлов
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.debug(f"[{request_id}] Временная директория очищена: {temp_dir}")
                except Exception as e:
                    logger.warning(f"[{request_id}] Ошибка очистки temp dir: {e}")
    
    async def _extract_segments_parallel(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        segments: List[DiarizationSegment],
        temp_dir: str,
        request_id: str
    ) -> List[Optional[str]]:
        """
        Нарезает аудио на сегменты параллельно.
        
        Returns:
            Список путей к файлам сегментов
        """
        async def extract_one(idx: int, segment: DiarizationSegment) -> Optional[str]:
            # Проверяем минимальную длительность сегмента
            segment_duration = segment.end - segment.start
            MIN_SEGMENT_DURATION = 0.3  # минимум 300ms для распознавания
            
            if segment_duration < MIN_SEGMENT_DURATION:
                logger.debug(
                    f"[{request_id}] Сегмент {idx} слишком короткий: {segment_duration:.3f}s, пропускаем"
                )
                return None
            
            start_sample = int(segment.start * sample_rate)
            end_sample = int(segment.end * sample_rate)
            
            # Ограничиваем границы
            start_sample = max(0, min(start_sample, len(audio_array)))
            end_sample = max(start_sample, min(end_sample, len(audio_array)))
            
            segment_audio = audio_array[start_sample:end_sample]
            
            # Дополнительная проверка - аудио не пустое
            if len(segment_audio) == 0:
                logger.warning(f"[{request_id}] Сегмент {idx}: пустое аудио после нарезки")
                return None
            
            output_path = os.path.join(temp_dir, f"segment_{idx:04d}.wav")
            
            await asyncio.to_thread(
                soundfile.write,
                output_path,
                segment_audio,
                sample_rate,
                subtype='PCM_16'
            )
            
            # Файл сегмента сохранен
            
            return output_path
        
        # Параллельная нарезка (I/O bound, можно все сразу)
        tasks = [extract_one(i, seg) for i, seg in enumerate(segments)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Сохраняем позиционное соответствие: храним (index, result) пары
        indexed_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[{request_id}] Ошибка нарезки сегмента {i}: {r}")
            else:
                indexed_results.append((i, r))

        segment_files = [None] * len(segments)  # Placeholder для всех сегментов
        for idx, file_path in indexed_results:
            segment_files[idx] = file_path

        logger.debug(f"[{request_id}] Нарезано {len(indexed_results)} сегментов из {len(segments)}")
        return segment_files
    
    async def _transcribe_segments_parallel(
        self,
        segment_files: List[Optional[str]],
        segments: List[DiarizationSegment],
        request_id: str
    ) -> List[TranscribedSegment]:
        """
        Транскрибирует сегменты параллельно с семафором.
        
        Использует семафор для ограничения количества одновременных
        обращений к модели GigaAM (thread-safe через RLock).
        
        Returns:
            Список транскрибированных сегментов
        """
        async def transcribe_one(
            idx: int,
            file_path: str,
            segment: DiarizationSegment
        ) -> TranscribedSegment:
            semaphore = await self._get_semaphore()
            async with semaphore:
                try:
                    # Вызываем синхронный метод в отдельном потоке
                    result = await asyncio.to_thread(
                        transcription_service.transcribe_audio,
                        file_path
                    )

                    if result.get("success"):
                        segments_data = result.get("segments", [])
                        if segments_data:
                            # Объединяем все сегменты в один текст
                            texts = []
                            confidences = []
                            for seg in segments_data:
                                seg_text = seg.get("text", "").strip()
                                if seg_text:
                                    texts.append(seg_text)
                                confidences.append(seg.get("confidence", 1.0))
                            text = " ".join(texts).strip()
                            # Вычисляем среднюю уверенность
                            confidence = sum(confidences) / len(confidences) if confidences else 1.0
                        else:
                            text = ""
                            confidence = 0.0
                    else:
                        text = ""
                        confidence = 0.0
                        logger.warning(
                            f"[{request_id}] Ошибка транскрипции сегмента {idx}: "
                            f"{result.get('error')}"
                        )
                    
                    return TranscribedSegment(
                        speaker=segment.speaker,
                        start=segment.start,
                        end=segment.end,
                        text=text,
                        confidence=confidence
                    )
                    
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Исключение при транскрипции сегмента {idx}: {e}"
                    )
                    return TranscribedSegment(
                        speaker=segment.speaker,
                        start=segment.start,
                        end=segment.end,
                        text="",
                        confidence=0.0
                    )
        
        # Запускаем все задачи параллельно (семафор ограничит выполнение)
        # Используем enumerate для сохранения исходных индексов
        tasks = [
            transcribe_one(i, file_path, segments[i])
            for i, file_path in enumerate(segment_files)
            if file_path is not None  # Пропускаем failed сегменты
        ]

        results = await asyncio.gather(*tasks)

        # Создаем полный список результатов с None для failed сегментов
        full_results: List[Optional[TranscribedSegment]] = [None] * len(segment_files)
        result_idx = 0
        for i, file_path in enumerate(segment_files):
            if file_path is not None and result_idx < len(results):
                full_results[i] = results[result_idx]
                result_idx += 1

        # Фильтруем None значения
        return [r for r in full_results if r is not None]


# Глобальный экземпляр сервиса
diarized_transcription_service = DiarizedTranscriptionService(
    max_concurrent_segments=settings.model_workers * 2  # 2x workers для лучшей загрузки
)
