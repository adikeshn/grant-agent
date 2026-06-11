from fetch_grants import fetch_grant_data
from pinecone_db import upsert
from supabase import ingest_batch, downstream_failure

def run_pipeline(yaml_name="neural_eng"):
    ids = []
    try:
        data, name = fetch_grant_data(yaml_filename=yaml_name)
        print(f"fetched {len(data)} awards")
        chunks, ids = ingest_batch(data)
        print(f"injested and generated {len(chunks)} chunks")
        upsert(chunks, name)
    except Exception as e:
        if ids:
            downstream_failure(ids)
        print(f"Error: {e}")
        raise e
    print("successful upsert")
    return 200

print(run_pipeline())

