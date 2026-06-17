import psycopg2
from psycopg2.extras import execute_values
from .chunk import chunk_award
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
import os

load_dotenv()

link = os.getenv("SUPABASE_LINK")

stop_words = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
    'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'this', 'that',
    'these', 'those', 'it', 'its', 'as', 'not', 'no', 'so', 'if',
    'than', 'then', 'when', 'where', 'which', 'who', 'how', 'what',
    'all', 'each', 'both', 'more', 'also', 'about', 'into', 'through'
}

def get_conn():
    if link is None:
        raise ValueError("SUPABASE_LINK environment variable not set")
    return psycopg2.connect(link)

def downstream_failure(ids):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM chunks WHERE award_id = ANY(%s)",
            (ids,)
        )
        conn.commit()
    except Exception as e:
        print("error downstreaming")
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    return 200


def is_already_ingested(award_id: str, cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM chunks WHERE award_id = %s LIMIT 1",
        (award_id,)
    )
    return cursor.fetchone() is not None

def tokenize(text: str) -> list[str]:
    tokens = text.lower().split()
    return [t for t in tokens if t not in stop_words]

def get_ids(domain: str, cursor):
    try:
        cursor.execute(
            "SELECT (id, text, award_id, source, year, amount, institution, directorate" +
            "pi_name) FROM chunks WHERE domain = %s",
            (domain,)
        )
        return {row[0]: [0, row[1], {
            "award_id": row[2],
            "source": row[3],
            "year": row[4],
            "amount": row[5],
            "institution": row[6],
            "directorate": row[7],
            "pi_name": row[8],
        }] for row in cursor.fetchall()}
    except Exception as e:
        print(f"exception fetching ids {e}")

def get_bm_25(bm25_indexes: dict, domain: str, cursor) -> BM25Okapi:

    if domain in bm25_indexes and bm25_indexes[domain] is not None:
        return bm25_indexes[domain]

    try:
        cursor.execute(
            "SELECT id, text FROM chunks WHERE domain = %s",
            (domain,)
        )
        output = cursor.fetchall()
        texts = [row[1] for row in output]
        ids = [row[0] for row in output]
        tokenized = [tokenize(text) for text in texts]
        bm25_indexes[domain] = {
            "index": BM25Okapi(tokenized),
            "ids": ids
        }
        return bm25_indexes[domain]
    except Exception as e:
        print(f"BM25 Index generation error: {e.with_traceback}")
        raise e


def write_chunks(chunks: list[dict], cursor) -> None:
    execute_values(cursor, """
        INSERT INTO chunks
            (id, award_id, chunk_index, text, source,
             year, amount, institution, directorate, pi_name, domain)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        c["id"], c['metadata']["award_id"], c['metadata']["chunk_index"], c["text"],
        c['metadata']["source"], c['metadata']["year"], c['metadata']["amount"],
        c['metadata']["institution"], c['metadata']["directorate"], c['metadata']["pi_name"], c['metadata']['domain']
    ) for c in chunks])

def ingest_batch(awards: list[dict]):
    conn = None
    cursor = None
    all_chunks = []
    ids = set()
    try:
        conn = get_conn()
        cursor = conn.cursor()
        for award in awards:
            if is_already_ingested(award["award_id"], cursor):
                continue
            chunks = chunk_award(award)
            all_chunks.extend(chunks)
            ids.add(award["award_id"])
        write_chunks(all_chunks, cursor)
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        raise e
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    return all_chunks, ids
