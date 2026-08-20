FROM python:3.12-slim

ARG APP_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN addgroup --system bert \
    && adduser --system --ingroup bert --home /app bert \
    && mkdir -p /data \
    && chown -R bert:bert /app /data

USER bert

EXPOSE 8080
CMD ["uvicorn", "app.application:app", "--host", "0.0.0.0", "--port", "8080"]
