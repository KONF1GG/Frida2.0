# Базовый образ с CUDA 12.5
FROM nvidia/cuda:12.5.0-runtime-ubuntu22.04

# Установка временной зоны и настройка неинтерактивного режима
ENV DEBIAN_FRONTEND=noninteractive
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    apt-get update && apt-get install -y tzdata && \
    dpkg-reconfigure --frontend noninteractive tzdata

# Установка зависимостей и добавление PPA для Python 3.12
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Установка pip и UV
RUN pip3 install --upgrade pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Установка Python 3.12 как дефолтного
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Копирование приложения
ADD . /app
WORKDIR /app

# Настройка виртуального окружения с UV
RUN uv venv
ENV UV_PROJECT_ENVIRONMENT=/env

# Установка PyTorch 2.4.1 с CUDA 12.4 для Python 3.12
RUN uv pip install torch==2.4.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Синхронизация остальных зависимостей из pyproject.toml
RUN uv sync --frozen --no-cache

# Команда запуска
CMD ["uv", "run", "main.py"]