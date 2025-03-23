# # Базовый образ с CUDA 12.8
# FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# # Установка временной зоны и настройка неинтерактивного режима
# ENV DEBIAN_FRONTEND=noninteractive
# RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
#     apt-get update && apt-get install -y tzdata && \
#     dpkg-reconfigure --frontend noninteractive tzdata

# # Установка зависимостей и добавление PPA для Python 3.12
# RUN apt-get update && apt-get install -y software-properties-common && \
#     add-apt-repository ppa:deadsnakes/ppa && \
#     apt-get update && apt-get install -y \
#     python3.12 \
#     python3.12-dev \
#     python3-pip \
#     python3-distutils \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

# # Установка pip и UV
# RUN pip3 install --upgrade pip
# # COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# # Установка Python 3.12 как дефолтного
# RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# # Копирование приложения
# ADD . /app
# WORKDIR /app

# # RUN pip install -r requirements.txt
# RUN pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# # Настройка виртуального окружения с UV
# # RUN uv venv
# # ENV UV_PROJECT_ENVIRONMENT=/env

# # Установка PyTorch 2.4.1 с CUDA 12.4 для Python 3.12
# # RUN uv pip install torch==2.4.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# # Синхронизация остальных зависимостей из pyproject.toml
# # RUN uv sync --frozen --no-cache

# # Команда запуска
# CMD ["python3", "main.py"]

# Используем официальный образ NVIDIA PyTorch с предустановленным PyTorch и CUDA
# Берем более новый образ PyTorch с CUDA 12.3
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

# Настраиваем неинтерактивный режим для apt
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем временную зону
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    apt-get update && apt-get install -y tzdata && \
    dpkg-reconfigure --frontend noninteractive tzdata

# Устанавливаем зависимости (если нужно)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Копируем приложение и задаем рабочую директорию
ADD . /app
WORKDIR /app

# Устанавливаем зависимости из requirements.txt
RUN pip install -r requirements.txt

# Понижаем версию NumPy, чтобы зависимости работали
RUN pip install "numpy<2.0"

# Запускаем приложение
CMD ["python3", "main.py"]