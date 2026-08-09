FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN addgroup --system jobtrack \
    && adduser --system --ingroup jobtrack --home /app jobtrack \
    && mkdir -p /data \
    && chown -R jobtrack:jobtrack /app /data

USER jobtrack

EXPOSE 8080
CMD ["uvicorn", "app.application:app", "--host", "0.0.0.0", "--port", "8080"]
