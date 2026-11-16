FROM python:3.11-slim

# make, postgresql-client - быстрое решение для запуска smoke-тестов в контейнере app
RUN apt-get update && apt-get install -y --no-install-recommends \
        make \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl ./etl
COPY ml ./ml
COPY tests ./tests
COPY Makefile .