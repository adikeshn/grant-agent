FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "if [ \"$SERVICE\" = \"worker\" ]; then celery -A ingestion.celery_app worker --loglevel=info --concurrency=1; else uvicorn api.api:api --host 0.0.0.0 --port 8080; fi"]