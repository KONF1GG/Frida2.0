FROM nvidia/cuda:12.5.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    apt-get update && apt-get install -y tzdata && \
    dpkg-reconfigure --frontend noninteractive tzdata

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app

RUN uv venv --python 3.12

ENV UV_PROJECT_ENVIRONMENT=/env

RUN uv pip install torch==2.4.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

RUN uv sync --frozen --no-cache

CMD ["uv", "run", "main.py"]