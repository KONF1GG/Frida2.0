FROM nvidia/cuda:11.6.1-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    apt-get update && apt-get install -y tzdata && \
    dpkg-reconfigure --frontend noninteractive tzdata

RUN apt-get update

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app

RUN uv venv --python 3.10
ENV UV_PROJECT_ENVIRONMENT=/env

RUN uv pip install torch==1.13.1+cu116 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu116
RUN uv sync --frozen --no-cache

CMD ["uv", "run", "main.py"]