FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TORCHCODEC_DISABLE=1 \
    CUDA_VISIBLE_DEVICES="" \
    HOME=/home/appuser \
    TORCH_HOME=/home/appuser/.cache/torch \
    TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface/transformers \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    libsndfile1 \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apt-get remove -y git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
RUN adduser --disabled-password --gecos "" --home /home/appuser --shell /usr/sbin/nologin appuser \
    && mkdir -p /home/appuser/.cache/torch \
    && mkdir -p /home/appuser/.cache/huggingface/transformers \
    && chown -R appuser:appuser /home/appuser /app

EXPOSE 7860

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3); sys.exit(0)"

CMD ["python", "app.py"]
