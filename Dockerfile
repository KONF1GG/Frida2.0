FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app

WORKDIR /app

RUN uv venv

ENV UV_PROJECT_ENVIRONMENT=/env

RUN uv sync --frozen --no-cache

CMD ["uv", "run", "main.py"]
