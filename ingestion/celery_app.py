from celery import Celery

redis_link = "redis://localhost:6379/0"

app = Celery('grant-rag-worker', 
             broker=redis_link,
             backend=redis_link,
             include=['ingestion.injest'])