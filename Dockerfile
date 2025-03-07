FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install uv

RUN uv venv

RUN source .venv/bin/activate

RUN uv sync

CMD ["uv", "run", "main.py"]
