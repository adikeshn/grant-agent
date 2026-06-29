from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

redis_link = os.getenv("REDIS_URL", "redis://localhost:6379/0")
if redis_link.startswith("rediss://"):
    redis_link += "?ssl_cert_reqs=CERT_REQUIRED"

app = Celery('grant-rag-worker', 
             broker=redis_link,
             backend=redis_link,
             include=['ingestion.injest'])