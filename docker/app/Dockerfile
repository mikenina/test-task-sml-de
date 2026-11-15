FROM python:3.11-slim

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl ./etl
COPY ml ./ml