FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_REQUIRE_HASHES=0 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    JOBS_DIR=/home/user/app/temp/jobs \
    AUDIO_ENHANCER_URL=""

ARG GIGAAM_REV=7447938d791c4f3e643386ee22c33777004293a5

# Создание пользователя для HF Spaces
RUN useradd -m -u 1000 user

WORKDIR $HOME/app

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Обновление pip
RUN pip install --upgrade pip setuptools wheel

# Копирование и установка зависимостей Python
COPY --chown=user:user requirements.txt .
RUN test -n "$GIGAAM_REV" && \
    python -c "from pathlib import Path; p=Path('requirements.txt'); lines=p.read_text().splitlines(); p.with_name('requirements.base.txt').write_text('\n'.join([l for l in lines if l.strip() and not l.strip().startswith('gigaam @')]) + '\n')" && \
    pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.base.txt && \
    pip install --no-cache-dir --no-deps \
    "gigaam @ git+https://github.com/salute-developers/GigaAM.git@${GIGAAM_REV}"

# Копирование исходного кода
COPY --chown=user:user . .

# Создание необходимых директорий
RUN mkdir -p temp logs && \
    mkdir -p temp/jobs && \
    chown -R user:user $HOME/app

# Переключение на пользователя
USER user

# Открытие порта для HF Spaces
EXPOSE 7860

# Настройка health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

# Запуск приложения через main.py для HF Spaces
CMD ["python", "main.py"]
