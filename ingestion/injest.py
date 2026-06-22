from api.api import DomainRequest

from .fetch_grants import fetch_grant_data
from .pinecone_db import upsert
from .supabase import ingest_batch, downstream_failure, get_bm_25
from .celery_app import app
from .write_to_graph import ingest_graph_nodes



@app.task
def run_injest_pipeline(inj_domain: DomainRequest, neo4j_index, pinecone_index, supabase_conn):
    ids = []
    chunks = []
    try:
        data, domain = fetch_grant_data(inj_domain)
        print(f"fetched {len(data)} awards")
        chunks, ids = ingest_batch(data, supabase_conn)
        print(f"injested and generated {len(chunks)} chunks")
        upsert(chunks, domain, pinecone_index)
        print("successful pinecone upsert")
        ingest_graph_nodes(data, neo4j_index)

    except Exception as e:
        if ids:
            downstream_failure(ids, supabase_conn)
        print(f"Error: {e}")
        raise e
    print("successful pinecone upsert")
    return len(chunks)

