# Базовый образ с CUDA 12.5
FROM nvidia/cuda:12.5.0-runtime-ubuntu22.04

# Установка зависимостей и добавление PPA для Python 3.12
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-distutils \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Установка pip и UV
RUN pip3 install --upgrade pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Копирование приложения
ADD . /app
WORKDIR /app

# Настройка виртуального окружения с UV
RUN uv venv
ENV UV_PROJECT_ENVIRONMENT=/env
RUN uv sync --frozen --no-cache

# Команда запуска
CMD ["uv", "run", "main.py"]