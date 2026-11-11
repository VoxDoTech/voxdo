"""Сервис диаризации аудио."""
import logging
import os
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Module-level cache for diarization pipelines
_pipeline_cache: dict[tuple[str, str | None], Any] = {}


def _get_diarization_pipeline(diarization_model: str, token: str | None):
    """Get cached diarization pipeline instance."""
    cache_key = (diarization_model, token)

    # Return cached pipeline if available
    if cache_key in _pipeline_cache:
        logger.info(f"Using cached diarization pipeline: {diarization_model}")
        return _pipeline_cache[cache_key]

    try:
        from pyannote.audio import Pipeline

        # Для community модели токен не требуется
        is_community = "community" in diarization_model.lower()

        # Пробуем загрузить pipeline с retry логикой
        init_attempts = []

        if is_community:
            # Community модель работает без токена
            init_attempts = [
                {},  # Без параметров токена
            ]
        elif token:
            # Для не-community моделей с токеном
            init_attempts = [
                {"use_auth_token": token},
                {"token": token},
            ]
        else:
            logger.error(f"Non-community model {diarization_model} requires HF_TOKEN")
            return None

        for kwargs in init_attempts:
            try:
                pipeline = Pipeline.from_pretrained(diarization_model, **kwargs)
                logger.info(f"Successfully loaded diarization pipeline: {diarization_model}")
                # Cache the pipeline
                _pipeline_cache[cache_key] = pipeline
                return pipeline
            except TypeError:
                continue
            except Exception as exc:
                logger.error(f"Failed to load diarization pipeline with kwargs {kwargs}: {exc}")
                continue

        return None

    except Exception as exc:
        logger.error(f"Error initializing diarization pipeline: {exc}")
        return None


def process_diarization(
    audio: np.ndarray,
    sr: int,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> dict[str, Any]:
    """Выполнение диаризации с использованием pyannote."""

    try:
        import torch

        # Используем последнюю community модель (работает без токена)
        diarization_model = os.getenv(
            "PYANNOTE_DIARIZATION_MODEL",
            "pyannote/speaker-diarization-community-1"
        )

        # Проверяем токен только для не-community моделей
        is_community = "community" in diarization_model.lower()
        token = os.getenv("HF_TOKEN", "").strip() or None

        if not is_community and not token:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="HF_TOKEN not configured. Set HF_TOKEN environment variable for non-community models."
            )

        # Получаем кешированный pipeline
        pipeline = _get_diarization_pipeline(diarization_model, token)

        if pipeline is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Failed to load pyannote diarization pipeline"
            )

        # Подготовка аудио для pyannote
        waveform = torch.from_numpy(audio).float()
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        audio_dict = {
            "waveform": waveform,
            "sample_rate": sr,
        }

        # Параметры диаризации
        diarization_params = {}
        if num_speakers is not None:
            diarization_params["num_speakers"] = num_speakers
        if min_speakers is not None:
            diarization_params["min_speakers"] = min_speakers
        if max_speakers is not None:
            diarization_params["max_speakers"] = max_speakers

        logger.info(
            f"Starting diarization: duration={len(audio)/sr:.2f}s, params={diarization_params}"
        )

        # Замер времени выполнения диаризации
        diarization_start_time = time.time()

        # Выполнение диаризации
        diarization = pipeline(audio_dict, **diarization_params)

        diarization_end_time = time.time()
        diarization_duration = diarization_end_time - diarization_start_time

        logger.info(
            f"Diarization processing completed in {diarization_duration:.2f}s"
        )

        # Конвертация результатов (новый API pyannote 4.x)
        segments = []

        logger.info(f"Diarization output type: {type(diarization)}")

        # Замер времени извлечения сегментов
        extraction_start_time = time.time()

        # DiarizeOutput в pyannote 4.x имеет атрибут speaker_diarization (Annotation объект)
        try:
            # Извлекаем Annotation из DiarizeOutput
            annotation = None

            if hasattr(diarization, 'speaker_diarization'):
                # Новый API (pyannote 4.x) - используем speaker_diarization
                annotation = diarization.speaker_diarization
                logger.info(f"Using speaker_diarization, type: {type(annotation)}")
            elif hasattr(diarization, 'itertracks'):
                # Старый API (pyannote < 4.0) - diarization это уже Annotation
                annotation = diarization
                logger.info("Using diarization directly as Annotation")
            else:
                raise ValueError(f"Cannot extract annotation from {type(diarization)}")

            # Теперь итерируем по Annotation
            if hasattr(annotation, 'itertracks'):
                for segment, _, label in annotation.itertracks(yield_label=True):
                    segments.append({
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "speaker": label,
                    })
            else:
                raise ValueError(f"Annotation has no itertracks method: {type(annotation)}")

        except Exception as e:
            logger.error(f"Failed to extract segments: {e}", exc_info=True)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="Failed to extract diarization segments"
            ) from e

        # Завершение замера времени извлечения сегментов
        extraction_end_time = time.time()
        extraction_duration = extraction_end_time - extraction_start_time

        if not segments:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="Diarization returned no segments"
            )

        # Сортировка по времени
        segments.sort(key=lambda s: s["start"])

        # Статистика
        unique_speakers = set(s["speaker"] for s in segments)
        total_duration = sum(s["end"] - s["start"] for s in segments)

        logger.info(
            f"Segment extraction completed in {extraction_duration:.2f}s"
        )

        logger.info(
            f"Diarization completed: {len(segments)} segments, "
            f"{len(unique_speakers)} speakers, "
            f"total_speech={total_duration:.2f}s, "
            f"processing_time={diarization_duration:.2f}s, "
            f"extraction_time={extraction_duration:.2f}s, "
            f"total_time={diarization_duration + extraction_duration:.2f}s"
        )

        # Общее время выполнения диаризации
        total_processing_time = diarization_duration + extraction_duration

        return {
            "success": True,
            "segments": segments,
            "num_speakers": len(unique_speakers),
            "speakers": sorted(unique_speakers),
            "total_speech_duration": total_duration,
            "audio_duration": len(audio) / sr,
            "processing_stats": {
                "diarization_time": round(diarization_duration, 2),
                "extraction_time": round(extraction_duration, 2),
                "total_time": round(total_processing_time, 2),
                "real_time_factor": round(total_processing_time / (len(audio) / sr), 2)
            }
        }

    except Exception as exc:
        from fastapi import HTTPException
        # Перебрасываем HTTPException как есть, чтобы сохранить оригинальный статус и сообщение
        if isinstance(exc, HTTPException):
            raise
        logger.error(f"Diarization error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Diarization failed"
        ) from exc
