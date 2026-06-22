from ingestion.pinecone_db import dense_retrieval
from ingestion.supabase import get_bm_25, tokenize, get_supabase_conn, get_ids
from ingestion.celery_app import app

from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def retrieve_chunk_rankings(bm25_indexes, pinecone_index, domain: str,
                            query_text: str, top_dense: int, top_sparse: int, 
                            top_final: int, rrf_k: int = 60):
    conn = None
    cursor = None
    try:
        conn = get_supabase_conn()
        cursor = conn.cursor()

        # get sparse and dense rankings
        dense_results = dense_retrieval(query_txt=query_text, namespace=domain, k=top_dense, index=pinecone_index)
        chunk_dict = get_ids(domain, cursor)
        if chunk_dict is None:
            raise ValueError("chunk list is None")
        if domain not in bm25_indexes:
            get_bm_25(bm25_indexes, domain, cursor)
        sparse_results = bm25_indexes[domain]["index"].get_top_n(tokenize(query_text), bm25_indexes[domain]["ids"], n=top_sparse)
        
        # calculate reciprocal rank fusion
        print("\n=== DENSE RETRIEVAL RANKINGS ===")
        for rank, match in enumerate(dense_results.matches):
            chunk_dict[match.id][0] += (1 / (rank + 1 + rrf_k))
            print(f"Rank {rank + 1}: {match.id}, {match.score}")

        print("\n=== SPARSE RETRIEVAL RANKINGS ===")
        for rank, item in enumerate(sparse_results, 1):
            chunk_dict[item][0] += (1 / (rank + rrf_k))
            print(f"Rank {rank}: {item}")

        # do reranking with cross encoder
        cross_encode_inp = []
        retrieved_ids = []
        headers = []
        for key, value in chunk_dict.items():
            if value[0] > 0:
                cross_encode_inp.append((query_text, value[1]))
                retrieved_ids.append(key)
                headers.append(value[2])
        return sorted((zip(retrieved_ids, cross_encode_inp, headers, model.predict(cross_encode_inp))), key=lambda x: x[3], reverse=True)[:top_final]


    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during retrieval: {e}")
        raise e

    finally:
        if cursor: cursor.close()
        if conn: conn.close()






