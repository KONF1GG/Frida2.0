FROM nvidia/cuda:12.5.0-runtime-Ubuntu22.04

RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-distutils \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app

RUN uv venv
ENV UV_PROJECT_ENVIRONMENT=/env
RUN uv sync --frozen --no-cache

CMD ["uv", "run", "main.py"]