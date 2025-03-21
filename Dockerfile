FROM nvidia/cuda:12.5.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app

RUN uv venv
ENV UV_PROJECT_ENVIRONMENT=/env
RUN uv sync --frozen --no-cache

# Команда запуска
CMD ["uv", "run", "main.py"]