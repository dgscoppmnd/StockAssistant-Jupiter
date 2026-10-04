FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/api.txt /tmp/requirements-api.txt
RUN pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/requirements-api.txt

COPY requirements/knowledge.txt /tmp/requirements-knowledge.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /tmp/requirements-knowledge.txt

COPY src /app/src
COPY docker/init-scripts/init.sql /app/docker/init-scripts/init.sql
COPY data/knowledge /app/data/knowledge
RUN mkdir -p /app/data/knowledge
VOLUME ["/app/data/knowledge"]

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
