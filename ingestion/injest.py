import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.api import DomainRequest

from .fetch_grants import fetch_grant_data
from .pinecone_db import upsert
from .supabase import ingest_batch, downstream_failure, get_bm_25
from .celery_app import app



@app.task
def run_injest_pipeline(inj_domain: DomainRequest):
    ids = []
    chunks = []
    try:
        data, domain = fetch_grant_data(inj_domain)
        print(f"fetched {len(data)} awards")
        chunks, ids = ingest_batch(data)
        print(f"injested and generated {len(chunks)} chunks")
        upsert(chunks, domain)
    except Exception as e:
        if ids:
            downstream_failure(ids)
        print(f"Error: {e}")
        raise e
    print("successful pinecone upsert")
    return len(chunks)

