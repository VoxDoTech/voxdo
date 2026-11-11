# Python микросервис для продвинутой обработки аудио
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/user \
    PATH=/home/user/.local/bin:/root/.cargo/bin:$PATH \
    NUMBA_DISABLE_CACHE=1 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    TORCH_HOME=/tmp/torch_cache \
    TRANSFORMERS_CACHE=/tmp/transformers_cache \
    HF_TOKEN=""

# HF Spaces ожидает пользователя user (uid 1000) и /home/user
RUN mkdir -p /home/user && \
    useradd -u 1000 -d /home/user -s /bin/bash user && \
    chown -R user:user /home/user

WORKDIR /home/user/app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    wget \
    curl \
    git \
    build-essential \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка Rust через rustup (для DeepFilterNet)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    . $HOME/.cargo/env && \
    rustc --version

# Создание директорий для кэша
RUN mkdir -p /tmp/numba_cache /tmp/torch_cache /tmp/transformers_cache && \
    chown -R user:user /tmp/numba_cache /tmp/torch_cache /tmp/transformers_cache

# Копирование и установка зависимостей
COPY --chown=user:user requirements.txt .
RUN . $HOME/.cargo/env && pip install --no-cache-dir -r requirements.txt

# Предзагрузка Silero VAD модели (чтобы не загружать при каждом запуске)
RUN python -c "import torch; torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False, trust_repo=True)" || true

# Копирование приложения
COPY --chown=user:user . .

# Переключение на пользователя
USER user

EXPOSE 7860

# Запуск uvicorn напрямую для лучшей производительности
CMD ["uvicorn", "api.endpoints:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
