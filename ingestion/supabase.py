import psycopg2
from psycopg2.extras import execute_values
from chunk import chunk_award
from dotenv import load_dotenv
import os

load_dotenv()

link = os.getenv("SUPABASE_LINK")

def get_conn():
    if link is None:
        raise ValueError("SUPABASE_LINK environment variable not set")
    return psycopg2.connect(os.environ[link])

def is_already_ingested(award_id: str, cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM chunks WHERE award_id = %s LIMIT 1",
        (award_id,)
    )
    return cursor.fetchone() is not None

def write_chunks(chunks: list[dict], cursor) -> None:
    execute_values(cursor, """
        INSERT INTO chunks
            (id, award_id, chunk_index, text, source,
             year, amount, institution, directorate, pi_name)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        c["id"], c['metadata']["award_id"], c['metadata']["chunk_index"], c["text"],
        c['metadata']["source"], c['metadata']["year"], c['metadata']["amount"],
        c['metadata']["institution"], c['metadata']["directorate"], c['metadata']["pi_name"]
    ) for c in chunks])

def ingest_batch(awards: list[dict]):
    conn = get_conn()
    cursor = conn.cursor()
    all_chunks = []
    try:
        for award in awards:
            if is_already_ingested(award["award_id"], cursor):
                continue
            chunks = chunk_award(award)
            all_chunks.extend(chunks)
        
        write_chunks(all_chunks, cursor)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    return all_chunks
