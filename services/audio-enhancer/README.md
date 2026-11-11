---
title: Audio Enhancer v2.0
emoji: 🎵
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
sleep_time: 900
pinned: false
suggested_hardware: t4-small
suggested_storage: small
startup_duration_timeout: 1h
---

# 🎵 Audio Enhancer v2.0

Продвинутый микросервис для улучшения качества аудио перед распознаванием речи (ASR/STT).

**🆕 НОВОЕ**: Поддержка телефонных звонков с кодеками G.711, G.729, Opus и дуплексной обработкой.

![Build](https://img.shields.io/github/actions/workflow/status/TechCraftEngineer/calls/jobs.yml?branch=main)
![Coverage](https://img.shields.io/badge/coverage-NA-lightgrey)
![PyPI/version](https://img.shields.io/badge/PyPI%2Fversion-NA-lightgrey)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)

## Участие в разработке

1. Сделайте `fork` репозитория.
2. Создайте ветку: `feature/<name>` или `fix/<name>`.
3. Внесите изменения и сделайте коммит.
4. Запушьте ветку в свой fork.
5. Откройте Pull Request в `main`.

Смотрите `../../CONTRIBUTING.md` для деталей по процессу и требованиям к PR.

## 🚀 Современные технологии

### Нейросетевые модели

- **DeepFilterNet** - State-of-the-art нейросетевое шумоподавление
  - Превосходит классические методы на 30-40%
  - Работает с частотой 48kHz
  - Удаляет шум без искажения речи
  - Автоматический fallback на классическое шумоподавление при недоступности

- **Silero VAD** - Нейросетевая детекция речи
  - Точное определение речевых сегментов
  - Удаление длинных пауз
  - Минимальная длительность речи: 250ms
  - Минимальная длительность паузы: 1000ms

### Профессиональная обработка

- **Pedalboard** (Spotify) - Студийное качество обработки
  - High-pass фильтр (80 Hz) - удаление низких частот
  - Low-pass фильтр (8000 Hz) - удаление высоких частот
  - Динамическая компрессия (threshold: -20dB, ratio: 4:1)
  - Профессиональные эффекты

- **LUFS нормализация** - Перцептивная громкость
  - Стандарт вещания (EBU R128)
  - Целевая громкость: -16 LUFS (оптимально для речи)
  - Лучше чем RMS/Peak нормализация
  - Автоматический fallback на RMS при ошибке

### Дополнительные улучшения

- **Спектральный гейтинг** - Адаптивная очистка от шума
  - Мягкий гейтинг с квадратичной маской
  - Порог шума: нижние 10% энергии
- **Pre-emphasis** - Усиление высоких частот речи (коэффициент 0.97)
- **Частотное усиление** - Оптимизация речевого диапазона
  - Речевой диапазон: 300-3400 Hz (усиление 1.3x)
  - Критичный диапазон: 1000-3000 Hz (усиление 1.5x)
  - Подавление нерелевантных частот (0.4x)
- **Kaiser-best ресемплинг** - Высококачественное изменение частоты

## 📦 Установка

```bash
cd services/audio-enhancer
pip install -r requirements.txt
```

## 🎯 Использование

### Запуск через Docker

```bash
cd services/audio-enhancer
docker-compose up --build
```

API доступен на <http://localhost:7860>

Документация: <http://localhost:7860/docs>

### API endpoints

#### Телефония 🆕

##### POST /telephony/enhance
Улучшение телефонного аудио с поддержкой кодеков.

```bash
curl -X POST "http://localhost:7860/telephony/enhance" \
  -F "file=@call.g711" \
  -F "format_type=g711" \
  -F "duplex=true" \
  -F "apply_telephony_filters=true"
```

##### POST /telephony/convert
Конвертация телефонного формата в WAV.

```bash
curl -X POST "http://localhost:7860/telephony/convert" \
  -F "file=@call.opus" \
  -F "from_format=opus" \
  -F "to_format=wav"
```

##### POST /telephony/split
Разделение дуплексного аудио на caller/callee.

```bash
curl -X POST "http://localhost:7860/telephony/split" \
  -F "file=@stereo_call.wav"
```

#### Стандартные endpoints

#### GET /health

Проверка здоровья сервиса:

```bash
curl http://localhost:7860/health
```

Ответ:

```json
{
  "status": "healthy",
  "silero_vad_loaded": true,
  "deepfilter_loaded": true,
  "version": "2.0.0"
}
```

#### POST /enhance

Полная обработка аудио:

```bash
curl -X POST "http://localhost:7860/enhance" \
  -F "file=@audio.mp3" \
  -F "use_deepfilter=true" \
  -F "spectral_gating=true" \
  -F "enhance_speech=true" \
  -F "use_compressor=true" \
  -F "normalize_volume=true" \
  -F "remove_silence=false" \
  -F "target_sample_rate=16000" \
  -o enhanced.wav
```

#### POST /denoise

Только классическое шумоподавление (быстрый endpoint):

```bash
curl -X POST "http://localhost:7860/denoise" \
  -F "file=@audio.mp3" \
  -F "stationary=true" \
  -F "prop_decrease=0.8" \
  -o denoised.wav
```

Параметры:

- `stationary` (bool, default: true) - Стационарный шум (true) или нестационарный (false)
- `prop_decrease` (float, 0-1, default: 0.8) - Агрессивность шумоподавления

## ⚙️ Параметры обработки

| Параметр             | Тип  | По умолчанию | Описание                                 |
| -------------------- | ---- | ------------ | ---------------------------------------- |
| `use_deepfilter`     | bool | true         | DeepFilterNet (AI шумоподавление, 48kHz) |
| `spectral_gating`    | bool | true         | Спектральный гейтинг (мягкая маска)      |
| `noise_reduction`    | bool | true         | Классическое шумоподавление (fallback)   |
| `enhance_speech`     | bool | true         | Усиление речевых частот (300-3400 Hz)    |
| `use_compressor`     | bool | true         | Динамическая компрессия (-20dB, 4:1)     |
| `normalize_volume`   | bool | true         | LUFS нормализация (-16 LUFS)             |
| `remove_silence`     | bool | false        | Удаление пауз (Silero VAD)               |
| `target_sample_rate` | int  | 16000        | Частота дискретизации (800-192000 Hz)    |

## 🎛️ Рекомендуемые настройки

### Для Whisper / ASR

```python
{
    "use_deepfilter": True,
    "spectral_gating": True,
    "enhance_speech": True,
    "use_compressor": True,
    "normalize_volume": True,
    "remove_silence": False,
    "target_sample_rate": 16000
}
```

### Для телефонных записей

```python
{
    "use_deepfilter": True,
    "spectral_gating": True,
    "enhance_speech": True,
    "use_compressor": True,
    "normalize_volume": True,
    "remove_silence": True,
    "target_sample_rate": 8000
}
```

### Для чистых студийных записей

```python
{
    "use_deepfilter": False,
    "spectral_gating": False,
    "enhance_speech": True,
    "use_compressor": False,
    "normalize_volume": True,
    "remove_silence": False,
    "target_sample_rate": 16000
}
```

## 📊 Поддерживаемые форматы

**Входные**: MP3, WAV, FLAC, M4A, AAC, OGG, WEBM, и другие (через librosa)

**Выходной**: WAV 16-bit PCM

## 🔧 Технические детали

### Pipeline обработки

1. **Загрузка** - Декодирование в mono через librosa, любая частота
2. **DeepFilterNet** - Нейросетевое шумоподавление (48kHz, автоматический ресемплинг)
3. **Классическое шумоподавление** - Fallback если DeepFilterNet недоступен (noisereduce, stationary=True, prop_decrease=0.8)
4. **Спектральный гейтинг** - Дополнительная очистка (порог: 10% перцентиль, квадратичная маска)
5. **Усиление речи**:
   - High-pass фильтр (80 Hz)
   - Low-pass фильтр (8000 Hz)
   - Pre-emphasis (коэффициент 0.97)
   - Частотное усиление (300-3400 Hz: 1.3x, 1000-3000 Hz: 1.5x)
6. **Динамическая компрессия** - Выравнивание динамического диапазона (threshold: -20dB, ratio: 4:1, attack: 5ms, release: 50ms)
7. **LUFS нормализация** - Перцептивная громкость (-16 LUFS, с пиковым ограничением 0.95)
8. **Удаление пауз** - Silero VAD (опционально, min_speech: 250ms, min_silence: 1000ms, threshold: 0.5)
9. **Ресемплинг** - Kaiser-best качество

### Производительность

- Обработка в памяти (без временных файлов)
- Максимальный размер загрузки: 80MB (до декодирования)
- Максимальная длительность: 4 часа (после декодирования)
- Скорость: ~10-20x realtime (зависит от CPU/GPU)
- Защита от OOM: проверка размера до и после декодирования

### Требования

- Python 3.10+
- CPU: 4+ cores рекомендуется
- RAM: 4GB+ рекомендуется
- GPU: опционально (ускоряет DeepFilterNet)
- Зависимости: librosa, noisereduce, pyloudnorm, soundfile, torch, pedalboard, scipy

## 🐳 Docker

```bash
docker build -t audio-enhancer .
docker run -p 7860:7860 audio-enhancer
```

## 📈 Сравнение качества

| Метод           | WER улучшение | Качество   | Скорость |
| --------------- | ------------- | ---------- | -------- |
| Без обработки   | 0%            | -          | -        |
| Классическое    | 10-15%        | ⭐⭐⭐     | ⚡⚡⚡   |
| DeepFilterNet   | 30-40%        | ⭐⭐⭐⭐⭐ | ⚡⚡     |
| Полный pipeline | 40-50%        | ⭐⭐⭐⭐⭐ | ⚡       |

## 🔬 Примеры использования

### Python

```python
import requests

with open("audio.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:7860/enhance",
        files={"file": f},
        data={
            "use_deepfilter": True,
            "target_sample_rate": 16000,
        }
    )

with open("enhanced.wav", "wb") as f:
    f.write(response.content)
```

### JavaScript

```javascript
const formData = new FormData();
formData.append("file", audioFile);
formData.append("use_deepfilter", "true");
formData.append("target_sample_rate", "16000");

const response = await fetch("http://localhost:7860/enhance", {
  method: "POST",
  body: formData,
});

const blob = await response.blob();
```

## 📝 Лицензия

MIT

## 🤝 Вклад

Приветствуются pull requests с улучшениями!
