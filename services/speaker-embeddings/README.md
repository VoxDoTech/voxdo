---
title: Speaker Diarization Service
emoji: "🎙️"
colorFrom: blue
colorTo: indigo
sdk: docker
python_version: "3.11"
app_file: app.py
pinned: false
---

# Speaker Diarization Service

Сервис для диаризации аудио (определения "кто говорил когда") с использованием pyannote.audio 4.x.

## Особенности

- **Community версия**: Работает локально без API ключей и токенов
- **Бесплатно**: Не требует подписки pyannoteAI
- **Модель**: `pyannote/speaker-diarization-community-1`

## Hugging Face Space (Docker)

- Рекомендуемый `SDK`: `Docker`
- Сервис слушает `PORT` из окружения (по умолчанию `7860`)
- **HF_TOKEN не требуется** для community модели

### Быстрый чек-лист деплоя

- Создайте новый Space с `SDK = Docker`.
- Загрузите содержимое папки `services/speaker-embeddings` в корень Space.
- Убедитесь, что Space собрался без ошибок (статус `Running`).
- Проверьте здоровье сервиса:
  - `GET /health` должен вернуть `{"status":"healthy", ...}`.
- Проверьте основной endpoint:
  - `POST /api/diarize` с `multipart/form-data` (`file` + опциональные `num_speakers`, `min_speakers`, `max_speakers`).

## Локальный запуск

### Docker Compose

```bash
# Скопируйте .env.example в .env (HF_TOKEN не требуется для community)
cp .env.example .env

# Запуск
docker-compose up -d

# Проверка
curl http://localhost:7860/health
```

### Прямой запуск

```bash
# Установите зависимости
pip install -r requirements.txt

# Запуск (HF_TOKEN не требуется)
export PORT=7860
python app.py
```

## Endpoints

### `POST /api/diarize`

Диаризация аудио файла - определение "кто говорил когда".

**Параметры:**
- `file`: аудио файл (multipart/form-data, обязательный)
- `num_speakers` (опционально): точное количество спикеров (int)
- `min_speakers` (опционально): минимальное количество спикеров (int)
- `max_speakers` (опционально): максимальное количество спикеров (int)

**Пример ответа:**

```json
{
  "success": true,
  "segments": [
    {"start": 0.0, "end": 3.5, "speaker": "SPEAKER_00"},
    {"start": 3.7, "end": 7.2, "speaker": "SPEAKER_01"}
  ],
  "num_speakers": 2,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "total_speech_duration": 10.7,
  "audio_duration": 12.0,
  "processing_stats": {
    "diarization_time": 2.34,
    "extraction_time": 0.12,
    "total_time": 2.46,
    "real_time_factor": 0.21
  }
}
```

## Логирование времени выполнения

Сервис предоставляет детальное логирование всех этапов обработки:

### Уровни логирования

1. **Загрузка аудио**: время загрузки и предобработки аудио файла
2. **Диаризация**: время выполнения основной модели pyannote
3. **Извлечение сегментов**: время парсинга результатов
4. **Общий запрос**: полное время обработки HTTP запроса

### Пример логов

```
2025-04-08 12:34:56 - speaker-embeddings - INFO - Audio loaded and preprocessed in 0.15s (duration: 30.45s, sample_rate: 16000Hz)
2025-04-08 12:34:56 - speaker-embeddings - INFO - Starting diarization: duration=30.45s, params={'num_speakers': 2}
2025-04-08 12:34:58 - speaker-embeddings - INFO - Diarization processing completed in 2.34s
2025-04-08 12:34:58 - speaker-embeddings - INFO - Segment extraction completed in 0.12s
2025-04-08 12:34:58 - speaker-embeddings - INFO - Diarization completed: 5 segments, 2 speakers, total_speech=28.90s, processing_time=2.34s, extraction_time=0.12s, total_time=2.46s
2025-04-08 12:34:58 - speaker-embeddings - INFO - Total request completed in 2.73s (audio: 30.45s, real_time_factor: 0.09x)
```

### Метрики производительности

- **Real-time factor**: отношение времени обработки к длительности аудио (меньше 1.0 = быстрее реального времени)
- **Processing stats** в ответе API содержит детальную разбивку времени
- При ошибках также логируется время до сбоя

### `GET /health`

Проверка работоспособности сервиса.

**Ответ для community модели:**

```json
{
  "status": "healthy",
  "pyannote_available": true,
  "requires_hf_token": false,
  "model": "pyannote/speaker-diarization-community-1"
}
```

### `GET /api/diagnostics`

Диагностическая информация о конфигурации.

### `GET /`

Информация о сервисе и доступных endpoints.

## Интеграция

В `giga-am` установите URL сервиса диаризации:

```bash
SPEAKER_DIARIZATION_URL=http://speaker-embeddings:7860
# или для Hugging Face Space:
SPEAKER_DIARIZATION_URL=https://<your-space>.hf.space
```

При недоступности сервиса `giga-am` может использовать fallback диаризацию.

## Использование не-community моделей

Если вы хотите использовать другие модели pyannote (например, `pyannote/speaker-diarization-3.1`), установите `HF_TOKEN`:

```bash
export HF_TOKEN=your_token_here
export PYANNOTE_DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
```

## Требования

- Python 3.11+
- pyannote.audio >= 4.0.0 (для поддержки community модели)
- PyTorch (CPU версия достаточна)
- 2GB+ RAM для загрузки модели

## Лицензия

Community модель распространяется под лицензией, разрешающей коммерческое использование без необходимости API ключей.

## Источники и исследования

- [pyannote.audio 4.x](https://github.com/pyannote/pyannote-audio) - Speaker diarization toolkit
- [PyannoteAI Benchmarks](https://arxiv.org/html/2509.26177v1) - SOTA: 11.2% DER
