FROM pytorch_base

ADD . /app
WORKDIR /app

RUN pip install -r requirements.txt --no-cache-dir

RUN pip install "numpy<2.0"

CMD ["python3", "main.py"]