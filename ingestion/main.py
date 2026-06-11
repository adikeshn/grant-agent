from fetch_grants import fetch_grant_data
from pinecone_db import upsert
from supabase import ingest_batch

def run_pipeline(yaml_name="neural_eng"):
    data, name = fetch_grant_data(yaml_filename=yaml_name)
    chunks = []
    try:
        chunks = ingest_batch(data)
    except Exception as e:
        print(f"Error while injesting awards: {e}")
        raise e

    try:
        upsert(chunks, name)
    except Exception as e:
        print(f"Error while upserting chunks: {e}")
        raise e

    return 200

