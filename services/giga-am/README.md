---
title: GigaAM Russian Speech Recognition
emoji: 🎤
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# GigaAM - API для распознавания русской речи

REST API для распознавания русской речи на базе GigaAM-v3-e2e-RNNT.

## Использование

### API Эндпоинты

- `POST /api/transcribe-sync` — Синхронная транскрибация (без диаризации)
- `POST /api/transcribe-async` — Асинхронная транскрибация с callback в Inngest
- `POST /api/transcribe-diarized-async` — Асинхронная транскрибация с сегментами диаризации
- `GET /api/tasks/{task_id}` — Статус и результат задачи
- `GET /api/tasks/{task_id}/result` — Только результат задачи
- `GET /api/status/{task_id}` — Статус задачи (альтернативный эндпоинт)
- `GET /api/tasks/stats` — Статистика по задачам
- `GET /api/health` — Проверка работоспособности
- `GET /api/ready` — Проверка готовности (модель загружена)
- `GET /docs` — Swagger документация

### Пример запроса

```bash
curl -X POST "https://your-space.hf.space/api/transcribe-sync" \
  -F "file=@audio.mp3" \
  -F "filename=audio.mp3"
```

### Ответ

```json
{
  "success": true,
  "segments": [
    {
      "text": "Привет, как дела?",
      "start": 0.5,
      "end": 2.1,
      "start_formatted": "00:00:00.500",
      "end_formatted": "00:00:02.100",
      "duration": 1.6
    }
  ],
  "total_duration": 2.1
}
```

## Поддерживаемые форматы

MP3, WAV, FLAC, M4A, AAC, OGG, WEBM (макс. 100MB)

## Диаризация спикеров (Speaker Diarization)

Диаризация в этом сервисе не выполняется — сегменты с разметкой спикеров
передаются извне в `POST /api/transcribe-diarized-async` (поле `segments`).

### Обработка аудио

Аудио всегда приводится к 16kHz mono при загрузке (librosa), поэтому
отдельной настройки ресемплинга нет — достаточно загрузить файл в
поддерживаемом формате.

См. также `.env.example` — там перечислены все поддерживаемые переменные.

### Проблемы с диаризацией?

Если все сегменты получают `SPEAKER_01`, проверьте:

1. Что входное аудио имеет достаточное качество (16kHz рекомендуется)
2. Что `HF_TOKEN` настроен и приняты условия
   https://huggingface.co/pyannote/segmentation-3.0
3. Что сегменты, переданные в `/api/transcribe-diarized-async`,
   содержат разных `speaker`

### Параметры кластеризации

Параметры `CLUSTERING_*` относятся к внешнему сервису диаризации
(speaker-embeddings), а не к этому API — здесь диаризация передаётся
готовыми сегментами в `POST /api/transcribe-diarized-async`.

## Настройка

Для работы с длинными аудио добавьте `HF_TOKEN` в Repository Settings → Secrets:

1. Получите токен: https://huggingface.co/settings/tokens
2. Примите условия: https://huggingface.co/pyannote/segmentation-3.0
3. Добавьте токен в Secrets как `HF_TOKEN`

### Переменные окружения

- `TRANSCRIPTION_TIMEOUT` - Таймаут распознавания в секундах (по умолчанию 900 = 15 минут)
- `MODEL_LOADING_TIMEOUT` - Таймаут загрузки модели в секундах (по умолчанию 1800 = 30 минут)
- `HF_TOKEN` - Токен для доступа к pyannote/segmentation-3.0
